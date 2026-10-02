import pytest
from django.test import RequestFactory

from common.views import server_error


@pytest.mark.django_db
def test_unknown_api_path_uses_common_json_format(client):
    response = client.get("/api/does-not-exist")

    assert response.status_code == 404
    assert response.json() == {
        "error": {"code": "NOT_FOUND", "message": "요청한 항목을 찾을 수 없습니다."}
    }


@pytest.mark.django_db
def test_non_api_404_is_not_json(client):
    response = client.get("/nope")

    assert response.status_code == 404
    assert not response["Content-Type"].startswith("application/json")


def test_api_500_is_json_without_details():
    response = server_error(RequestFactory().get("/api/anything"))

    assert response.status_code == 500
    assert b"SERVER_ERROR" in response.content
    assert b"Traceback" not in response.content
