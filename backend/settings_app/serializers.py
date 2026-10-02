import re

from django.conf import settings
from rest_framework import serializers

from .models import AVAILABLE_MODELS, EXTRA_INSTRUCTIONS_MAX_LENGTH, RAG_LIMITS, SystemSetting


class SystemSettingSerializer(serializers.ModelSerializer):
    """Never exposes the API Key itself, only whether it is set and a masked hint."""

    api_key_configured = serializers.SerializerMethodField()
    api_key_masked = serializers.CharField(read_only=True)
    available_models = serializers.SerializerMethodField()
    claude_model = serializers.ChoiceField(choices=AVAILABLE_MODELS)
    bot_name = serializers.CharField(max_length=100)
    welcome_message = serializers.CharField(max_length=1000)
    extra_instructions = serializers.CharField(
        max_length=EXTRA_INSTRUCTIONS_MAX_LENGTH, allow_blank=True, required=False
    )

    class Meta:
        model = SystemSetting
        fields = [
            "api_key_configured",
            "api_key_masked",
            "api_key_updated_at",
            "claude_model",
            "available_models",
            "bot_name",
            "welcome_message",
            "extra_instructions",
        ]
        read_only_fields = ["api_key_updated_at"]

    def get_api_key_configured(self, obj):
        return obj.chatbot_enabled

    def get_available_models(self, obj):
        return AVAILABLE_MODELS


class ApiKeySerializer(serializers.Serializer):
    api_key = serializers.CharField(max_length=500, trim_whitespace=True)

    def validate_api_key(self, value):
        if len(value) < 8 or any(ch.isspace() for ch in value):
            raise serializers.ValidationError("API Key 형식이 올바르지 않습니다.")
        return value


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
