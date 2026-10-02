import logging

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from . import services
from .models import SystemSetting
from .serializers import ApiKeySerializer, SystemSettingSerializer

logger = logging.getLogger(__name__)


@api_view(["GET", "PATCH"])
def system_settings(request):
    setting = SystemSetting.load()
    if request.method == "PATCH":
        serializer = SystemSettingSerializer(setting, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
    return Response(SystemSettingSerializer(setting).data)


@api_view(["PUT", "DELETE"])
def api_key(request):
    setting = SystemSetting.load()
    if request.method == "DELETE":
        setting.clear_api_key()
        logger.info("Anthropic API Key deleted by %s", request.user.username)
        return Response(status=status.HTTP_204_NO_CONTENT)

    serializer = ApiKeySerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    key = serializer.validated_data["api_key"]
    services.validate_api_key(key)
    setting.set_api_key(key)
    logger.info("Anthropic API Key updated by %s", request.user.username)
    return Response(SystemSettingSerializer(setting).data)
