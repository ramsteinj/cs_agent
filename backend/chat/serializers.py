from django.conf import settings
from rest_framework import serializers


class SendMessageSerializer(serializers.Serializer):
    session_id = serializers.UUIDField()
    message = serializers.CharField(
        max_length=settings.CHAT_MESSAGE_MAX_LENGTH, trim_whitespace=True
    )
