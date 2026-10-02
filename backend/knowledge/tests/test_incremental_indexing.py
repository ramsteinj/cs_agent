"""Only changed parts are re-embedded (specs/05 §2.4): big documents take ~40s each."""

from unittest import mock

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from knowledge import embeddings, indexing
from knowledge.models import KnowledgeChunk, ProductDocument

from .factories import make_company, make_product

URL = "/api/admin/products"


@pytest.fixture
def product(db):
    return make_product(make_company(), name="SC95A", category="TV", description="설명")


@pytest.fixture
def embedded():
    """Record every text sent to the embedder."""
    texts = []
    real = embeddings.embed_passages

    def spy(batch, model_name=None):
        texts.extend(batch)
        return real(batch, model_name)

    with mock.patch.object(indexing.embeddings, "embed_passages", side_effect=spy):
        yield texts


def _upload(client, product, name, body, title=""):
    return client.post(
        f"{URL}/{product.pk}/documents",
        {"file": SimpleUploadedFile(name, body.encode()), "title": title},
        format="multipart",
    )


def _doc_chunk_ids(product):
    return set(
        KnowledgeChunk.objects.filter(product=product, document__isnull=False).values_list(
            "id", flat=True
        )
    )


@pytest.mark.django_db
class TestIncrementalIndexing:
    def test_upload_embeds_only_the_new_document(self, admin_client, product, embedded):
        _upload(admin_client, product, "manual.txt", "매뉴얼 내용")
        embedded.clear()

        _upload(admin_client, product, "guide.txt", "설치 가이드 내용", "빠른 설치 가이드")

        assert len(embedded) == 1 and "빠른 설치 가이드" in embedded[0]

    def test_delete_embeds_nothing(self, admin_client, product, embedded):
        _upload(admin_client, product, "manual.txt", "매뉴얼 내용")
        document = ProductDocument.objects.get()
        embedded.clear()

        admin_client.delete(f"{URL}/{product.pk}/documents/{document.pk}")

        assert embedded == []
        assert not KnowledgeChunk.objects.filter(content__contains="매뉴얼 내용").exists()

    def test_rename_embeds_only_that_document(self, admin_client, product, embedded):
        _upload(admin_client, product, "a.txt", "첫 문서")
        _upload(admin_client, product, "b.txt", "둘째 문서")
        first = ProductDocument.objects.get(file_name="a.txt")
        embedded.clear()

        admin_client.patch(
            f"{URL}/{product.pk}/documents/{first.pk}", {"title": "사용자 매뉴얼"}, format="json"
        )

        assert len(embedded) == 1 and "사용자 매뉴얼 (a.txt)" in embedded[0]

    def test_price_change_keeps_document_chunks(self, admin_client, product, embedded):
        _upload(admin_client, product, "manual.txt", "매뉴얼 내용")
        before = _doc_chunk_ids(product)
        embedded.clear()

        admin_client.patch(f"{URL}/{product.pk}", {"price": "월 7,000원"}, format="json")

        assert _doc_chunk_ids(product) == before
        assert len(embedded) == 1 and "월 7,000원" in embedded[0]

    def test_activation_change_embeds_nothing(self, admin_client, product, embedded):
        _upload(admin_client, product, "manual.txt", "매뉴얼 내용")
        embedded.clear()

        admin_client.patch(f"{URL}/{product.pk}", {"is_active": False}, format="json")

        assert embedded == []
        assert not KnowledgeChunk.objects.filter(product=product, is_searchable=True).exists()

    def test_name_change_rebuilds_everything(self, admin_client, product, embedded):
        _upload(admin_client, product, "manual.txt", "매뉴얼 내용")
        embedded.clear()

        admin_client.patch(f"{URL}/{product.pk}", {"name": "SC95A-2"}, format="json")

        assert len(embedded) == 2  # product fields + the document
        header = KnowledgeChunk.objects.get(product=product, document__isnull=False).content
        assert header.startswith("[제품] SC95A-2 ")

    def test_category_change_re_embeds_only_the_field_chunk(self, admin_client, product, embedded):
        _upload(admin_client, product, "manual.txt", "매뉴얼 내용")
        before = _doc_chunk_ids(product)
        embedded.clear()

        admin_client.patch(f"{URL}/{product.pk}", {"category": "모니터"}, format="json")

        assert len(embedded) == 1 and "카테고리: 모니터" in embedded[0]
        assert _doc_chunk_ids(product) == before

    def test_unchanged_save_embeds_nothing(self, admin_client, product, embedded):
        embedded.clear()

        admin_client.patch(f"{URL}/{product.pk}", {"description": "설명"}, format="json")

        assert embedded == []

    def test_large_document_chunks_are_numbered_per_section(self, admin_client, product):
        long_text = " ".join(f"{i}번째 문장은 설명입니다." for i in range(300))
        _upload(admin_client, product, "big.txt", long_text)

        indexes = list(
            KnowledgeChunk.objects.filter(product=product, document__isnull=False)
            .order_by("chunk_index")
            .values_list("chunk_index", flat=True)
        )
        assert indexes == list(range(len(indexes))) and len(indexes) > 5
