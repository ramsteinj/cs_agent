import logging

import anthropic
from rest_framework import status

from common.exceptions import ApiError

logger = logging.getLogger(__name__)

VALIDATION_TIMEOUT_SECONDS = 15


def validate_api_key(api_key: str):
    """Check the key against the Anthropic API with one cheap call (specs/01 F-A6).

    Raises ApiError INVALID_API_KEY (400) when Anthropic rejects the key, or
    LLM_ERROR (502) when the check could not be completed. Exception text is never
    exposed or logged because it may echo part of the key.
    """
    client = anthropic.Anthropic(api_key=api_key, max_retries=1, timeout=VALIDATION_TIMEOUT_SECONDS)
    try:
        client.models.list(limit=1)
    except (anthropic.AuthenticationError, anthropic.PermissionDeniedError):
        raise ApiError(
            "INVALID_API_KEY", "유효하지 않은 API Key입니다.", status.HTTP_400_BAD_REQUEST
        ) from None
    except anthropic.APIError as exc:
        logger.warning("API Key validation failed: %s", type(exc).__name__)
        raise ApiError(
            "LLM_ERROR",
            "Anthropic API에 연결할 수 없어 API Key를 확인하지 못했습니다. "
            "잠시 후 다시 시도해 주세요.",
            status.HTTP_502_BAD_GATEWAY,
        ) from None
