import uuid

from django.db import models
from django.utils import timezone

from common.models import TimeStampedModel


class ChatSession(TimeStampedModel):
    """Anonymous chat session; the frontend keeps the id in sessionStorage."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    client_ip_hash = models.CharField(max_length=64, blank=True)  # never the raw IP
    last_activity_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return str(self.id)


class ChatMessage(TimeStampedModel):
    class Role(models.TextChoices):
        USER = "user", "user"
        ASSISTANT = "assistant", "assistant"

    class Status(models.TextChoices):
        OK = "ok", "ok"
        ERROR = "error", "error"

    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=10, choices=Role.choices)
    content = models.TextField(blank=True)
    retrieved_chunk_ids = models.JSONField(default=list, blank=True)
    model = models.CharField(max_length=100, blank=True)
    input_tokens = models.PositiveIntegerField(null=True, blank=True)
    output_tokens = models.PositiveIntegerField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OK)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self):
        return f"{self.role}: {self.content[:30]}"
