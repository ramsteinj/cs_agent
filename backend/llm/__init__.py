"""LLM providers: the only place that calls ChatGPT / Claude / Gemini (CLAUDE.md)."""

from .anthropic_provider import AnthropicProvider
from .base import REFUSAL_MESSAGE, FinalReply, InvalidAPIKey, LLMError, Provider
from .gemini_provider import GeminiProvider
from .openai_provider import OpenAIProvider

PROVIDERS = {p.name: p for p in (AnthropicProvider(), OpenAIProvider(), GeminiProvider())}
PROVIDER_CHOICES = [(p.name, p.label) for p in PROVIDERS.values()]
DEFAULT_PROVIDER = "anthropic"


def get_provider(name):
    try:
        return PROVIDERS[name]
    except KeyError:
        raise ValueError(f"Unknown LLM provider: {name}") from None


def stream_reply(provider, api_key, model, system, messages, max_output_tokens, temperature=None):
    """Yield text deltas from the given provider, then return a FinalReply."""
    return (
        yield from get_provider(provider).stream_reply(
            api_key, model, system, messages, max_output_tokens, temperature
        )
    )


__all__ = [
    "DEFAULT_PROVIDER",
    "PROVIDERS",
    "PROVIDER_CHOICES",
    "REFUSAL_MESSAGE",
    "FinalReply",
    "InvalidAPIKey",
    "LLMError",
    "Provider",
    "get_provider",
    "stream_reply",
]
