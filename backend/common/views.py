from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


@api_view(["GET"])
@permission_classes([AllowAny])
def health(request):
    return Response({"status": "ok"})


def _api_error(request, code, message, status_code):
    from django.http import JsonResponse

    from .exceptions import _error_body

    return JsonResponse(
        _error_body(code, message), status=status_code, json_dumps_params={"ensure_ascii": False}
    )


def not_found(request, exception=None):
    """handler404: common JSON format under /api/, Django's page elsewhere (DEBUG=False)."""
    if request.path.startswith("/api/"):
        return _api_error(request, "NOT_FOUND", "요청한 항목을 찾을 수 없습니다.", 404)
    from django.views.defaults import page_not_found

    return page_not_found(request, exception)


def server_error(request):
    """handler500: never leak a stack trace; JSON under /api/."""
    if request.path.startswith("/api/"):
        return _api_error(request, "SERVER_ERROR", "일시적인 오류가 발생했습니다.", 500)
    from django.views.defaults import server_error as default_server_error

    return default_server_error(request)
