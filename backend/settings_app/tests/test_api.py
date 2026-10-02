import json
from unittest import mock

import pytest

import llm
from settings_app.models import LLMProviderConfig, SystemSetting

KEY = "sk-ant-api03-test-secret-value-WXYZ"
SETTINGS_URL = "/api/admin/settings"


def key_url(provider):
    return f"/api/admin/settings/providers/{provider}/api-key"


@pytest.fixture
def validate():
    """Patch every provider's validate_key (no network). Returns {provider: mock}."""
    patches = {
        name: mock.patch.object(type(provider), "validate_key", autospec=True)
        for name, provider in llm.PROVIDERS.items()
    }
    mocks = {name: patch.start() for name, patch in patches.items()}
    yield mocks
    for patch in patches.values():
        patch.stop()


def _no_plain_key(response, key=KEY):
    assert key not in json.dumps(response.json() if response.content else {})


@pytest.mark.django_db
class TestSettings:
    def test_defaults(self, admin_client):
        body = admin_client.get(SETTINGS_URL).json()

        assert body["llm_provider"] == "anthropic"
        assert body["chatbot_enabled"] is False
        assert [p["provider"] for p in body["providers"]] == ["anthropic", "openai", "gemini"]
        claude, chatgpt, gemini = body["providers"]
        assert claude == {
            "provider": "anthropic",
            "label": "Claude",
            "api_key_configured": False,
            "api_key_masked": "",
            "api_key_updated_at": None,
            "model": "claude-opus-5-5",
            "default_model": "claude-opus-5-5",
        }
        assert (chatgpt["label"], chatgpt["model"]) == ("ChatGPT", "")
        assert (gemini["label"], gemini["model"]) == ("Gemini", "")

    def test_patch_provider_and_bot_settings(self, admin_client):
        response = admin_client.patch(
            SETTINGS_URL,
            {"llm_provider": "gemini", "bot_name": "OK 상담봇", "extra_instructions": "친근하게"},
            format="json",
        )

        assert response.status_code == 200
        setting = SystemSetting.load()
        assert (setting.llm_provider, setting.bot_name) == ("gemini", "OK 상담봇")

    def test_unknown_provider_rejected(self, admin_client):
        response = admin_client.patch(SETTINGS_URL, {"llm_provider": "mistral"}, format="json")

        assert response.status_code == 400
        assert "llm_provider" in response.json()["error"]["details"]

    def test_patch_validation(self, admin_client):
        assert admin_client.patch(SETTINGS_URL, {"bot_name": ""}, format="json").status_code == 400
        response = admin_client.patch(
            SETTINGS_URL, {"extra_instructions": "가" * 2001}, format="json"
        )
        assert "extra_instructions" in response.json()["error"]["details"]


