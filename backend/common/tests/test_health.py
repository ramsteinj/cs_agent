import pytest
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_health_returns_ok():
    response = APIClient().get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.django_db
def test_unknown_api_path_returns_404():
    assert APIClient().get("/api/does-not-exist").status_code == 404
