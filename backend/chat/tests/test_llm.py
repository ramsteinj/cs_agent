from types import SimpleNamespace
from unittest import mock

import anthropic
import httpx2
import pytest

from chat import llm

_REQUEST = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")


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
    with mock.patch("chat.llm.anthropic.Anthropic") as cls:
        yield cls


def _stream_returns(client_cls, deltas, final):
    stream = mock.MagicMock()
    stream.text_stream = iter(deltas)
    stream.get_final_message.return_value = final
    client_cls.return_value.beta.messages.stream.return_value.__enter__.return_value = stream
    return client_cls.return_value.beta.messages.stream


def _run(gen):
    deltas = []
    while True:
        try:
            deltas.append(next(gen))
        except StopIteration as stop:
            return deltas, stop.value


def test_streams_deltas_and_returns_final(client_cls):
    _stream_returns(client_cls, ["안녕", "하세요"], _final("안녕하세요"))

    deltas, final = _run(llm.stream_reply("key", "claude-opus-5-5", "sys", [{"role": "user"}]))

    assert deltas == ["안녕", "하세요"]
    assert final.text == "안녕하세요"
    assert (final.input_tokens, final.output_tokens) == (100, 20)
    assert final.refused is False
    assert client_cls.call_args.kwargs == {"api_key": "key", "timeout": 60, "max_retries": 2}


def test_opus_request_uses_low_effort_and_default_fallback(client_cls):
    stream = _stream_returns(client_cls, [], _final())

    _run(llm.stream_reply("key", "claude-opus-5-5", "sys", []))

    params = stream.call_args.kwargs
    assert params["model"] == "claude-opus-5-5"
    assert params["max_tokens"] == 4096
    assert params["output_config"] == {"effort": "low"}
    assert params["fallbacks"] == "default"
    assert params["betas"] == ["server-side-fallback-2026-07-01"]
    assert "thinking" not in params


def test_haiku_request_omits_effort_and_fallback(client_cls):
    stream = _stream_returns(client_cls, [], _final())

    _run(llm.stream_reply("key", "claude-haiku-4-5", "sys", []))

    params = stream.call_args.kwargs
    assert "output_config" not in params
    assert "fallbacks" not in params
    assert "betas" not in params


def test_refusal_is_replaced_with_polite_message(client_cls):
    _stream_returns(client_cls, ["부분"], _final("부분", stop_reason="refusal"))

    _, final = _run(llm.stream_reply("key", "claude-opus-5-5", "sys", []))

    assert final.refused is True
    assert final.text == llm.REFUSAL_MESSAGE


@pytest.mark.parametrize(
    "error",
    [
        anthropic.AuthenticationError(
            "x", response=httpx2.Response(401, request=_REQUEST), body=None
        ),
        anthropic.RateLimitError("x", response=httpx2.Response(429, request=_REQUEST), body=None),
        anthropic.InternalServerError(
            "x", response=httpx2.Response(500, request=_REQUEST), body=None
        ),
        anthropic.APIConnectionError(request=_REQUEST),
    ],
)
def test_api_errors_become_llm_error(client_cls, error):
    client_cls.return_value.beta.messages.stream.side_effect = error

    with pytest.raises(llm.LLMError):
        _run(llm.stream_reply("sk-ant-secret-key", "claude-opus-5-5", "sys", []))


def test_api_key_is_not_logged(client_cls, caplog):
    client_cls.return_value.beta.messages.stream.side_effect = anthropic.AuthenticationError(
        "invalid x-api-key sk-ant-secret-key",
        response=httpx2.Response(401, request=_REQUEST),
        body=None,
    )

    with pytest.raises(llm.LLMError):
        _run(llm.stream_reply("sk-ant-secret-key", "claude-opus-5-5", "sys", []))

    assert "sk-ant-secret-key" not in caplog.text
