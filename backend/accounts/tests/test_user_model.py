import pytest
from django.contrib.auth import get_user_model


def test_custom_user_model_is_active():
    assert get_user_model()._meta.label == "accounts.User"


@pytest.mark.django_db
def test_user_defaults():
    user = get_user_model().objects.create_user("someone", password="pw-123456")

    assert user.role == "USER"
    assert user.is_admin_role is False
    assert user.must_change_password is False
    assert user.failed_login_count == 0
    assert user.locked_until is None
