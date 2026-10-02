from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from settings_app.models import SystemSetting


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
