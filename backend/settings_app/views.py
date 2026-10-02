from django.http import Http404
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

import llm
from common.audit import audit

from . import rag, services
from .models import LLMProviderConfig, SystemSetting
from .serializers import (
    ApiKeySerializer,
    ProviderModelSerializer,
    ProviderSerializer,
    RagSettingsSerializer,
    SystemSettingSerializer,
)


def _config(provider):
    if provider not in llm.PROVIDERS:
        raise Http404
    return LLMProviderConfig.get(provider)


def _settings_response():
    return Response(SystemSettingSerializer(SystemSetting.load()).data)


@api_view(["GET", "PATCH"])
def system_settings(request):
    setting = SystemSetting.load()
    if request.method == "PATCH":
        serializer = SystemSettingSerializer(setting, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        audit("settings_updated", request.user, fields=",".join(sorted(serializer.validated_data)))
    return _settings_response()


@api_view(["PUT", "DELETE"])
def provider_api_key(request, provider):
    config = _config(provider)
    if request.method == "DELETE":
        config.clear_api_key()
        audit("api_key_deleted", request.user, provider=provider)
        return Response(status=status.HTTP_204_NO_CONTENT)

    serializer = ApiKeySerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    key = serializer.validated_data["api_key"]
    services.validate_api_key(provider, key)
    config.set_api_key(key)
    audit("api_key_updated", request.user, provider=provider)
    return _settings_response()


@api_view(["PATCH"])
def provider_config(request, provider):
    config = _config(provider)
    serializer = ProviderModelSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    config.model = serializer.validated_data["model"]
    config.save(update_fields=["model", "updated_at"])
    audit("llm_model_updated", request.user, provider=provider, model=config.model)
    return Response(ProviderSerializer(config).data)


@api_view(["GET"])
def provider_models(request, provider):
    config = _config(provider)
    return Response(
        {"models": services.list_models(config), "default_model": config.spec.default_model}
    )


@api_view(["GET", "PATCH"])
def rag_settings(request):
    setting = SystemSetting.load()
    reindexed = None
    if request.method == "PATCH":
        serializer = RagSettingsSerializer(setting, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        reindexed = rag.update_rag_settings(serializer, request.user)
        setting.refresh_from_db()
    return Response({**RagSettingsSerializer(setting).data, "reindexed_chunks": reindexed})
