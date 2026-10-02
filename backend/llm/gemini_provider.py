"""Gemini via the official google-genai SDK."""

import logging

import httpx
from google import genai
from google.genai import errors, types

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

NON_CHAT_MARKERS = ("embedding", "tts", "image", "aqa")
BLOCKED_FINISH_REASONS = {"SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST", "SPII"}
# Invalid keys come back as 400 INVALID_ARGUMENT (API_KEY_INVALID), 401 or 403.
INVALID_KEY_CODES = {400, 401, 403}


def _enum_name(value):
    return getattr(value, "name", None) or (str(value) if value else None)


class GeminiProvider(Provider):
    name = "gemini"
    label = "Gemini"
    default_model = ""  # chosen by the admin from the account's model list
    key_prefix = "AIza"

    def supports_temperature(self, model):
        return bool(model)  # every generateContent chat model accepts temperature

    def _client(self, api_key, timeout=TIMEOUT_SECONDS, attempts=MAX_RETRIES + 1):
        options = types.HttpOptions(
            timeout=int(timeout * 1000),  # milliseconds
            retry_options=types.HttpRetryOptions(attempts=attempts),
        )
        return genai.Client(api_key=api_key, http_options=options)

    def describe_error(self, exc):
        if isinstance(exc, errors.APIError):
            return f"status={exc.code} code={exc.status or 'unknown'}"
        return f"error={type(exc).__name__}"

    def validate_key(self, api_key):
        client = self._client(api_key, timeout=VALIDATION_TIMEOUT_SECONDS, attempts=1)
        try:
            next(iter(client.models.list(config={"page_size": 1})), None)
        except errors.ClientError as exc:
            if exc.code in INVALID_KEY_CODES:
                raise InvalidAPIKey(self.describe_error(exc)) from None
            raise LLMError(self.describe_error(exc)) from None
        except (errors.APIError, httpx.HTTPError) as exc:
            raise LLMError(self.describe_error(exc)) from None

    def list_models(self, api_key):
        try:
            models = list(self._client(api_key).models.list(config={"page_size": 100}))
        except (errors.APIError, httpx.HTTPError) as exc:
            raise LLMError(self.describe_error(exc)) from None
        ids = []
        for model in models:
            name = (model.name or "").removeprefix("models/")
            if "generateContent" not in (model.supported_actions or []):
                continue
            if name and not any(marker in name for marker in NON_CHAT_MARKERS):
                ids.append(name)
        return sorted(ids)

    def stream_reply(self, api_key, model, system, messages, max_output_tokens, temperature=None):
        client = self._client(api_key)
        contents = [
            types.Content(
                role="model" if m["role"] == "assistant" else "user",
                parts=[types.Part.from_text(text=m["content"])],
            )
            for m in messages
        ]
        config = types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=max_output_tokens,
            temperature=self.effective_temperature(model, temperature),
        )
        last = None
        streamed = []
        try:
            for chunk in client.models.generate_content_stream(
                model=model, contents=contents, config=config
            ):
                last = chunk
                text = chunk.text
                if text:
                    streamed.append(text)
                    yield text
        except (errors.APIError, httpx.HTTPError) as exc:
            raise LLMError(self.describe_error(exc)) from None

        candidate = last.candidates[0] if last and last.candidates else None
        finish = _enum_name(candidate.finish_reason) if candidate else None
        blocked = _enum_name(getattr(last.prompt_feedback, "block_reason", None)) if last else None
        refused = bool(blocked) or finish in BLOCKED_FINISH_REASONS
        text = "".join(streamed)
        if refused:
            logger.info("Gemini declined a request (finish=%s, block=%s)", finish, blocked)
            text = REFUSAL_MESSAGE
        usage = last.usage_metadata if last else None
        return FinalReply(
            text=text,
            model=(last.model_version if last and last.model_version else model),
            stop_reason="refusal" if refused else finish,
            input_tokens=getattr(usage, "prompt_token_count", None),
            output_tokens=getattr(usage, "candidates_token_count", None),
            refused=refused,
        )
