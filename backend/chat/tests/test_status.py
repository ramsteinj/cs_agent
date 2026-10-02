import pytest

from settings_app.models import LLMProviderConfig, SystemSetting


@pytest.mark.django_db
def test_status_disabled_without_api_key(api_client):
    response = api_client.get("/api/chat/status")

    assert response.status_code == 200
    assert response.json() == {
        "enabled": False,
        "bot_name": "고객지원 챗봇",
        "welcome_message": "안녕하세요! 회사와 제품에 대해 궁금한 점을 물어보세요.",
    }


@pytest.mark.django_db
def test_status_enabled_with_api_key(api_client):
    setting = SystemSetting.load()
    setting.bot_name = "OK 상담봇"
    setting.save()
    LLMProviderConfig.get("anthropic").set_api_key("sk-ant-api03-test-secret-value-WXYZ")

    body = api_client.get("/api/chat/status").json()

    assert body["enabled"] is True
    assert body["bot_name"] == "OK 상담봇"
    assert "api_key" not in str(body)
