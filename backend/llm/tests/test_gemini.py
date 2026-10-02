from types import SimpleNamespace
from unittest import mock

import httpx
import pytest
from google.genai import errors

import llm
from llm.gemini_provider import GeminiProvider

from .helpers import run

provider = GeminiProvider()


def _chunk(text, finish=None, block=None, usage=None):
    candidate = SimpleNamespace(finish_reason=SimpleNamespace(name=finish) if finish else None)
    return SimpleNamespace(
        text=text,
        candidates=[candidate],
        prompt_feedback=SimpleNamespace(block_reason=SimpleNamespace(name=block))
        if block
        else None,
        usage_metadata=usage,
        model_version="gemini-test-pro" if finish else None,
    )


def _api_error(cls, code, status):
    return cls(code, {"error": {"code": code, "status": status, "message": "secret detail"}})


@pytest.fixture
def client_cls():
    with mock.patch("llm.gemini_provider.genai.Client") as cls:
        yield cls


def test_streams_chunks_and_maps_roles(client_cls):
    usage = SimpleNamespace(prompt_token_count=30, candidates_token_count=4)
    stream = client_cls.return_value.models.generate_content_stream
    stream.return_value = iter([_chunk("월 "), _chunk("5,000원", finish="STOP", usage=usage)])
    messages = [
        {"role": "user", "content": "이전"},
        {"role": "assistant", "content": "답"},
        {"role": "user", "content": "질문"},
    ]

    deltas, final = run(provider.stream_reply("key", "gemini-test-pro", "sys", messages, 512))

    assert deltas == ["월 ", "5,000원"]
    assert (final.text, final.stop_reason, final.model) == ("월 5,000원", "STOP", "gemini-test-pro")
    assert (final.input_tokens, final.output_tokens) == (30, 4)
    kwargs = stream.call_args.kwargs
    assert kwargs["model"] == "gemini-test-pro"
    assert [c.role for c in kwargs["contents"]] == ["user", "model", "user"]
    assert kwargs["contents"][2].parts[0].text == "질문"
    assert kwargs["config"].system_instruction == "sys"
    assert kwargs["config"].max_output_tokens == 512
    options = client_cls.call_args.kwargs["http_options"]
    assert (options.timeout, options.retry_options.attempts) == (60000, 3)


@pytest.mark.parametrize(
    "chunks",
    [
        [_chunk("부분"), _chunk(None, finish="SAFETY")],
        [_chunk(None, block="PROHIBITED_CONTENT")],
    ],
)
def test_safety_blocks_are_refusals(client_cls, chunks):
    client_cls.return_value.models.generate_content_stream.return_value = iter(chunks)

    _, final = run(provider.stream_reply("key", "gemini-test-pro", "sys", [], 512))

    assert final.refused is True
    assert final.text == llm.REFUSAL_MESSAGE


def test_errors_and_log_format(client_cls):
    client_cls.return_value.models.generate_content_stream.side_effect = _api_error(
        errors.ClientError, 429, "RESOURCE_EXHAUSTED"
    )

    with pytest.raises(llm.LLMError) as excinfo:
        run(provider.stream_reply("AIzaSecret", "gemini-test-pro", "sys", [], 512))

    assert str(excinfo.value) == "status=429 code=RESOURCE_EXHAUSTED"


def test_network_error(client_cls):
    client_cls.return_value.models.generate_content_stream.side_effect = httpx.ConnectError("x")

    with pytest.raises(llm.LLMError) as excinfo:
        run(provider.stream_reply("key", "gemini-test-pro", "sys", [], 512))

    assert str(excinfo.value) == "error=ConnectError"


@pytest.mark.parametrize("code", [400, 401, 403])
def test_validate_key_invalid(client_cls, code):
    client_cls.return_value.models.list.side_effect = _api_error(
        errors.ClientError, code, "INVALID_ARGUMENT"
    )

    with pytest.raises(llm.InvalidAPIKey):
        provider.validate_key("bad")


def test_validate_key_ok_and_server_error(client_cls):
    client_cls.return_value.models.list.return_value = iter([SimpleNamespace(name="models/x")])
    provider.validate_key("key")
    assert client_cls.return_value.models.list.call_args.kwargs == {"config": {"page_size": 1}}

    client_cls.return_value.models.list.side_effect = _api_error(
        errors.ServerError, 503, "UNAVAILABLE"
    )
    with pytest.raises(llm.LLMError) as excinfo:
        provider.validate_key("key")
    assert not isinstance(excinfo.value, llm.InvalidAPIKey)


def test_list_models_keeps_generate_content_models(client_cls):
    def model(name, actions=("generateContent",)):
        return SimpleNamespace(name=f"models/{name}", supported_actions=list(actions))

    client_cls.return_value.models.list.return_value = iter(
        [
            model("gemini-test-pro"),
            model("gemini-test-flash"),
            model("gemini-embedding-001", ("embedContent",)),
            model("gemini-test-flash-preview-tts"),
            model("gemini-test-flash-image"),
            model("aqa"),
        ]
    )

    assert provider.list_models("key") == ["gemini-test-flash", "gemini-test-pro"]


def test_temperature_is_supported_and_passed(client_cls):
    assert provider.supports_temperature("gemini-test-pro") is True
    assert provider.temperature_range == (0.0, 2.0)
    stream = client_cls.return_value.models.generate_content_stream
    stream.return_value = iter([_chunk("a", finish="STOP")])

    run(provider.stream_reply("key", "gemini-test-pro", "sys", [], 512, temperature=0.7))

    assert stream.call_args.kwargs["config"].temperature == 0.7


def test_no_temperature_means_model_default(client_cls):
    stream = client_cls.return_value.models.generate_content_stream
    stream.return_value = iter([_chunk("a", finish="STOP")])

    run(provider.stream_reply("key", "gemini-test-pro", "sys", [], 512))

    assert stream.call_args.kwargs["config"].temperature is None


def test_request_params_match_the_real_sdk_signature(client_cls):
    import inspect

    from google.genai.models import Models

    stream = client_cls.return_value.models.generate_content_stream
    stream.return_value = iter([_chunk("a", finish="STOP")])
    run(provider.stream_reply("key", "gemini-test-pro", "sys", [], 512, temperature=0.7))

    inspect.signature(Models.generate_content_stream).bind(None, **stream.call_args.kwargs)
