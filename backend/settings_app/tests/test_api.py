import json
from unittest import mock

import anthropic
import httpx2
import pytest

from settings_app.models import AVAILABLE_MODELS, SystemSetting

KEY = "sk-ant-api03-test-secret-value-WXYZ"
SETTINGS_URL = "/api/admin/settings"
KEY_URL = "/api/admin/settings/api-key"

_REQUEST = httpx2.Request("GET", "https://api.anthropic.com/v1/models")


def _status_error(cls, code):
    return cls("error", response=httpx2.Response(code, request=_REQUEST), body=None)


@pytest.fixture
def anthropic_client():
    """Patch the SDK client used for key validation; .models.list succeeds by default."""
    with mock.patch("settings_app.services.anthropic.Anthropic") as client_cls:
        yield client_cls


def _assert_no_plain_key(response):
    assert KEY not in json.dumps(response.json() if response.content else {})


@pytest.mark.django_db
class TestGetAndPatch:
    def test_get_defaults(self, admin_client):
        response = admin_client.get(SETTINGS_URL)

        assert response.status_code == 200
        body = response.json()
        assert body["api_key_configured"] is False
        assert body["api_key_masked"] == ""
        assert body["claude_model"] == "claude-opus-5-5"
        assert body["available_models"] == AVAILABLE_MODELS

    def test_patch_updates_chatbot_settings(self, admin_client):
        response = admin_client.patch(
            SETTINGS_URL,
            {
                "claude_model": "claude-sonnet-5-5",
                "bot_name": "OK 상담봇",
                "welcome_message": "무엇을 도와드릴까요?",
                "extra_instructions": "친근한 말투로 답하세요.",
            },
            format="json",
        )

        assert response.status_code == 200
        setting = SystemSetting.load()
        assert setting.claude_model == "claude-sonnet-5-5"
        assert setting.bot_name == "OK 상담봇"
        assert setting.extra_instructions == "친근한 말투로 답하세요."

    def test_patch_rejects_unknown_model(self, admin_client):
        response = admin_client.patch(SETTINGS_URL, {"claude_model": "gpt-4"}, format="json")

        assert response.status_code == 400
        assert "claude_model" in response.json()["error"]["details"]

    def test_patch_rejects_too_long_extra_instructions(self, admin_client):
        response = admin_client.patch(
            SETTINGS_URL, {"extra_instructions": "가" * 2001}, format="json"
        )

        assert response.status_code == 400
        assert "extra_instructions" in response.json()["error"]["details"]

    def test_patch_rejects_blank_bot_name(self, admin_client):
        response = admin_client.patch(SETTINGS_URL, {"bot_name": ""}, format="json")

        assert response.status_code == 400

    def test_patch_cannot_set_api_key_fields(self, admin_client):
        admin_client.patch(
            SETTINGS_URL,
            {"api_key_masked": "x", "anthropic_api_key_encrypted": "x"},
            format="json",
        )

        assert SystemSetting.load().chatbot_enabled is False


@pytest.mark.django_db
class TestApiKey:
    def test_valid_key_is_saved_and_masked(self, admin_client, anthropic_client):
        response = admin_client.put(KEY_URL, {"api_key": KEY}, format="json")

        assert response.status_code == 200
        body = response.json()
        assert body["api_key_configured"] is True
        assert body["api_key_masked"] == "sk-ant-...WXYZ"
        _assert_no_plain_key(response)
        anthropic_client.assert_called_once()
        assert anthropic_client.call_args.kwargs["api_key"] == KEY
        anthropic_client.return_value.models.list.assert_called_once_with(limit=1)
        assert SystemSetting.load().get_api_key() == KEY

    @pytest.mark.parametrize(
        "error", [(anthropic.AuthenticationError, 401), (anthropic.PermissionDeniedError, 403)]
    )
    def test_rejected_key_is_not_saved(self, admin_client, anthropic_client, error):
        anthropic_client.return_value.models.list.side_effect = _status_error(*error)

        response = admin_client.put(KEY_URL, {"api_key": KEY}, format="json")

        assert response.status_code == 400
        assert response.json()["error"] == {
            "code": "INVALID_API_KEY",
            "message": "유효하지 않은 API Key입니다.",
        }
        assert SystemSetting.load().chatbot_enabled is False

    def test_connection_failure_returns_502_and_keeps_old_key(self, admin_client, anthropic_client):
        SystemSetting.load().set_api_key("sk-ant-old-key-0000")
        anthropic_client.return_value.models.list.side_effect = anthropic.APIConnectionError(
            request=_REQUEST
        )

        response = admin_client.put(KEY_URL, {"api_key": KEY}, format="json")

        assert response.status_code == 502
        assert response.json()["error"]["code"] == "LLM_ERROR"
        assert SystemSetting.load().get_api_key() == "sk-ant-old-key-0000"

    def test_malformed_key_is_rejected_without_calling_anthropic(
        self, admin_client, anthropic_client
    ):
        response = admin_client.put(KEY_URL, {"api_key": "bad key"}, format="json")

        assert response.status_code == 400
        anthropic_client.assert_not_called()

    def test_delete_disables_chatbot(self, admin_client, api_client):
        SystemSetting.load().set_api_key(KEY)
        assert api_client.get("/api/chat/status").json()["enabled"] is True

        assert admin_client.delete(KEY_URL).status_code == 204

        assert SystemSetting.load().chatbot_enabled is False
        assert api_client.get("/api/chat/status").json()["enabled"] is False

    def test_key_is_never_logged(self, admin_client, anthropic_client, caplog):
        admin_client.put(KEY_URL, {"api_key": KEY}, format="json")
        anthropic_client.return_value.models.list.side_effect = _status_error(
            anthropic.AuthenticationError, 401
        )
        admin_client.put(KEY_URL, {"api_key": KEY}, format="json")

        assert KEY not in caplog.text
