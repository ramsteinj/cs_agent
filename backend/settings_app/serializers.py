import re

from django.conf import settings
from rest_framework import serializers

import llm
from chat.prompts import DEFAULT_SYSTEM_PROMPT

from .models import (
    EXTRA_INSTRUCTIONS_MAX_LENGTH,
    RAG_LIMITS,
    SYSTEM_PROMPT_MAX_LENGTH,
    LLMProviderConfig,
    SystemSetting,
)


class ProviderSerializer(serializers.ModelSerializer):
    """Per-provider state. Never exposes the API Key itself."""

    label = serializers.SerializerMethodField()
    api_key_configured = serializers.SerializerMethodField()
    api_key_masked = serializers.SerializerMethodField()
    default_model = serializers.SerializerMethodField()
    temperature_supported = serializers.SerializerMethodField()
    temperature_range = serializers.SerializerMethodField()

    class Meta:
        model = LLMProviderConfig
        fields = [
            "provider",
            "label",
            "api_key_configured",
            "api_key_masked",
            "api_key_updated_at",
            "model",
            "default_model",
            "temperature",
            "temperature_supported",
            "temperature_range",
        ]

    def get_label(self, obj):
        return obj.spec.label

    def get_api_key_configured(self, obj):
        return obj.api_key_configured

    def get_api_key_masked(self, obj):
        return obj.api_key_hint if obj.api_key_configured else ""

    def get_default_model(self, obj):
        return obj.spec.default_model

    def get_temperature_supported(self, obj):
        return obj.temperature_supported

    def get_temperature_range(self, obj):
        return list(obj.spec.temperature_range)


class SystemSettingSerializer(serializers.ModelSerializer):
    llm_provider = serializers.ChoiceField(choices=llm.PROVIDER_CHOICES, required=False)
    chatbot_enabled = serializers.SerializerMethodField()
    providers = serializers.SerializerMethodField()
    bot_name = serializers.CharField(max_length=100, required=False)
    welcome_message = serializers.CharField(max_length=1000, required=False)
    system_prompt = serializers.CharField(
        max_length=SYSTEM_PROMPT_MAX_LENGTH, required=False, trim_whitespace=False
    )
    default_system_prompt = serializers.SerializerMethodField()
    extra_instructions = serializers.CharField(
        max_length=EXTRA_INSTRUCTIONS_MAX_LENGTH, allow_blank=True, required=False
    )

    class Meta:
        model = SystemSetting
        fields = [
            "llm_provider",
            "chatbot_enabled",
            "providers",
            "bot_name",
            "welcome_message",
            "system_prompt",
            "default_system_prompt",
            "extra_instructions",
        ]

    def get_default_system_prompt(self, obj):
        return DEFAULT_SYSTEM_PROMPT

    def validate_system_prompt(self, value):
        if not value.strip():
            raise serializers.ValidationError("시스템 프롬프트를 입력해 주세요.")
        return value.strip()

    def get_chatbot_enabled(self, obj):
        return obj.chatbot_enabled

    def get_providers(self, obj):
        return ProviderSerializer(LLMProviderConfig.all_providers(), many=True).data


class ApiKeySerializer(serializers.Serializer):
    api_key = serializers.CharField(max_length=500, trim_whitespace=True)

    def validate_api_key(self, value):
        if len(value) < 8 or any(ch.isspace() for ch in value):
            raise serializers.ValidationError("API Key 형식이 올바르지 않습니다.")
        return value


class ProviderConfigSerializer(serializers.Serializer):
    """PATCH model and/or temperature (None = model default)."""

    model = serializers.CharField(max_length=100, required=False)
    temperature = serializers.FloatField(required=False, allow_null=True)

    def validate_model(self, value):
        value = value.strip()
        if not re.fullmatch(r"[A-Za-z0-9._:/-]+", value):
            raise serializers.ValidationError("모델 이름 형식이 올바르지 않습니다.")
        return value

    def validate(self, attrs):
        config = self.context["config"]
        temperature = attrs.get("temperature")
        if temperature is None:
            return attrs
        model = attrs.get("model", config.model)
        spec = config.spec
        if not spec.supports_temperature(model):
            raise serializers.ValidationError(
                {
                    "temperature": [
                        f"선택한 모델({model or '미선택'})은 temperature 설정을 지원하지 않습니다."
                    ]
                }
            )
        low, high = spec.temperature_range
        if not low <= temperature <= high:
            raise serializers.ValidationError(
                {"temperature": [f"{low:g}~{high:g} 사이의 값을 입력해 주세요."]}
            )
        return attrs


def _int_field(name):
    low, high = RAG_LIMITS[name]
    return serializers.IntegerField(min_value=low, max_value=high, required=False)


class RagSettingsSerializer(serializers.ModelSerializer):
    """RAG tuning values with the ranges from specs/05 §1.1."""

    embedding_model = serializers.CharField(max_length=200, required=False)
    embedding_dim = serializers.SerializerMethodField()
    chunk_max_chars = _int_field("chunk_max_chars")
    chunk_overlap_chars = _int_field("chunk_overlap_chars")
    retrieval_top_k = _int_field("retrieval_top_k")
    retrieval_max_distance = serializers.FloatField(
        min_value=RAG_LIMITS["retrieval_max_distance"][0],
        max_value=RAG_LIMITS["retrieval_max_distance"][1],
        required=False,
    )
    history_messages = _int_field("history_messages")
    max_sources = _int_field("max_sources")
    llm_max_output_tokens = _int_field("llm_max_output_tokens")

    class Meta:
        model = SystemSetting
        fields = [
            "embedding_model",
            "embedding_dim",
            "chunk_max_chars",
            "chunk_overlap_chars",
            "retrieval_top_k",
            "retrieval_max_distance",
            "search_with_previous_question",
            "history_messages",
            "max_sources",
            "llm_max_output_tokens",
        ]

    def get_embedding_dim(self, obj):
        return settings.EMBEDDING_DIM

    def validate_embedding_model(self, value):
        value = value.strip()
        if not re.fullmatch(r"[A-Za-z0-9._/-]+", value):
            raise serializers.ValidationError(
                "모델 이름 형식이 올바르지 않습니다. (예: intfloat/multilingual-e5-small)"
            )
        return value

    def validate(self, attrs):
        max_chars = attrs.get("chunk_max_chars", self.instance.chunk_max_chars)
        overlap = attrs.get("chunk_overlap_chars", self.instance.chunk_overlap_chars)
        if overlap >= max_chars:
            raise serializers.ValidationError(
                {"chunk_overlap_chars": ["청크 겹침은 청크 최대 길이보다 작아야 합니다."]}
            )
        return attrs
