import logging

from django.db import models
from django.utils import timezone

import llm
from common.models import TimeStampedModel

from . import crypto

logger = logging.getLogger(__name__)

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


class SystemSetting(TimeStampedModel):
    """Global settings, always a single row with pk=1 (specs/03-data-model.md §5)."""

    SINGLETON_PK = 1

    llm_provider = models.CharField(
        max_length=20, choices=llm.PROVIDER_CHOICES, default=llm.DEFAULT_PROVIDER
    )
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

    @property
    def active_provider_config(self):
        return LLMProviderConfig.get(self.llm_provider)

    @property
    def chatbot_enabled(self) -> bool:
        """The selected provider has both an API Key and a model."""
        return self.active_provider_config.ready


class LLMProviderConfig(TimeStampedModel):
    """API Key (encrypted) and model per LLM provider (specs/03-data-model.md §5)."""

    provider = models.CharField(max_length=20, choices=llm.PROVIDER_CHOICES, unique=True)
    api_key_encrypted = models.TextField(blank=True, default="")
    api_key_hint = models.CharField(max_length=32, blank=True, default="")
    api_key_updated_at = models.DateTimeField(null=True, blank=True)
    model = models.CharField(max_length=100, blank=True, default="")
    temperature = models.FloatField(null=True, blank=True)  # None = model default

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.provider

    @classmethod
    def get(cls, provider):
        config, _ = cls.objects.get_or_create(
            provider=provider, defaults={"model": llm.get_provider(provider).default_model}
        )
        return config

    @classmethod
    def all_providers(cls):
        """One config per provider, in PROVIDERS order."""
        return [cls.get(name) for name in llm.PROVIDERS]

    @property
    def spec(self):
        return llm.get_provider(self.provider)

    def set_api_key(self, plain_key: str):
        self.api_key_encrypted = crypto.encrypt(plain_key)
        self.api_key_hint = self.spec.mask_key(plain_key)
        self.api_key_updated_at = timezone.now()
        self.save()

    def get_api_key(self) -> str | None:
        if not self.api_key_encrypted:
            return None
        try:
            return crypto.decrypt(self.api_key_encrypted)
        except crypto.InvalidToken:
            # FIELD_ENCRYPTION_KEY changed: treat as not configured, admin must re-enter it.
            logger.warning(
                "Stored %s API Key cannot be decrypted (encryption key changed?)", self.provider
            )
            return None

    def clear_api_key(self):
        self.api_key_encrypted = ""
        self.api_key_hint = ""
        self.api_key_updated_at = None
        self.save()

    @property
    def api_key_configured(self) -> bool:
        return self.get_api_key() is not None

    @property
    def temperature_supported(self) -> bool:
        return self.spec.supports_temperature(self.model)

    @property
    def ready(self) -> bool:
        return bool(self.model) and self.api_key_configured
