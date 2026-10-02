import pytest
from cryptography.fernet import Fernet
from django.core.exceptions import ImproperlyConfigured
from django.db import connection

from settings_app import crypto
from settings_app.models import LLMProviderConfig, SystemSetting

KEY = "sk-ant-api03-test-secret-value-WXYZ"


def test_encrypt_round_trip_and_ciphertext_differs():
    token = crypto.encrypt(KEY)

    assert token != KEY
    assert KEY not in token
    assert crypto.decrypt(token) == KEY


@pytest.mark.parametrize("bad_key", ["", "not-a-fernet-key"])
def test_missing_or_invalid_encryption_key_fails_fast(settings, bad_key):
    settings.FIELD_ENCRYPTION_KEY = bad_key

    with pytest.raises(ImproperlyConfigured):
        crypto.get_fernet()


@pytest.mark.django_db
class TestSystemSetting:
    def test_load_creates_singleton_with_defaults(self):
        setting = SystemSetting.load()

        assert setting.pk == 1
        assert setting.llm_provider == "anthropic"
        assert setting.chatbot_enabled is False
        assert SystemSetting.objects.count() == 1

    def test_save_always_uses_pk_1(self):
        SystemSetting(bot_name="other").save()

        assert SystemSetting.objects.count() == 1
        assert SystemSetting.load().bot_name == "other"

    def test_delete_is_forbidden(self):
        with pytest.raises(NotImplementedError):
            SystemSetting.load().delete()

    def test_enabled_follows_the_selected_provider(self):
        LLMProviderConfig.get("anthropic").set_api_key(KEY)
        setting = SystemSetting.load()
        assert setting.chatbot_enabled is True

        setting.llm_provider = "openai"
        setting.save()
        assert setting.chatbot_enabled is False


@pytest.mark.django_db
class TestLLMProviderConfig:
    def test_defaults_per_provider(self):
        assert LLMProviderConfig.get("anthropic").model == "claude-opus-5-5"
        assert LLMProviderConfig.get("openai").model == ""
        assert [c.provider for c in LLMProviderConfig.all_providers()] == [
            "anthropic",
            "openai",
            "gemini",
        ]

    def test_api_key_is_stored_encrypted(self):
        LLMProviderConfig.get("anthropic").set_api_key(KEY)

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT api_key_encrypted FROM settings_app_llmproviderconfig "
                "WHERE provider = 'anthropic'"
            )
            raw = cursor.fetchone()[0]
        assert raw and KEY not in raw

        config = LLMProviderConfig.get("anthropic")
        assert config.get_api_key() == KEY
        assert config.api_key_hint == "sk-ant-...WXYZ"
        assert config.api_key_updated_at is not None
        assert config.ready is True

    def test_clear_api_key(self):
        config = LLMProviderConfig.get("gemini")
        config.set_api_key("AIzaSecret1234")

        config.clear_api_key()

        assert config.get_api_key() is None
        assert config.api_key_hint == ""
        assert config.ready is False

    def test_key_encrypted_with_another_key_is_treated_as_missing(self, settings):
        config = LLMProviderConfig.get("anthropic")
        config.set_api_key(KEY)
        settings.FIELD_ENCRYPTION_KEY = Fernet.generate_key().decode()

        assert config.get_api_key() is None
        assert SystemSetting.load().chatbot_enabled is False
