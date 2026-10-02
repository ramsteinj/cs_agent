import pytest

from knowledge.models import Company, KnowledgeChunk, Product

from .factories import make_company, make_product

URL = "/api/admin/companies"

PAYLOAD = {
    "name": "오케이테크",
    "description": "클라우드 협업 도구를 만드는 회사입니다.",
    "website": "https://example.com",
    "phone": "02-123-4567",
    "email": "help@example.com",
    "address": "서울시 강남구",
    "business_hours": "평일 09:00-18:00",
    "extra_info": "환불은 7일 이내 가능합니다.",
}


def _company_chunks(company_id):
    return KnowledgeChunk.objects.filter(source_type="company", source_id=company_id)


@pytest.mark.django_db
class TestCompanyApi:
    def test_create_indexes_company(self, admin_client):
        response = admin_client.post(URL, PAYLOAD, format="json")

        assert response.status_code == 201
        body = response.json()
        assert body["name"] == "오케이테크"
        assert body["product_count"] == 0
        assert body["chunk_count"] >= 1
        chunks = _company_chunks(body["id"])
        assert chunks.count() == body["chunk_count"]
        assert chunks.first().content.startswith("[회사] 오케이테크")
        assert chunks.first().embedding_model == "fake"

    def test_missing_required_fields(self, admin_client):
        response = admin_client.post(URL, {"website": "https://x.com"}, format="json")

        assert response.status_code == 400
        error = response.json()["error"]
        assert error["code"] == "VALIDATION_ERROR"
        assert {"name", "description"} <= set(error["details"])

    def test_invalid_email_and_url(self, admin_client):
        payload = {**PAYLOAD, "email": "not-an-email", "website": "nope"}

        response = admin_client.post(URL, payload, format="json")

        assert response.status_code == 400
        assert {"email", "website"} <= set(response.json()["error"]["details"])

    def test_duplicate_name_is_conflict_with_field_detail(self, admin_client):
        make_company(name="오케이테크")

        response = admin_client.post(URL, PAYLOAD, format="json")

        assert response.status_code == 409
        error = response.json()["error"]
        assert error["code"] == "CONFLICT"
        assert error["details"]["name"] == ["이미 등록된 회사명입니다."]

    def test_update_reindexes_company_and_its_products(self, admin_client):
        company = make_company(name="옛이름")
        product = make_product(company)

        response = admin_client.put(
            f"{URL}/{company.pk}", {**PAYLOAD, "name": "새이름"}, format="json"
        )

        assert response.status_code == 200
        assert _company_chunks(company.pk).first().content.startswith("[회사] 새이름")
        product_chunk = KnowledgeChunk.objects.get(source_type="product", source_id=product.pk)
        assert "(새이름)" in product_chunk.content

    def test_partial_update(self, admin_client):
        company = make_company()

        response = admin_client.patch(
            f"{URL}/{company.pk}", {"extra_info": "새 환불 정책"}, format="json"
        )

        assert response.status_code == 200
        assert "새 환불 정책" in _company_chunks(company.pk).first().content

    def test_delete_cascades_products_and_chunks(self, admin_client):
        company = make_company()
        make_product(company)

        assert admin_client.delete(f"{URL}/{company.pk}").status_code == 204

        assert not Company.objects.exists()
        assert not Product.objects.exists()
        assert not KnowledgeChunk.objects.exists()

    def test_list_counts_search_and_pagination(self, admin_client):
        alpha = make_company(name="알파")
        make_product(alpha, name="p1")
        make_product(alpha, name="p2")
        make_company(name="베타")

        body = admin_client.get(URL).json()
        assert body["count"] == 2
        assert [r["name"] for r in body["results"]] == ["베타", "알파"]  # ordered by name
        alpha_row = body["results"][1]
        assert alpha_row["product_count"] == 2
        assert alpha_row["chunk_count"] == _company_chunks(alpha.pk).count()

        searched = admin_client.get(URL, {"search": "알"}).json()
        assert [r["name"] for r in searched["results"]] == ["알파"]

    def test_page_size_param(self, admin_client):
        for i in range(25):
            make_company(name=f"회사{i:02d}", index=False)

        assert len(admin_client.get(URL).json()["results"]) == 20
        assert len(admin_client.get(URL, {"page_size": 100}).json()["results"]) == 25

    def test_not_found(self, admin_client):
        response = admin_client.get(f"{URL}/9999")

        assert response.status_code == 404
        assert response.json()["error"]["code"] == "NOT_FOUND"
