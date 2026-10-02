import logging

from django.db import models
from django.utils import timezone

from common.models import TimeStampedModel

from . import crypto

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-opus-5-5"
AVAILABLE_MODELS = ["claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-4-5"]
DEFAULT_BOT_NAME = "고객지원 챗봇"
DEFAULT_WELCOME_MESSAGE = "안녕하세요! 회사와 제품에 대해 궁금한 점을 물어보세요."
EXTRA_INSTRUCTIONS_MAX_LENGTH = 2000
DEFAULT_EMBEDDING_MODEL = "intfloat/multilingual-e5-small"

# RAG tuning ranges (specs/05 §1.1): field -> (min, max)
RAG_LIMITS = {
    "chunk_max_chars": (100, 4000),
    "chunk_overlap_chars": (0, 3999),
    "retrieval_top_k": (1, 20),
    "retrieval_max_distance": (0.0, 2.0),
    "history_messages": (0, 50),
    "max_sources": (0, 10),
    "llm_max_output_tokens": (256, 32000),
}
# Changing these rebuilds every chunk.
REINDEX_FIELDS = ("embedding_model", "chunk_max_chars", "chunk_overlap_chars")
API_KEY_MASK_PREFIX = "sk-ant-"


class SystemSetting(TimeStampedModel):
    """Global settings, always a single row with pk=1 (specs/03-data-model.md §5)."""

    SINGLETON_PK = 1

    anthropic_api_key_encrypted = models.TextField(blank=True, default="")
    api_key_last4 = models.CharField(max_length=4, blank=True, default="")
    api_key_updated_at = models.DateTimeField(null=True, blank=True)
    claude_model = models.CharField(max_length=100, default=DEFAULT_MODEL)
    bot_name = models.CharField(max_length=100, default=DEFAULT_BOT_NAME)
    welcome_message = models.TextField(default=DEFAULT_WELCOME_MESSAGE)
    extra_instructions = models.TextField(
        blank=True, default="", max_length=EXTRA_INSTRUCTIONS_MAX_LENGTH
    )

    # --- RAG tuning (specs/05 §1.1) ---
    embedding_model = models.CharField(max_length=200, default=DEFAULT_EMBEDDING_MODEL)
    chunk_max_chars = models.PositiveIntegerField(default=500)
    chunk_overlap_chars = models.PositiveIntegerField(default=100)
    retrieval_top_k = models.PositiveIntegerField(default=5)
    retrieval_max_distance = models.FloatField(default=0.6)
    search_with_previous_question = models.BooleanField(default=True)
    history_messages = models.PositiveIntegerField(default=10)
    max_sources = models.PositiveIntegerField(default=3)
    llm_max_output_tokens = models.PositiveIntegerField(default=4096)

    class Meta:
        verbose_name = "system setting"

    def __str__(self):
        return "SystemSetting"

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=cls.SINGLETON_PK)
        return obj

    def save(self, *args, **kwargs):
        self.pk = self.SINGLETON_PK
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise NotImplementedError("SystemSetting cannot be deleted.")

    # --- API Key -----------------------------------------------------------

    def set_api_key(self, plain_key: str):
        self.anthropic_api_key_encrypted = crypto.encrypt(plain_key)
        self.api_key_last4 = plain_key[-4:]
        self.api_key_updated_at = timezone.now()
        self.save()

    def get_api_key(self) -> str | None:
        if not self.anthropic_api_key_encrypted:
            return None
        try:
            return crypto.decrypt(self.anthropic_api_key_encrypted)
        except crypto.InvalidToken:
            # FIELD_ENCRYPTION_KEY changed: treat as not configured, admin must re-enter it.
            logger.warning("Stored API Key cannot be decrypted (encryption key changed?)")
            return None

    def clear_api_key(self):
        self.anthropic_api_key_encrypted = ""
        self.api_key_last4 = ""
        self.api_key_updated_at = None
        self.save()

    @property
    def api_key_masked(self) -> str:
        if not self.anthropic_api_key_encrypted:
            return ""
        return f"{API_KEY_MASK_PREFIX}...{self.api_key_last4}"

    @property
    def chatbot_enabled(self) -> bool:
        return self.get_api_key() is not None
