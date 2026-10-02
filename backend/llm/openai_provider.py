"""ChatGPT via the official openai SDK (Responses API)."""

import logging

import openai

from .base import (
    MAX_RETRIES,
    REFUSAL_MESSAGE,
    TIMEOUT_SECONDS,
    VALIDATION_TIMEOUT_SECONDS,
    FinalReply,
    InvalidAPIKey,
    LLMError,
    Provider,
)

logger = logging.getLogger(__name__)

CHAT_PREFIXES = ("gpt-", "o1", "o3", "o4", "chatgpt-")
NON_CHAT_MARKERS = ("audio", "realtime", "transcribe", "tts", "image", "search", "embedding")


def is_chat_model(model_id):
    return model_id.startswith(CHAT_PREFIXES) and not any(m in model_id for m in NON_CHAT_MARKERS)


class OpenAIProvider(Provider):
    name = "openai"
    label = "ChatGPT"
    default_model = ""  # chosen by the admin from the account's model list
    key_prefix = "sk-"

    def _client(self, api_key, timeout=TIMEOUT_SECONDS, max_retries=MAX_RETRIES):
        return openai.OpenAI(api_key=api_key, timeout=timeout, max_retries=max_retries)

    def describe_error(self, exc):
        if isinstance(exc, openai.APIStatusError):
            return (
                f"status={exc.status_code} type={exc.type or 'unknown'} "
                f"code={exc.code or '-'} request_id={exc.request_id or '-'}"
            )
        return f"error={type(exc).__name__}"

    def validate_key(self, api_key):
        client = self._client(api_key, timeout=VALIDATION_TIMEOUT_SECONDS, max_retries=1)
        try:
            client.models.list()
        except (openai.AuthenticationError, openai.PermissionDeniedError) as exc:
            raise InvalidAPIKey(self.describe_error(exc)) from None
        except openai.APIError as exc:
            raise LLMError(self.describe_error(exc)) from None

    def list_models(self, api_key):
        try:
            ids = [model.id for model in self._client(api_key).models.list()]
        except openai.APIError as exc:
            raise LLMError(self.describe_error(exc)) from None
        return sorted(i for i in ids if is_chat_model(i))

    def stream_reply(self, api_key, model, system, messages, max_output_tokens):
        client = self._client(api_key)
        try:
            with client.responses.stream(
                model=model,
                instructions=system,
                input=[{"role": m["role"], "content": m["content"]} for m in messages],
                max_output_tokens=max_output_tokens,
            ) as stream:
                for event in stream:
                    if event.type == "response.output_text.delta":
                        yield event.delta
                final = stream.get_final_response()
        except openai.APIError as exc:
            raise LLMError(self.describe_error(exc)) from None

        if final.error:
            raise LLMError(f"response failed code={final.error.code}")
        refused = any(
            getattr(part, "type", None) == "refusal"
            for item in final.output
            if getattr(item, "type", None) == "message"
            for part in item.content
        )
        text = final.output_text
        if refused:
            logger.info("ChatGPT declined a request")
            text = REFUSAL_MESSAGE
        incomplete = getattr(final.incomplete_details, "reason", None)
        usage = final.usage
        return FinalReply(
            text=text,
            model=final.model,
            stop_reason="refusal" if refused else (incomplete or final.status),
            input_tokens=getattr(usage, "input_tokens", None),
            output_tokens=getattr(usage, "output_tokens", None),
            refused=refused,
        )
