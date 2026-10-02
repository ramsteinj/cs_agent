from unittest import mock

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

SDK_CLIENTS = (
    "llm.anthropic_provider.anthropic.Anthropic",
    "llm.openai_provider.openai.OpenAI",
    "llm.gemini_provider.genai.Client",
)


@pytest.fixture(autouse=True)
def _no_real_llm_calls():
    """Fail loudly if a test would reach a real LLM API (tests patch the client they use)."""
    patches = [
        mock.patch(target, side_effect=AssertionError(f"real LLM API call in tests: {target}"))
        for target in SDK_CLIENTS
    ]
    for patch in patches:
        patch.start()
    yield
    for patch in reversed(patches):
        patch.stop()


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
