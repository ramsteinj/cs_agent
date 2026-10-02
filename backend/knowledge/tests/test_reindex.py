import psycopg
import pytest
from django.core.management import call_command
from django.db import connection

from knowledge.indexing import REINDEX_LOCK_KEY
from knowledge.models import Company, KnowledgeChunk, Product

from .factories import make_company, make_product


@pytest.mark.django_db
def test_reindex_rebuilds_all_chunks(admin_client):
    company = make_company(index=False)
    make_product(company, index=False)
    make_product(company, name="두번째", index=False)
    assert not KnowledgeChunk.objects.exists()

    response = admin_client.post("/api/admin/knowledge/reindex")

    assert response.status_code == 200
    assert response.json()["chunks"] == KnowledgeChunk.objects.count() >= 3


@pytest.mark.django_db
def test_reindex_conflict_when_already_running(admin_client):
    params = connection.get_connection_params()
    params.pop("cursor_factory", None)
    params.pop("context", None)
    with psycopg.connect(**params, autocommit=True) as other:
        other.execute("SELECT pg_advisory_lock(%s)", [REINDEX_LOCK_KEY])
        try:
            response = admin_client.post("/api/admin/knowledge/reindex")
        finally:
            other.execute("SELECT pg_advisory_unlock(%s)", [REINDEX_LOCK_KEY])

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CONFLICT"


@pytest.mark.django_db
def test_stats(admin_client):
    make_product(make_company())

    body = admin_client.get("/api/admin/knowledge/stats").json()

    assert body["companies"] == 1
    assert body["products"] == 1
    assert body["chunks"] == KnowledgeChunk.objects.count()
    assert body["embedding_model"] == "fake"
    assert body["embedding_dim"] == 384


@pytest.mark.django_db
def test_load_sample_knowledge_is_idempotent():
    call_command("load_sample_knowledge")
    call_command("load_sample_knowledge")

    assert Company.objects.count() == 1
    assert Product.objects.count() == 3
    assert KnowledgeChunk.objects.filter(is_searchable=False).exists()  # inactive product

    call_command("load_sample_knowledge", "--reset")
    assert Product.objects.count() == 3
