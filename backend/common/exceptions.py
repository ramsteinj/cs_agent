"""Common API error format (specs/04-api.md):

{"error": {"code": "...", "message": "...", "details": {...}}}
"""

from django.core.exceptions import PermissionDenied
from django.http import Http404
from rest_framework import exceptions, status
from rest_framework.views import exception_handler


class ApiError(exceptions.APIException):
    """Raise from views/services to return a specific error code."""

    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "BAD_REQUEST"
    default_detail = "잘못된 요청입니다."

    def __init__(self, code=None, message=None, status_code=None, details=None):
        if status_code is not None:
            self.status_code = status_code
        self.error_code = code or self.default_code
        self.details = details
        super().__init__(detail=message or self.default_detail, code=self.error_code)


# Default (code, message) per DRF exception type. Order matters: subclasses first.
_DEFAULTS = [
    (exceptions.ValidationError, "VALIDATION_ERROR", "입력값을 확인해 주세요."),
    (exceptions.NotAuthenticated, "NOT_AUTHENTICATED", "로그인이 필요합니다."),
    (exceptions.AuthenticationFailed, "NOT_AUTHENTICATED", "인증 정보가 올바르지 않습니다."),
    (exceptions.PermissionDenied, "PERMISSION_DENIED", "권한이 없습니다."),
    (exceptions.NotFound, "NOT_FOUND", "요청한 항목을 찾을 수 없습니다."),
    (exceptions.Throttled, "RATE_LIMITED", "요청이 너무 많습니다. 잠시 후 다시 시도해 주세요."),
    (exceptions.MethodNotAllowed, "METHOD_NOT_ALLOWED", "허용되지 않은 요청 방식입니다."),
    (exceptions.ParseError, "VALIDATION_ERROR", "요청 형식이 올바르지 않습니다."),
    (exceptions.UnsupportedMediaType, "VALIDATION_ERROR", "지원하지 않는 요청 형식입니다."),
]


def _flatten_codes(codes):
    if isinstance(codes, dict):
        return [c for value in codes.values() for c in _flatten_codes(value)]
    if isinstance(codes, list):
        return [c for value in codes for c in _flatten_codes(value)]
    return [codes]


def _only_unique_errors(exc):
    codes = _flatten_codes(exc.get_codes())
    return bool(codes) and all(code == "unique" for code in codes)


def _error_body(code, message, details=None):
    error = {"code": code, "message": message}
    if details:
        error["details"] = details
    return {"error": error}


def api_exception_handler(exc, context):
    if isinstance(exc, Http404):
        exc = exceptions.NotFound()
    elif isinstance(exc, PermissionDenied):
        exc = exceptions.PermissionDenied()

    response = exception_handler(exc, context)
    if response is None:
        return None  # unhandled -> Django 500

    if isinstance(exc, ApiError):
        response.data = _error_body(exc.error_code, str(exc.detail), exc.details)
        return response

    code, message, details = "ERROR", "요청을 처리할 수 없습니다.", None
    for exc_type, default_code, default_message in _DEFAULTS:
        if isinstance(exc, exc_type):
            code, message = default_code, default_message
            break

    if isinstance(exc, exceptions.ValidationError):
        details = exc.detail if isinstance(exc.detail, dict) else {"non_field_errors": exc.detail}
        if _only_unique_errors(exc):
            # Duplicates are 409 CONFLICT, still with field details for forms (specs/04).
            code, message = "CONFLICT", "이미 등록된 항목입니다."
            response.status_code = status.HTTP_409_CONFLICT

    response.data = _error_body(code, message, details)
    return response
