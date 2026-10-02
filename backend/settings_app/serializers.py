from rest_framework import serializers

from .models import AVAILABLE_MODELS, EXTRA_INSTRUCTIONS_MAX_LENGTH, SystemSetting


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
