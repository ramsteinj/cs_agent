import anthropic
import httpx2

from common.anthropic_errors import describe_api_error

_REQUEST = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")


def _status_error(cls, status, error_type, request_id="req_011abc"):
    response = httpx2.Response(status, request=_REQUEST, headers={"request-id": request_id})
    body = {"type": "error", "error": {"type": error_type, "message": "secret detail"}}
    return cls("secret detail", response=response, body=body)


def test_status_error_has_status_type_and_request_id():
    exc = _status_error(anthropic.BadRequestError, 400, "invalid_request_error")

    assert describe_api_error(exc) == (
        "status=400 type=invalid_request_error request_id=req_011abc"
    )


def test_raw_message_is_not_included():
    exc = _status_error(anthropic.AuthenticationError, 401, "authentication_error")

    assert "secret detail" not in describe_api_error(exc)


def test_missing_type_and_request_id():
    response = httpx2.Response(502, request=_REQUEST)
    exc = anthropic.InternalServerError("bad gateway", response=response, body="<html>")

    assert describe_api_error(exc) == "status=502 type=unknown request_id=-"


def test_connection_error_has_no_response():
    exc = anthropic.APITimeoutError(request=_REQUEST)

    assert describe_api_error(exc) == "error=APITimeoutError"
