from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from common.audit import audit

from . import services
from .models import SystemSetting
from .serializers import ApiKeySerializer, SystemSettingSerializer


@api_view(["GET", "PATCH"])
def system_settings(request):
    setting = SystemSetting.load()
    if request.method == "PATCH":
        serializer = SystemSettingSerializer(setting, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        audit("settings_updated", request.user, fields=",".join(sorted(serializer.validated_data)))
    return Response(SystemSettingSerializer(setting).data)


@api_view(["PUT", "DELETE"])
def api_key(request):
    setting = SystemSetting.load()
    if request.method == "DELETE":
        setting.clear_api_key()
        audit("api_key_deleted", request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)

    serializer = ApiKeySerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    key = serializer.validated_data["api_key"]
    services.validate_api_key(key)
    setting.set_api_key(key)
    audit("api_key_updated", request.user)
    return Response(SystemSettingSerializer(setting).data)
