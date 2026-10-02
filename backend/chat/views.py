import json
import logging

from django.http import StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from rest_framework import status as http
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from common.exceptions import error_json
from settings_app.models import SystemSetting

from . import services
from .models import ChatSession
from .serializers import SendMessageSerializer

logger = logging.getLogger(__name__)

DISABLED_MESSAGE = "현재 상담 서비스를 준비 중입니다."


@api_view(["GET"])
@permission_classes([AllowAny])
def status(request):
    """Public chatbot state. Always 200; enabled=false when no API Key (specs/01 F-U2)."""
    setting = SystemSetting.load()
    return Response(
        {
            "enabled": setting.chatbot_enabled,
            "bot_name": setting.bot_name,
            "welcome_message": setting.welcome_message,
        }
    )


@api_view(["POST"])
@permission_classes([AllowAny])
def create_session(request):
    session = services.create_session(services.client_ip(request))
    return Response({"session_id": str(session.id)}, status=http.HTTP_201_CREATED)


@api_view(["GET"])
@permission_classes([AllowAny])
def session_messages(request, session_id):
    session = ChatSession.objects.filter(pk=session_id).first()
    if session is None:
        raise NotFound()
    return Response(services.public_messages(session))


def _sse(event):
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


@csrf_exempt  # no cookie auth on this public endpoint
@require_POST
def send_message(request):
    """POST /api/chat/messages -> text/event-stream (specs/04 §7).

    Errors detected before streaming starts use the common JSON error format.
    """
    try:
        payload = json.loads(request.body or b"{}")
    except (ValueError, UnicodeDecodeError):
        return error_json("VALIDATION_ERROR", "요청 형식이 올바르지 않습니다.", 400)
    serializer = SendMessageSerializer(data=payload if isinstance(payload, dict) else {})
    if not serializer.is_valid():
        return error_json("VALIDATION_ERROR", "입력값을 확인해 주세요.", 400, serializer.errors)

    if not SystemSetting.load().chatbot_enabled:
        return error_json("CHATBOT_DISABLED", DISABLED_MESSAGE, 503)

    session = ChatSession.objects.filter(pk=serializer.validated_data["session_id"]).first()
    if session is None:
        return error_json("NOT_FOUND", "대화 세션을 찾을 수 없습니다.", 404)

    if services.ip_rate_limited(services.client_ip(request)):
        return error_json("RATE_LIMITED", "요청이 너무 많습니다. 잠시 후 다시 시도해 주세요.", 429)
    if services.session_full(session):
        return error_json(
            "RATE_LIMITED", "이 대화의 최대 메시지 수에 도달했습니다. 새 대화를 시작해 주세요.", 429
        )

    events = services.answer_stream(session, serializer.validated_data["message"])
    response = StreamingHttpResponse(
        (_sse(event) for event in events), content_type="text/event-stream; charset=utf-8"
    )
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response
