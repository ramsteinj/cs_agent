"""Common interface for LLM providers (specs/05 §4.1).

Every provider implements the same methods so chat and settings code never touch a
vendor SDK directly. Errors are converted to LLMError / InvalidAPIKey whose messages
are safe to log (status, error type, request ID; never the key or raw API text).
"""

from dataclasses import dataclass

TIMEOUT_SECONDS = 60
MAX_RETRIES = 2
VALIDATION_TIMEOUT_SECONDS = 15

REFUSAL_MESSAGE = "죄송합니다. 해당 질문에는 답변드리기 어렵습니다."


class LLMError(Exception):
    """The provider call failed. str(exc) is a loggable summary."""


class InvalidAPIKey(LLMError):
    """The provider rejected the API Key."""


@dataclass
class FinalReply:
    text: str
    model: str
    stop_reason: str | None
    input_tokens: int | None
    output_tokens: int | None
    refused: bool = False


class Provider:
    name = ""
    label = ""
    default_model = ""
    recommended_models: tuple = ()
    key_prefix = ""  # fixed, non-secret key prefix shown in the masked value

    def mask_key(self, api_key):
        prefix = self.key_prefix if api_key.startswith(self.key_prefix) else ""
        return f"{prefix}...{api_key[-4:]}"

    def validate_key(self, api_key):
        """Cheap/free call (model listing). Raises InvalidAPIKey or LLMError."""
        raise NotImplementedError

    def list_models(self, api_key):
        """Chat-capable model IDs."""
        raise NotImplementedError

    def stream_reply(self, api_key, model, system, messages, max_output_tokens):
        """Yield text deltas, then return a FinalReply (use `yield from`).

        messages: [{"role": "user" | "assistant", "content": str}, ...]
        """
        raise NotImplementedError

    def describe_error(self, exc):
        return f"error={type(exc).__name__}"
