"""The only place that calls the Claude API (CLAUDE.md, specs/05-rag-pipeline.md §4.1)."""

import logging
from dataclasses import dataclass

import anthropic

from common.anthropic_errors import describe_api_error

logger = logging.getLogger(__name__)

MAX_TOKENS = 4096
TIMEOUT_SECONDS = 60
MAX_RETRIES = 2
# Customer-support chat does well at low effort and answers faster (specs/05 §4.1).
EFFORT = "low"
# Models that accept output_config.effort / server-side fallbacks. Haiku 4.5 rejects effort.
EFFORT_MODELS = {"claude-opus-5-5", "claude-sonnet-5-5"}
FALLBACK_MODELS = {"claude-opus-5-5", "claude-sonnet-5-5"}
FALLBACK_BETA = "server-side-fallback-2026-07-01"

REFUSAL_MESSAGE = "죄송합니다. 해당 질문에는 답변드리기 어렵습니다."


class LLMError(Exception):
    """Claude call failed. The message is safe to log (no key, no raw API text)."""


@dataclass
class FinalReply:
    text: str
    model: str
    stop_reason: str | None
    input_tokens: int | None
    output_tokens: int | None
    refused: bool = False


def _request_params(model, system, messages):
    params = {
        "model": model,
        "max_tokens": MAX_TOKENS,
        "system": system,
        "messages": messages,
    }
    if model in EFFORT_MODELS:
        params["output_config"] = {"effort": EFFORT}
    if model in FALLBACK_MODELS:
        # On a safety-classifier decline the API re-runs the request on Anthropic's
        # recommended fallback model inside the same call.
        params["betas"] = [FALLBACK_BETA]
        params["fallbacks"] = "default"
    return params


def stream_reply(api_key, model, system, messages):
    """Yield text deltas, then return a FinalReply (use `yield from` to get it).

    Raises LLMError on any API failure.
    """
    client = anthropic.Anthropic(api_key=api_key, timeout=TIMEOUT_SECONDS, max_retries=MAX_RETRIES)
    try:
        with client.beta.messages.stream(**_request_params(model, system, messages)) as stream:
            for text in stream.text_stream:
                yield text
            final = stream.get_final_message()
    except anthropic.APIError as exc:
        # e.g. "status=400 type=invalid_request_error request_id=req_..." (no key, no raw text)
        description = describe_api_error(exc)
        logger.warning("Claude API call failed (model=%s): %s", model, description)
        raise LLMError(description) from None

    text = "".join(block.text for block in final.content if block.type == "text")
    refused = final.stop_reason == "refusal"
    if refused:
        logger.info("Claude declined a request (category=%s)", _refusal_category(final))
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


def _refusal_category(message):
    details = getattr(message, "stop_details", None)
    return getattr(details, "category", None)
