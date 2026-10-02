import pytest
from cryptography.fernet import Fernet
from django.core.exceptions import ImproperlyConfigured
from django.db import connection

from settings_app import crypto
from settings_app.models import DEFAULT_MODEL, SystemSetting

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
        assert setting.claude_model == DEFAULT_MODEL
        assert setting.chatbot_enabled is False
        assert SystemSetting.load().pk == 1
        assert SystemSetting.objects.count() == 1

    def test_save_always_uses_pk_1(self):
        SystemSetting(bot_name="other").save()

        assert SystemSetting.objects.count() == 1
        assert SystemSetting.load().bot_name == "other"

    def test_delete_is_forbidden(self):
        with pytest.raises(NotImplementedError):
            SystemSetting.load().delete()

    def test_api_key_is_stored_encrypted(self):
        SystemSetting.load().set_api_key(KEY)

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT anthropic_api_key_encrypted FROM settings_app_systemsetting WHERE id = 1"
            )
            raw = cursor.fetchone()[0]
        assert raw and raw != KEY and KEY not in raw

        setting = SystemSetting.load()
        assert setting.get_api_key() == KEY
        assert setting.api_key_masked == "sk-ant-...WXYZ"
        assert setting.api_key_updated_at is not None
        assert setting.chatbot_enabled is True

    def test_clear_api_key(self):
        setting = SystemSetting.load()
        setting.set_api_key(KEY)

        setting.clear_api_key()

        assert setting.get_api_key() is None
        assert setting.api_key_masked == ""
        assert setting.chatbot_enabled is False

    def test_key_encrypted_with_another_key_is_treated_as_missing(self, settings):
        setting = SystemSetting.load()
        setting.set_api_key(KEY)
        settings.FIELD_ENCRYPTION_KEY = Fernet.generate_key().decode()

        assert setting.get_api_key() is None
        assert setting.chatbot_enabled is False
