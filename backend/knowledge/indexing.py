"""Keep KnowledgeChunk in sync with Company / Product (specs/05-rag-pipeline.md §2.4).

Callers run these inside transaction.atomic() together with the model save, so an
embedding failure rolls back the whole change.
"""

import logging

from django.db import connection, transaction
from rest_framework import status

from common.exceptions import ApiError

from . import embeddings
from .chunking import chunk_text, company_document, document_header, product_document
from .models import Company, KnowledgeChunk

logger = logging.getLogger(__name__)

REINDEX_LOCK_KEY = 0x6B6E6F77  # arbitrary app-wide advisory lock id ("know")


def _embedding_error():
    return ApiError(
        "EMBEDDING_ERROR",
        "임베딩 생성에 실패했습니다. 잠시 후 다시 시도해 주세요.",
        status.HTTP_503_SERVICE_UNAVAILABLE,
    )


def _chunk_settings():
    from settings_app.models import SystemSetting

    setting = SystemSetting.load()
    return setting.chunk_max_chars, setting.chunk_overlap_chars


def _make_chunks(source_type, source, company, product, sections, searchable):
    """Chunk every (header, body, document) section, embed them in one batch, number them."""
    max_chars, overlap = _chunk_settings()
    pieces = [
        (text, document, index)  # index restarts per section
        for header, body, document in sections
        for index, text in enumerate(chunk_text(header, body, max_chars=max_chars, overlap=overlap))
    ]
    try:
        vectors = embeddings.embed_passages([text for text, _, _ in pieces])
        model_name = embeddings.model_name()
    except embeddings.EmbeddingError:  # ImproperlyConfigured (wrong dimension) propagates
        logger.exception("Embedding failed for %s:%s", source_type, source.pk)
        raise _embedding_error() from None
    return [
        KnowledgeChunk(
            source_type=source_type,
            source_id=source.pk,
            company=company,
            product=product,
            document=document,
            chunk_index=index,
            content=text,
            embedding=vector,
            embedding_model=model_name,
            is_searchable=searchable,
        )
        for (text, document, index), vector in zip(pieces, vectors, strict=True)
    ]


def _replace(source_type, source_id, chunks):
    KnowledgeChunk.objects.filter(source_type=source_type, source_id=source_id).delete()
    KnowledgeChunk.objects.bulk_create(chunks)
    return len(chunks)


def _product_chunks(product):
    return KnowledgeChunk.objects.filter(
        source_type=KnowledgeChunk.SourceType.PRODUCT, source_id=product.pk
    )


def _field_section(product):
    return (*product_document(product), None)


def _document_section(product, document):
    return (document_header(product, document), document.text, document)


def _create(product, sections):
    chunks = _make_chunks(
        KnowledgeChunk.SourceType.PRODUCT,
        product,
        product.company,
        product,
        sections,
        searchable=product.is_active,
    )
    KnowledgeChunk.objects.bulk_create(chunks)
    return len(chunks)


def reindex_product(product):
    """Rebuild every chunk of a product: fields first, then each document (specs/05 §2.1).

    Needed when something in the chunk headers changes (name, company, category).
    """
    _product_chunks(product).delete()
    sections = [_field_section(product)]
    sections += [_document_section(product, doc) for doc in product.documents.all()]
    return _create(product, sections)


def reindex_product_fields(product):
    """Re-embed only the product-field chunks (description, price, ...); documents untouched."""
    _product_chunks(product).filter(document__isnull=True).delete()
    return _create(product, [_field_section(product)])


def index_document(document):
    """(Re-)embed one document's chunks; the product's other chunks are untouched."""
    product = document.product
    _product_chunks(product).filter(document=document).delete()
    return _create(product, [_document_section(product, document)])


def set_product_searchable(product):
    """Activation change: no re-embedding needed."""
    return _product_chunks(product).update(is_searchable=product.is_active)


def reindex_company(company, include_products=True):
    """Re-chunk a company. Product chunks embed the company name, so they follow too."""
    chunks = _make_chunks(
        KnowledgeChunk.SourceType.COMPANY,
        company,
        company,
        None,
        [(*company_document(company), None)],
        searchable=True,
    )
    count = _replace(KnowledgeChunk.SourceType.COMPANY, company.pk, chunks)
    if include_products:
        for product in company.products.select_related("company").prefetch_related("documents"):
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
