import pytest
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

# Every admin-only endpoint that exists so far. Extend as phases add /api/admin/* routes.
ADMIN_ENDPOINTS = [
    ("get", "/api/auth/me"),
    ("post", "/api/auth/logout"),
    ("post", "/api/auth/change-password"),
    ("get", "/api/admin/settings"),
    ("patch", "/api/admin/settings"),
    ("put", "/api/admin/settings/providers/anthropic/api-key"),
    ("delete", "/api/admin/settings/providers/openai/api-key"),
    ("patch", "/api/admin/settings/providers/gemini"),
    ("get", "/api/admin/settings/providers/anthropic/models"),
    ("get", "/api/admin/settings/rag"),
    ("patch", "/api/admin/settings/rag"),
    ("get", "/api/admin/companies"),
    ("post", "/api/admin/companies"),
    ("get", "/api/admin/companies/1"),
    ("put", "/api/admin/companies/1"),
    ("delete", "/api/admin/companies/1"),
    ("get", "/api/admin/products"),
    ("post", "/api/admin/products"),
    ("get", "/api/admin/products/categories"),
    ("patch", "/api/admin/products/1"),
    ("delete", "/api/admin/products/1"),
    ("get", "/api/admin/products/1/documents"),
    ("post", "/api/admin/products/1/documents"),
    ("delete", "/api/admin/products/1/documents/1"),
    ("post", "/api/admin/knowledge/reindex"),
    ("get", "/api/admin/knowledge/stats"),
]


@pytest.mark.django_db
@pytest.mark.parametrize(("method", "url"), ADMIN_ENDPOINTS)
def test_anonymous_gets_401(method, url):
    response = getattr(APIClient(), method)(url, format="json")

    assert response.status_code == 401


@pytest.mark.django_db
@pytest.mark.parametrize(("method", "url"), ADMIN_ENDPOINTS)
def test_non_admin_gets_403(method, url, django_user_model):
    user = django_user_model.objects.create_user("guest", password="x")
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=user).key}")

    response = getattr(client, method)(url, format="json")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "PERMISSION_DENIED"
