from unittest import mock

import pytest

from knowledge.embeddings import EmbeddingError
from knowledge.models import KnowledgeChunk, Product

from .factories import make_company, make_product

URL = "/api/admin/products"


def _chunks(product_id):
    return KnowledgeChunk.objects.filter(source_type="product", source_id=product_id)


def _payload(company, **overrides):
    data = {
        "company": company.pk,
        "name": "오케이드라이브",
        "category": "문서 관리",
        "summary": "클라우드 드라이브",
        "description": "팀 문서를 안전하게 저장합니다.",
        "price": "월 5,000원",
        "features": "버전 기록",
        "usage_guide": "",
        "faq": "",
        "is_active": True,
    }
    data.update(overrides)
    return data


@pytest.mark.django_db
class TestProductApi:
    def test_create_indexes_product(self, admin_client):
        company = make_company()

        response = admin_client.post(URL, _payload(company), format="json")

        assert response.status_code == 201
        body = response.json()
        assert body["company_name"] == company.name
        assert body["chunk_count"] == _chunks(body["id"]).count() >= 1
        chunk = _chunks(body["id"]).first()
        assert chunk.content.startswith("[제품] 오케이드라이브 (오케이테크) / 카테고리: 문서 관리")
        assert "가격: 월 5,000원" in chunk.content
        assert chunk.company_id == company.pk
        assert chunk.is_searchable is True

    def test_required_fields(self, admin_client):
        response = admin_client.post(URL, {}, format="json")

        assert response.status_code == 400
        assert {"company", "name"} <= set(response.json()["error"]["details"])

    def test_update_rebuilds_chunks(self, admin_client):
        product = make_product(make_company())
        old_ids = set(_chunks(product.pk).values_list("id", flat=True))

        response = admin_client.patch(f"{URL}/{product.pk}", {"price": "월 7,000원"}, format="json")

        assert response.status_code == 200
        assert set(_chunks(product.pk).values_list("id", flat=True)).isdisjoint(old_ids)
        assert "월 7,000원" in _chunks(product.pk).first().content

    def test_deactivate_makes_chunks_unsearchable(self, admin_client):
        product = make_product(make_company())

        admin_client.patch(f"{URL}/{product.pk}", {"is_active": False}, format="json")

        assert not _chunks(product.pk).filter(is_searchable=True).exists()

    def test_delete_removes_chunks(self, admin_client):
        product = make_product(make_company())

        assert admin_client.delete(f"{URL}/{product.pk}").status_code == 204
        assert not _chunks(product.pk).exists()

    def test_same_name_and_category_is_conflict(self, admin_client):
        company = make_company()
        make_product(company, name="오케이드라이브", category="문서 관리")

        response = admin_client.post(URL, _payload(company), format="json")

        assert response.status_code == 409
        assert "카테고리" in response.json()["error"]["details"]["name"][0]

    def test_same_name_with_another_category_is_allowed(self, admin_client):
        company = make_company()
        make_product(company, name="SC95A", category="Quick Install Guide")

        response = admin_client.post(
            URL, _payload(company, name="SC95A", category="E-Manual"), format="json"
        )

        assert response.status_code == 201

    def test_changing_category_into_a_duplicate_is_rejected(self, admin_client):
        company = make_company()
        make_product(company, name="SC95A", category="TV")
        other = make_product(company, name="SC95A", category="모니터")

        response = admin_client.patch(f"{URL}/{other.pk}", {"category": "TV"}, format="json")

        assert response.status_code == 409

    def test_same_name_in_another_company_is_allowed(self, admin_client):
        make_product(make_company(name="A"), name="오케이드라이브")

        response = admin_client.post(URL, _payload(make_company(name="B")), format="json")

        assert response.status_code == 201

    def test_renaming_to_own_name_is_not_a_duplicate(self, admin_client):
        product = make_product(make_company())

        response = admin_client.put(
            f"{URL}/{product.pk}", _payload(product.company, name=product.name), format="json"
        )

        assert response.status_code == 200

    def test_embedding_failure_rolls_back(self, admin_client):
        company = make_company()
        with mock.patch(
            "knowledge.indexing.embeddings.embed_passages", side_effect=EmbeddingError("x")
        ):
            response = admin_client.post(URL, _payload(company), format="json")

        assert response.status_code == 503
        assert response.json()["error"]["code"] == "EMBEDDING_ERROR"
        assert not Product.objects.exists()

    def test_filters_and_search(self, admin_client):
        a = make_company(name="A")
        b = make_company(name="B")
        make_product(a, name="드라이브", category="문서")
        make_product(a, name="캘린더", category="일정", is_active=False)
        make_product(b, name="미팅", category="회의")

        def names(**params):
            return sorted(r["name"] for r in admin_client.get(URL, params).json()["results"])

        assert names() == ["드라이브", "미팅", "캘린더"]
        assert names(company=a.pk) == ["드라이브", "캘린더"]
        assert names(category="일정") == ["캘린더"]
        assert names(is_active="false") == ["캘린더"]
        assert names(is_active="true") == ["드라이브", "미팅"]
        assert names(search="미") == ["미팅"]

    def test_categories(self, admin_client):
        company = make_company()
        make_product(company, name="a", category="문서", index=False)
        make_product(company, name="b", category="문서", index=False)
        make_product(company, name="c", category="", index=False)
        make_product(company, name="d", category="일정", index=False)

        assert admin_client.get(f"{URL}/categories").json() == ["문서", "일정"]
