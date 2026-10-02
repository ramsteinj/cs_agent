"""Keep KnowledgeChunk in sync with Company / Product (specs/05-rag-pipeline.md §2.4).

Callers run these inside transaction.atomic() together with the model save, so an
embedding failure rolls back the whole change.
"""

import logging

from django.conf import settings
from django.db import connection, transaction
from rest_framework import status

from common.exceptions import ApiError

from . import embeddings
from .chunking import chunk_text, company_document, product_document
from .models import Company, KnowledgeChunk

logger = logging.getLogger(__name__)

REINDEX_LOCK_KEY = 0x6B6E6F77  # arbitrary app-wide advisory lock id ("know")


def _embedding_error():
    return ApiError(
        "EMBEDDING_ERROR",
        "임베딩 생성에 실패했습니다. 잠시 후 다시 시도해 주세요.",
        status.HTTP_503_SERVICE_UNAVAILABLE,
    )


def _make_chunks(source_type, source, company, product, header, body, searchable):
    texts = chunk_text(
        header, body, max_chars=settings.CHUNK_MAX_CHARS, overlap=settings.CHUNK_OVERLAP_CHARS
    )
    try:
        vectors = embeddings.embed_passages(texts)
        model_name = embeddings.model_name()
    except embeddings.EmbeddingError:
        logger.exception("Embedding failed for %s:%s", source_type, source.pk)
        raise _embedding_error() from None
    return [
        KnowledgeChunk(
            source_type=source_type,
            source_id=source.pk,
            company=company,
            product=product,
            chunk_index=index,
            content=text,
            embedding=vector,
            embedding_model=model_name,
            is_searchable=searchable,
        )
        for index, (text, vector) in enumerate(zip(texts, vectors, strict=True))
    ]


def _replace(source_type, source_id, chunks):
    KnowledgeChunk.objects.filter(source_type=source_type, source_id=source_id).delete()
    KnowledgeChunk.objects.bulk_create(chunks)
    return len(chunks)


def reindex_product(product):
    header, body = product_document(product)
    chunks = _make_chunks(
        KnowledgeChunk.SourceType.PRODUCT,
        product,
        product.company,
        product,
        header,
        body,
        searchable=product.is_active,
    )
    return _replace(KnowledgeChunk.SourceType.PRODUCT, product.pk, chunks)


def reindex_company(company, include_products=True):
    """Re-chunk a company. Product chunks embed the company name, so they follow too."""
    header, body = company_document(company)
    chunks = _make_chunks(
        KnowledgeChunk.SourceType.COMPANY, company, company, None, header, body, searchable=True
    )
    count = _replace(KnowledgeChunk.SourceType.COMPANY, company.pk, chunks)
    if include_products:
        for product in company.products.select_related("company"):
            count += reindex_product(product)
    return count


def reindex_all():
    """Rebuild every chunk (F-A8). Raises CONFLICT if another reindex is running."""
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_try_advisory_xact_lock(%s)", [REINDEX_LOCK_KEY])
            acquired = cursor.fetchone()[0]
        if not acquired:
            raise ApiError("CONFLICT", "재색인이 이미 진행 중입니다.", status.HTTP_409_CONFLICT)
        KnowledgeChunk.objects.all().delete()
        total = sum(reindex_company(company) for company in Company.objects.all())
    logger.info("Full reindex finished: %d chunks", total)
    return total
