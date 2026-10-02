from types import SimpleNamespace
from unittest import mock

import httpx2
import openai
import pytest

import llm
from llm.openai_provider import OpenAIProvider, is_chat_model

from .helpers import run

_REQUEST = httpx2.Request("POST", "https://api.openai.com/v1/responses")
provider = OpenAIProvider()


def _status_error(cls, code, err_type, err_code=None, request_id="req_abc"):
    response = httpx2.Response(code, request=_REQUEST, headers={"x-request-id": request_id})
    body = {"message": "secret detail", "type": err_type, "code": err_code}
    return cls("secret detail", response=response, body=body)


def _final(text="답변", refusal=False, error=None, incomplete=None):
    content = [SimpleNamespace(type="refusal" if refusal else "output_text", text=text)]
    return SimpleNamespace(
        output=[
            SimpleNamespace(type="reasoning"),
            SimpleNamespace(type="message", content=content),
        ],
        output_text="" if refusal else text,
        model="gpt-test-1",
        status="incomplete" if incomplete else "completed",
        incomplete_details=SimpleNamespace(reason=incomplete) if incomplete else None,
        error=error,
        usage=SimpleNamespace(input_tokens=50, output_tokens=7),
    )


@pytest.fixture
def client_cls():
    with mock.patch("llm.openai_provider.openai.OpenAI") as cls:
        yield cls


def _stream_returns(client_cls, deltas, final):
    events = [SimpleNamespace(type="response.created")] + [
        SimpleNamespace(type="response.output_text.delta", delta=d) for d in deltas
    ]
    stream = mock.MagicMock()
    stream.__iter__.return_value = iter(events)
    stream.get_final_response.return_value = final
    client_cls.return_value.responses.stream.return_value.__enter__.return_value = stream
    return client_cls.return_value.responses.stream


def test_streams_text_deltas_with_responses_api(client_cls):
    stream = _stream_returns(client_cls, ["월 ", "5,000원"], _final("월 5,000원"))
    messages = [
        {"role": "user", "content": "이전"},
        {"role": "assistant", "content": "답"},
        {"role": "user", "content": "질문"},
    ]

    deltas, final = run(provider.stream_reply("key", "gpt-test-1", "sys", messages, 1024))

    assert deltas == ["월 ", "5,000원"]
    assert (final.text, final.model, final.stop_reason) == ("월 5,000원", "gpt-test-1", "completed")
    assert (final.input_tokens, final.output_tokens) == (50, 7)
    assert stream.call_args.kwargs == {
        "model": "gpt-test-1",
        "instructions": "sys",
        "input": messages,
        "max_output_tokens": 1024,
    }


def test_refusal(client_cls):
    _stream_returns(client_cls, [], _final("I can't help with that", refusal=True))

    _, final = run(provider.stream_reply("key", "gpt-test-1", "sys", [], 1024))

    assert final.refused is True
    assert final.text == llm.REFUSAL_MESSAGE


def test_incomplete_keeps_partial_text(client_cls):
    _stream_returns(client_cls, ["부분"], _final("부분", incomplete="max_output_tokens"))

    _, final = run(provider.stream_reply("key", "gpt-test-1", "sys", [], 256))

    assert (final.text, final.stop_reason) == ("부분", "max_output_tokens")


def test_failed_response_raises(client_cls):
    _stream_returns(client_cls, [], _final("", error=SimpleNamespace(code="server_error")))

    with pytest.raises(llm.LLMError):
        run(provider.stream_reply("key", "gpt-test-1", "sys", [], 256))


def test_errors_and_log_format(client_cls):
    error = _status_error(
        openai.RateLimitError, 429, "insufficient_quota", "insufficient_quota", "req_q1"
    )
    client_cls.return_value.responses.stream.side_effect = error

    with pytest.raises(llm.LLMError) as excinfo:
        run(provider.stream_reply("sk-proj-secret", "gpt-test-1", "sys", [], 256))

    assert str(excinfo.value) == (
        "status=429 type=insufficient_quota code=insufficient_quota request_id=req_q1"
    )


def test_validate_key(client_cls):
    provider.validate_key("key")
    client_cls.return_value.models.list.assert_called_once_with()

    client_cls.return_value.models.list.side_effect = _status_error(
        openai.AuthenticationError, 401, "invalid_request_error", "invalid_api_key"
    )
    with pytest.raises(llm.InvalidAPIKey):
        provider.validate_key("bad")

    client_cls.return_value.models.list.side_effect = openai.APIConnectionError(request=_REQUEST)
    with pytest.raises(llm.LLMError) as excinfo:
        provider.validate_key("key")
    assert str(excinfo.value) == "error=APIConnectionError"


def test_list_models_keeps_chat_models_only(client_cls):
    ids = [
        "gpt-test-1",
        "gpt-test-1-mini",
        "o4-mini",
        "text-embedding-3-small",
        "gpt-4o-audio-preview",
        "gpt-4o-realtime-preview",
        "whisper-1",
        "dall-e-3",
        "gpt-image-1",
        "gpt-4o-mini-tts",
        "gpt-4o-search-preview",
    ]
    client_cls.return_value.models.list.return_value = [SimpleNamespace(id=i) for i in ids]

    assert provider.list_models("key") == ["gpt-test-1", "gpt-test-1-mini", "o4-mini"]


def test_is_chat_model():
    assert is_chat_model("chatgpt-4o-latest")
    assert not is_chat_model("gpt-4o-transcribe")


@pytest.mark.parametrize(
    ("model", "supported"),
    [
        ("gpt-4.1", True),
        ("gpt-4o-mini", True),
        ("chatgpt-4o-latest", True),
        ("gpt-3.5-turbo", True),
        ("o3", False),
        ("o4-mini", False),
        ("gpt-5", False),
        ("gpt-test-1", False),
    ],
)
def test_temperature_support(model, supported):
    assert provider.supports_temperature(model) is supported


def test_temperature_sent_only_when_supported(client_cls):
    stream = _stream_returns(client_cls, [], _final())

    run(provider.stream_reply("key", "gpt-4.1", "sys", [], 256, temperature=1.4))
    assert stream.call_args.kwargs["temperature"] == 1.4

    run(provider.stream_reply("key", "o4-mini", "sys", [], 256, temperature=1.4))
    assert "temperature" not in stream.call_args.kwargs
