"""LLM provider key validation and model listing for the admin API (specs/04 §6)."""

import logging

from rest_framework import status

import llm
from common.exceptions import ApiError

logger = logging.getLogger(__name__)

INVALID_KEY_MESSAGE = "유효하지 않은 API Key입니다."
UNREACHABLE_MESSAGE = "LLM API에 연결할 수 없어 확인하지 못했습니다. 잠시 후 다시 시도해 주세요."


def _unreachable():
    return ApiError("LLM_ERROR", UNREACHABLE_MESSAGE, status.HTTP_502_BAD_GATEWAY)


def validate_api_key(provider, api_key):
    """One cheap provider call. Raises ApiError INVALID_API_KEY (400) or LLM_ERROR (502).

    Log lines carry only status / error type / request ID (never the key).
    """
    try:
        llm.get_provider(provider).validate_key(api_key)
    except llm.InvalidAPIKey as exc:
        logger.info("%s API Key rejected: %s", provider, exc)
        raise ApiError(
            "INVALID_API_KEY", INVALID_KEY_MESSAGE, status.HTTP_400_BAD_REQUEST
        ) from None
    except llm.LLMError as exc:
        logger.warning("%s API Key validation failed: %s", provider, exc)
        raise _unreachable() from None


def list_models(config):
    """Selectable models. Claude falls back to its recommended list without a key."""
    spec = config.spec
    api_key = config.get_api_key()
    if api_key is None:
        if spec.recommended_models:
            return list(spec.recommended_models)
        raise ApiError(
            "API_KEY_REQUIRED",
            f"{spec.label} API Key를 먼저 등록해 주세요.",
            status.HTTP_400_BAD_REQUEST,
        )
    try:
        return spec.list_models(api_key)
    except llm.LLMError as exc:
        logger.warning("%s model listing failed: %s", config.provider, exc)
        raise _unreachable() from None
