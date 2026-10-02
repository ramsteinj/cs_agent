import pytest
from django.core.cache import cache
from rest_framework.test import APIClient


@pytest.fixture(autouse=True)
def _clear_cache():
    # Throttle counters live in the cache; isolate tests from each other.
    cache.clear()
    yield
    cache.clear()


@pytest.fixture(autouse=True)
def _fake_embeddings(settings):
    # Deterministic hashing vectors; no model download in tests (specs/08).
    settings.EMBEDDING_BACKEND = "fake"


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def admin_user(django_user_model):
    return django_user_model.objects.create_user(
        "manager", password="Str0ng-pass!", role="ADMIN", is_staff=True
    )


@pytest.fixture
def admin_client(admin_user):
    from rest_framework.authtoken.models import Token

    client = APIClient()
    token = Token.objects.create(user=admin_user)
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    return client
