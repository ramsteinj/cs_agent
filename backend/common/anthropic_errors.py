import anthropic


def describe_api_error(exc):
    """Loggable summary of an Anthropic SDK error: status, error type and request ID.

    The error type (e.g. invalid_request_error, authentication_error, rate_limit_error) and
    the request ID let operators diagnose failures or contact Anthropic support. The raw
    error message is left out on purpose so nothing user- or key-related ends up in logs.
    """
    if isinstance(exc, anthropic.APIStatusError):
        return (
            f"status={exc.status_code} type={exc.type or 'unknown'} "
            f"request_id={exc.request_id or '-'}"
        )
    return f"error={type(exc).__name__}"  # connection errors / timeouts: no response
