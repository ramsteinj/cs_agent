from types import SimpleNamespace
from unittest import mock

import anthropic
import httpx2
import pytest

import llm
from llm.anthropic_provider import AnthropicProvider

from .helpers import run

_REQUEST = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
provider = AnthropicProvider()


def _status_error(cls, code, error_type="invalid_request_error", request_id="req_011x"):
    response = httpx2.Response(code, request=_REQUEST, headers={"request-id": request_id})
    body = {"type": "error", "error": {"type": error_type, "message": "secret detail"}}
    return cls("secret detail", response=response, body=body)


def _final(text="답변", stop_reason="end_turn"):
    return SimpleNamespace(
        content=[SimpleNamespace(type="thinking"), SimpleNamespace(type="text", text=text)],
        model="claude-opus-5-5",
        stop_reason=stop_reason,
        stop_details=SimpleNamespace(category="cyber") if stop_reason == "refusal" else None,
        usage=SimpleNamespace(input_tokens=100, output_tokens=20),
    )


@pytest.fixture
def client_cls():
    with mock.patch("llm.anthropic_provider.anthropic.Anthropic") as cls:
        yield cls


def _stream_returns(client_cls, deltas, final):
    stream = mock.MagicMock()
    stream.text_stream = iter(deltas)
    stream.get_final_message.return_value = final
    client_cls.return_value.beta.messages.stream.return_value.__enter__.return_value = stream
    return client_cls.return_value.beta.messages.stream


def test_streams_deltas_and_returns_final(client_cls):
    _stream_returns(client_cls, ["안녕", "하세요"], _final("안녕하세요"))

    deltas, final = run(provider.stream_reply("key", "claude-opus-5-5", "sys", [], 4096))

    assert deltas == ["안녕", "하세요"]
    assert final.text == "안녕하세요"
    assert (final.input_tokens, final.output_tokens) == (100, 20)
    assert client_cls.call_args.kwargs == {"api_key": "key", "timeout": 60, "max_retries": 2}


def test_dispatch_through_package(client_cls):
    _stream_returns(client_cls, ["a"], _final("a"))

    _, final = run(llm.stream_reply("anthropic", "key", "claude-opus-5-5", "sys", [], 100))

    assert final.text == "a"


def test_opus_request_uses_low_effort_and_default_fallback(client_cls):
    stream = _stream_returns(client_cls, [], _final())

    run(provider.stream_reply("key", "claude-opus-5-5", "sys", [{"role": "user"}], 2048))

    params = stream.call_args.kwargs
    assert params["model"] == "claude-opus-5-5"
    assert params["max_tokens"] == 2048
    assert params["system"] == "sys"
    assert params["output_config"] == {"effort": "low"}
    assert params["fallbacks"] == "default"
    assert params["betas"] == ["server-side-fallback-2026-07-01"]
    assert "thinking" not in params


def test_haiku_request_omits_effort_and_fallback(client_cls):
    stream = _stream_returns(client_cls, [], _final())

    run(provider.stream_reply("key", "claude-haiku-4-5", "sys", [], 4096))

    params = stream.call_args.kwargs
    assert "output_config" not in params
    assert "fallbacks" not in params
    assert "betas" not in params


def test_refusal_is_replaced_with_polite_message(client_cls):
    _stream_returns(client_cls, ["부분"], _final("부분", stop_reason="refusal"))

    _, final = run(provider.stream_reply("key", "claude-opus-5-5", "sys", [], 4096))

    assert final.refused is True
    assert final.text == llm.REFUSAL_MESSAGE


@pytest.mark.parametrize(
    "error",
    [
        _status_error(anthropic.AuthenticationError, 401, "authentication_error"),
        _status_error(anthropic.RateLimitError, 429, "rate_limit_error"),
        _status_error(anthropic.InternalServerError, 500, "api_error"),
        anthropic.APIConnectionError(request=_REQUEST),
    ],
)
def test_api_errors_become_llm_error_without_secrets(client_cls, error):
    client_cls.return_value.beta.messages.stream.side_effect = error

    with pytest.raises(llm.LLMError) as excinfo:
        run(provider.stream_reply("sk-ant-secret-key", "claude-opus-5-5", "sys", [], 4096))

    assert "secret" not in str(excinfo.value)


def test_describe_error_format():
    error = _status_error(anthropic.BadRequestError, 400, request_id="req_011credit")

    assert provider.describe_error(error) == (
        "status=400 type=invalid_request_error request_id=req_011credit"
    )
    assert provider.describe_error(anthropic.APITimeoutError(request=_REQUEST)) == (
        "error=APITimeoutError"
    )


def test_validate_key(client_cls):
    provider.validate_key("key")
    client_cls.return_value.models.list.assert_called_once_with(limit=1)

    client_cls.return_value.models.list.side_effect = _status_error(
        anthropic.AuthenticationError, 401, "authentication_error"
    )
    with pytest.raises(llm.InvalidAPIKey):
        provider.validate_key("bad")

    client_cls.return_value.models.list.side_effect = anthropic.APIConnectionError(request=_REQUEST)
    with pytest.raises(llm.LLMError) as excinfo:
        provider.validate_key("key")
    assert not isinstance(excinfo.value, llm.InvalidAPIKey)


def test_list_models_puts_recommended_first(client_cls):
    client_cls.return_value.models.list.return_value = [
        SimpleNamespace(id="claude-sonnet-5-5"),
        SimpleNamespace(id="claude-opus-4-8"),
    ]

    assert provider.list_models("key") == [
        "claude-opus-5-5",
        "claude-sonnet-5-5",
        "claude-haiku-4-5",
        "claude-opus-4-8",
    ]


@pytest.mark.parametrize(
    ("model", "supported"),
    [
        ("claude-opus-5-5", False),
        ("claude-sonnet-5-5", False),
        ("claude-opus-5", False),
        ("claude-sonnet-5", False),
        ("claude-opus-4-8", False),
        ("claude-opus-4-7", False),
        ("claude-fable-5-1", False),
        ("claude-haiku-4-5", True),
        ("claude-haiku-4-5-20251001", True),
        ("claude-sonnet-4-6", True),
        ("claude-opus-4-6", True),
        ("claude-3-7-sonnet-latest", True),
        ("claude-future-9", False),
        ("", False),
    ],
)
def test_temperature_support(model, supported):
    assert provider.supports_temperature(model) is supported


def test_temperature_range_is_0_to_1():
    assert provider.temperature_range == (0.0, 1.0)


def test_temperature_sent_only_when_supported(client_cls):
    stream = _stream_returns(client_cls, [], _final())

    run(provider.stream_reply("key", "claude-haiku-4-5", "sys", [], 512, temperature=0.3))
    assert stream.call_args.kwargs["temperature"] == 0.3

    run(provider.stream_reply("key", "claude-opus-5-5", "sys", [], 512, temperature=0.3))
    assert "temperature" not in stream.call_args.kwargs

    run(provider.stream_reply("key", "claude-haiku-4-5", "sys", [], 512, temperature=None))
    assert "temperature" not in stream.call_args.kwargs
