import logging
from unittest import mock

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from knowledge.embeddings import EmbeddingError
from knowledge.models import KnowledgeChunk, ProductDocument
from knowledge.retrieval import search

from .factories import make_company, make_product
from .files import make_docx, make_pdf


def _url(product, document=None):
    base = f"/api/admin/products/{product.pk}/documents"
    return f"{base}/{document.pk}" if document else base


def _upload(client, product, name, data):
    return client.post(_url(product), {"file": SimpleUploadedFile(name, data)}, format="multipart")


@pytest.fixture
def product(db):
    return make_product(make_company(), name="오케이드라이브", description="")


@pytest.mark.django_db
class TestDocumentApi:
    def test_upload_docx_indexes_its_text(self, admin_client, product):
        data = make_docx(["대용량 요금제는 월 9,900원이며 2TB를 제공합니다."])

        response = _upload(admin_client, product, "요금제.docx", data)

        assert response.status_code == 201
        body = response.json()
        assert body["file_name"] == "요금제.docx"
        assert body["file_type"] == "docx"
        assert body["char_count"] == len("대용량 요금제는 월 9,900원이며 2TB를 제공합니다.")
        assert body["preview"].startswith("대용량 요금제")
        assert "text" not in body
        chunks = KnowledgeChunk.objects.filter(product=product).order_by("chunk_index")
        assert chunks[0].content.startswith("[제품] 오케이드라이브 (오케이테크)")
        doc_chunk = chunks.last()
        assert doc_chunk.content.startswith(
            "[제품] 오케이드라이브 (오케이테크) / 문서: 요금제.docx"
        )
        assert "월 9,900원" in doc_chunk.content
        assert [c.chunk_index for c in chunks] == list(range(chunks.count()))

    def test_product_document_count_and_list(self, admin_client, product):
        _upload(admin_client, product, "a.txt", "첫 문서".encode())
        _upload(admin_client, product, "b.pdf", make_pdf("second document"))

        listed = admin_client.get(_url(product)).json()
        detail = admin_client.get(f"/api/admin/products/{product.pk}").json()

        assert [d["file_name"] for d in listed] == ["a.txt", "b.pdf"]
        assert detail["document_count"] == 2

    def test_document_content_is_searchable(self, admin_client, product, settings):
        _upload(
            admin_client, product, "faq.txt", "환불은 결제 후 7일 이내 전액 가능합니다".encode()
        )

        results = search("환불 7일 이내 가능", max_distance=2.0)

        assert any("문서: faq.txt" in chunk.content for chunk in results)

    def test_delete_removes_document_chunks(self, admin_client, product):
        _upload(admin_client, product, "a.txt", "삭제될 문서 내용".encode())
        document = ProductDocument.objects.get()

        assert admin_client.delete(_url(product, document)).status_code == 204

        assert not ProductDocument.objects.exists()
        assert not KnowledgeChunk.objects.filter(content__contains="삭제될 문서").exists()

    def test_delete_other_products_document_is_404(self, admin_client, product):
        other = make_product(product.company, name="다른 제품")
        _upload(admin_client, other, "a.txt", b"x")
        document = ProductDocument.objects.get()

        assert admin_client.delete(_url(product, document)).status_code == 404

    def test_rejected_file_creates_nothing(self, admin_client, product):
        response = _upload(admin_client, product, "old.doc", b"data")

        assert response.status_code == 400
        assert response.json()["error"]["code"] == "UNSUPPORTED_FILE"
        assert not ProductDocument.objects.exists()

    def test_missing_file_field(self, admin_client, product):
        response = admin_client.post(_url(product), {}, format="multipart")

        assert response.status_code == 400
        assert "file" in response.json()["error"]["details"]

    def test_embedding_failure_rolls_back_the_document(self, admin_client, product):
        with mock.patch(
            "knowledge.indexing.embeddings.embed_passages", side_effect=EmbeddingError("x")
        ):
            response = _upload(admin_client, product, "a.txt", b"hello")

        assert response.status_code == 503
        assert not ProductDocument.objects.exists()

    def test_inactive_product_documents_are_not_searchable(self, admin_client, product):
        _upload(admin_client, product, "a.txt", "비공개 문서".encode())

        admin_client.patch(f"/api/admin/products/{product.pk}", {"is_active": False}, format="json")

        assert not KnowledgeChunk.objects.filter(product=product, is_searchable=True).exists()

    def test_company_rename_updates_document_headers(self, admin_client, product):
        _upload(admin_client, product, "a.txt", b"hello")

        admin_client.patch(
            f"/api/admin/companies/{product.company.pk}", {"name": "새회사"}, format="json"
        )

        doc_chunk = KnowledgeChunk.objects.get(content__contains="문서: a.txt")
        assert "(새회사) / 문서: a.txt" in doc_chunk.content

    def test_upload_and_delete_are_audited(self, admin_client, product, caplog):
        caplog.set_level(logging.INFO, logger="audit")

        _upload(admin_client, product, "a.txt", b"hello")
        document = ProductDocument.objects.get()
        admin_client.delete(_url(product, document))

        assert "event=product_document_uploaded user='manager'" in caplog.text
        assert "event=product_document_deleted user='manager'" in caplog.text

    def test_product_without_description_is_allowed(self, admin_client, product):
        response = admin_client.post(
            "/api/admin/products",
            {"company": product.company.pk, "name": "문서만 있는 제품"},
            format="json",
        )

        assert response.status_code == 201
