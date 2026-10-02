"""RAG tuning settings update (specs/05 §1.1, specs/04 §6)."""

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from rest_framework import serializers, status

from common.audit import audit
from common.exceptions import ApiError
from knowledge import embeddings
from knowledge.indexing import reindex_all

from .models import REINDEX_FIELDS


def _validate_embedding_model(name):
    """Load the model now so a wrong name or dimension never reaches the index."""
    if settings.EMBEDDING_BACKEND == "fake":
        return
    try:
        embeddings.get_embedder(name).load()
    except ImproperlyConfigured:
        raise serializers.ValidationError(
            {
                "embedding_model": [
                    f"{settings.EMBEDDING_DIM}차원 임베딩을 만드는 모델만 사용할 수 있습니다."
                ]
            }
        ) from None
    except embeddings.EmbeddingError:
        raise ApiError(
            "EMBEDDING_ERROR",
            "임베딩 모델을 불러올 수 없습니다. 모델 이름을 확인해 주세요.",
            status.HTTP_503_SERVICE_UNAVAILABLE,
        ) from None


def update_rag_settings(serializer, user):
    """Save the settings; rebuild all chunks when chunking/embedding settings change.

    Everything runs in one transaction, so a failed reindex also undoes the change.
    Returns the number of chunks when a reindex ran, else None.
    """
    setting = serializer.instance
    data = serializer.validated_data
    changed = sorted(field for field in data if data[field] != getattr(setting, field))
    needs_reindex = any(field in REINDEX_FIELDS for field in changed)

    with transaction.atomic():
        serializer.save()
        if "embedding_model" in changed:
            _validate_embedding_model(data["embedding_model"])
        reindexed = reindex_all() if needs_reindex else None

    if changed:
        audit("rag_settings_updated", user, fields=",".join(changed), reindexed=reindexed)
    return reindexed