@pytest.mark.django_db
class TestProviderKeys:
    @pytest.mark.parametrize(
        ("provider", "key", "masked"),
        [
            ("anthropic", KEY, "sk-ant-...WXYZ"),
            ("openai", "sk-proj-test-secret-ABCD", "sk-...ABCD"),
            ("gemini", "AIzaSyTestSecretEFGH", "AIza...EFGH"),
        ],
    )
    def test_valid_key_is_saved_encrypted_and_masked(
        self, admin_client, validate, provider, key, masked
    ):
        response = admin_client.put(key_url(provider), {"api_key": key}, format="json")

        assert response.status_code == 200
        row = next(p for p in response.json()["providers"] if p["provider"] == provider)
        assert row["api_key_configured"] is True
        assert row["api_key_masked"] == masked
        _no_plain_key(response, key)
        validate[provider].assert_called_once()
        config = LLMProviderConfig.get(provider)
        assert config.get_api_key() == key
        assert key not in config.api_key_encrypted

    def test_rejected_key_is_not_saved(self, admin_client, validate):
        validate["openai"].side_effect = llm.InvalidAPIKey("status=401")

        response = admin_client.put(
            key_url("openai"), {"api_key": "sk-bad-key-1234"}, format="json"
        )

        assert response.status_code == 400
        assert response.json()["error"] == {
            "code": "INVALID_API_KEY",
            "message": "유효하지 않은 API Key입니다.",
        }
        assert LLMProviderConfig.get("openai").api_key_configured is False

    def test_unreachable_provider_returns_502_and_keeps_old_key(self, admin_client, validate):
        LLMProviderConfig.get("gemini").set_api_key("AIzaOldKey0000")
        validate["gemini"].side_effect = llm.LLMError("error=ConnectError")

        response = admin_client.put(key_url("gemini"), {"api_key": "AIzaNewKey1111"}, format="json")

        assert response.status_code == 502
        assert response.json()["error"]["code"] == "LLM_ERROR"
        assert LLMProviderConfig.get("gemini").get_api_key() == "AIzaOldKey0000"

    def test_malformed_key_rejected_without_calling_provider(self, admin_client, validate):
        response = admin_client.put(key_url("anthropic"), {"api_key": "bad key"}, format="json")

        assert response.status_code == 400
        validate["anthropic"].assert_not_called()

    def test_unknown_provider_404(self, admin_client):
        assert (
            admin_client.put(key_url("mistral"), {"api_key": KEY}, format="json").status_code == 404
        )

    def test_delete_selected_provider_key_disables_chatbot(self, admin_client, api_client):
        LLMProviderConfig.get("anthropic").set_api_key(KEY)
        assert api_client.get("/api/chat/status").json()["enabled"] is True

        assert admin_client.delete(key_url("anthropic")).status_code == 204

        assert api_client.get("/api/chat/status").json()["enabled"] is False

    def test_keys_are_kept_when_switching_providers(self, admin_client, api_client):
        LLMProviderConfig.get("anthropic").set_api_key(KEY)

        admin_client.patch(SETTINGS_URL, {"llm_provider": "openai"}, format="json")
        assert api_client.get("/api/chat/status").json()["enabled"] is False  # no OpenAI key

        admin_client.patch(SETTINGS_URL, {"llm_provider": "anthropic"}, format="json")
        assert api_client.get("/api/chat/status").json()["enabled"] is True

    def test_provider_without_model_is_not_ready(self, admin_client, api_client):
        config = LLMProviderConfig.get("openai")
        config.set_api_key("sk-proj-test-1234")
        admin_client.patch(SETTINGS_URL, {"llm_provider": "openai"}, format="json")

        assert api_client.get("/api/chat/status").json()["enabled"] is False

        admin_client.patch(
            "/api/admin/settings/providers/openai", {"model": "gpt-test-1"}, format="json"
        )
        assert api_client.get("/api/chat/status").json()["enabled"] is True


@pytest.mark.django_db
class TestModels:
    def test_change_claude_model(self, admin_client):
        response = admin_client.patch(
            "/api/admin/settings/providers/anthropic", {"model": "claude-sonnet-5-5"}, format="json"
        )

        assert response.status_code == 200
        assert response.json()["model"] == "claude-sonnet-5-5"
        assert LLMProviderConfig.get("anthropic").model == "claude-sonnet-5-5"

    def test_model_name_validation(self, admin_client):
        response = admin_client.patch(
            "/api/admin/settings/providers/anthropic", {"model": "bad model"}, format="json"
        )

        assert response.status_code == 400
        assert "model" in response.json()["error"]["details"]

    def test_claude_models_without_key_are_recommended(self, admin_client):
        body = admin_client.get("/api/admin/settings/providers/anthropic/models").json()

        assert body == {
            "models": ["claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-4-5"],
            "default_model": "claude-opus-5-5",
        }

    def test_other_models_need_a_key(self, admin_client):
        response = admin_client.get("/api/admin/settings/providers/gemini/models")

        assert response.status_code == 400
        assert response.json()["error"]["code"] == "API_KEY_REQUIRED"

    def test_models_from_provider(self, admin_client):
        LLMProviderConfig.get("openai").set_api_key("sk-proj-test-1234")
        with mock.patch.object(
            type(llm.get_provider("openai")), "list_models", return_value=["gpt-test-1"]
        ) as list_models:
            body = admin_client.get("/api/admin/settings/providers/openai/models").json()

        assert body == {"models": ["gpt-test-1"], "default_model": ""}
        list_models.assert_called_once_with("sk-proj-test-1234")

    def test_model_listing_failure_is_502(self, admin_client):
        LLMProviderConfig.get("gemini").set_api_key("AIzaTest1234")
        with mock.patch.object(
            type(llm.get_provider("gemini")), "list_models", side_effect=llm.LLMError("status=503")
        ):
            response = admin_client.get("/api/admin/settings/providers/gemini/models")

        assert response.status_code == 502


@pytest.mark.django_db
def test_failure_logs_have_no_key(admin_client, validate, caplog):
    validate["anthropic"].side_effect = llm.InvalidAPIKey(
        "status=401 type=authentication_error request_id=req_1"
    )

    admin_client.put(key_url("anthropic"), {"api_key": KEY}, format="json")

    assert "status=401 type=authentication_error request_id=req_1" in caplog.text
    assert KEY not in caplog.text
