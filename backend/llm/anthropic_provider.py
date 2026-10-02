"""Claude via the official anthropic SDK."""

import logging

import anthropic

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

# Customer-support chat does well at low effort and answers faster. Haiku 4.5 rejects
# effort; server-side fallbacks are for Opus 5.5 / Sonnet 5.5.
EFFORT = "low"
EFFORT_MODELS = {"claude-opus-5-5", "claude-sonnet-5-5"}
FALLBACK_MODELS = {"claude-opus-5-5", "claude-sonnet-5-5"}
FALLBACK_BETA = "server-side-fallback-2026-07-01"


class AnthropicProvider(Provider):
    name = "anthropic"
    label = "Claude"
    default_model = "claude-opus-5-5"
    recommended_models = ("claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-4-5")
    key_prefix = "sk-ant-"
    temperature_range = (0.0, 1.0)
    # Opus 4.7+ (4.8, 5, 5.5), Sonnet 5 / 5.5 and Fable reject sampling parameters (400).
    temperature_model_prefixes = (
        "claude-haiku-4-5",
        "claude-opus-4-6",
        "claude-sonnet-4-6",
        "claude-opus-4-5",
        "claude-sonnet-4-5",
        "claude-opus-4-1",
        "claude-opus-4-0",
        "claude-sonnet-4-0",
        "claude-3",
    )

    def _client(self, api_key, timeout=TIMEOUT_SECONDS, max_retries=MAX_RETRIES):
        return anthropic.Anthropic(api_key=api_key, timeout=timeout, max_retries=max_retries)

    def describe_error(self, exc):
        if isinstance(exc, anthropic.APIStatusError):
            return (
                f"status={exc.status_code} type={exc.type or 'unknown'} "
                f"request_id={exc.request_id or '-'}"
            )
        return f"error={type(exc).__name__}"

    def validate_key(self, api_key):
        client = self._client(api_key, timeout=VALIDATION_TIMEOUT_SECONDS, max_retries=1)
        try:
            client.models.list(limit=1)
        except (anthropic.AuthenticationError, anthropic.PermissionDeniedError) as exc:
            raise InvalidAPIKey(self.describe_error(exc)) from None
        except anthropic.APIError as exc:
            raise LLMError(self.describe_error(exc)) from None

    def list_models(self, api_key):
        try:
            ids = [model.id for model in self._client(api_key).models.list(limit=100)]
        except anthropic.APIError as exc:
            raise LLMError(self.describe_error(exc)) from None
        return [*self.recommended_models, *(i for i in ids if i not in self.recommended_models)]

    def _params(self, model, system, messages, max_output_tokens, temperature=None):
        params = {
            "model": model,
            "max_tokens": max_output_tokens,
            "system": system,
            "messages": messages,
        }
        temperature = self.effective_temperature(model, temperature)
        if temperature is not None:
            params["temperature"] = temperature
        if model in EFFORT_MODELS:
            params["output_config"] = {"effort": EFFORT}
        if model in FALLBACK_MODELS:
            # On a safety-classifier decline the API re-runs the request on Anthropic's
            # recommended fallback model inside the same call.
            params["betas"] = [FALLBACK_BETA]
            params["fallbacks"] = "default"
        return params

    def stream_reply(self, api_key, model, system, messages, max_output_tokens, temperature=None):
        client = self._client(api_key)
        try:
            params = self._params(model, system, messages, max_output_tokens, temperature)
            with client.beta.messages.stream(**params) as stream:
                for text in stream.text_stream:
                    yield text
                final = stream.get_final_message()
        except anthropic.APIError as exc:
            raise LLMError(self.describe_error(exc)) from None

        text = "".join(block.text for block in final.content if block.type == "text")
        refused = final.stop_reason == "refusal"
        if refused:
            category = getattr(getattr(final, "stop_details", None), "category", None)
            logger.info("Claude declined a request (category=%s)", category)
            text = REFUSAL_MESSAGE
        usage = final.usage
        return FinalReply(
            text=text,
            model=final.model,
            stop_reason=final.stop_reason,
            input_tokens=getattr(usage, "input_tokens", None),
            output_tokens=getattr(usage, "output_tokens", None),
            refused=refused,
        )
