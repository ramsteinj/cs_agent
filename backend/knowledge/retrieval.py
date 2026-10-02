"""Vector search over KnowledgeChunk (specs/05-rag-pipeline.md §3)."""

from django.conf import settings
from pgvector.django import CosineDistance

from . import embeddings
from .models import KnowledgeChunk


def search(query_text, top_k=None, max_distance=None):
    """Top-K searchable chunks by cosine distance, nearest first.

    Chunks farther than max_distance are dropped; each result has a .distance attribute.
    """
    top_k = settings.RAG_TOP_K if top_k is None else top_k
    max_distance = settings.RAG_MAX_DISTANCE if max_distance is None else max_distance
    if not query_text or not query_text.strip():
        return []

    query_vector = embeddings.embed_query(query_text)
    return list(
        KnowledgeChunk.objects.filter(is_searchable=True)
        .annotate(distance=CosineDistance("embedding", query_vector))
        .filter(distance__lte=max_distance)
        .order_by("distance")[:top_k]
    )
