from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.authtoken.models import Token

LOGIN = "/api/auth/login"
INVALID = "아이디 또는 비밀번호가 올바르지 않습니다."


def _login(client, username, password):
    return client.post(LOGIN, {"username": username, "password": password}, format="json")


@pytest.mark.django_db
class TestLogin:
    def test_default_admin_can_login(self, api_client):
        response = _login(api_client, "admin", "admin1234!")

        assert response.status_code == 200
        body = response.json()
        assert body["token"]
        assert body["user"] == {
            "id": body["user"]["id"],
            "username": "admin",
            "role": "ADMIN",
            "must_change_password": True,
        }

    def test_wrong_password_returns_generic_401(self, api_client):
        response = _login(api_client, "admin", "wrong")

        assert response.status_code == 401
        assert response.json()["error"] == {"code": "INVALID_CREDENTIALS", "message": INVALID}

    def test_unknown_user_returns_same_message(self, api_client):
        response = _login(api_client, "nobody", "wrong")

        assert response.status_code == 401
        assert response.json()["error"]["message"] == INVALID

    def test_non_admin_role_cannot_login(self, api_client, django_user_model):
        django_user_model.objects.create_user("guest", password="Str0ng-pass!")

        response = _login(api_client, "guest", "Str0ng-pass!")

        assert response.status_code == 401
        assert response.json()["error"]["message"] == INVALID

    def test_inactive_admin_cannot_login(self, api_client, admin_user):
        admin_user.is_active = False
        admin_user.save()

        assert _login(api_client, "manager", "Str0ng-pass!").status_code == 401

    def test_missing_fields_returns_validation_error(self, api_client):
        response = api_client.post(LOGIN, {}, format="json")

        assert response.status_code == 400
        assert set(response.json()["error"]["details"]) == {"username", "password"}

    def test_lock_after_five_failures(self, api_client, admin_user):
        for _ in range(4):
            assert _login(api_client, "manager", "wrong").status_code == 401
        assert _login(api_client, "manager", "wrong").status_code == 401  # 5th -> lock

        response = _login(api_client, "manager", "Str0ng-pass!")

        assert response.status_code == 423
        assert response.json()["error"]["code"] == "ACCOUNT_LOCKED"

    def test_lock_expires(self, api_client, admin_user):
        admin_user.locked_until = timezone.now() - timedelta(seconds=1)
        admin_user.save()

        assert _login(api_client, "manager", "Str0ng-pass!").status_code == 200

    def test_success_resets_failure_count(self, api_client, admin_user):
        _login(api_client, "manager", "wrong")
        _login(api_client, "manager", "Str0ng-pass!")

        admin_user.refresh_from_db()
        assert admin_user.failed_login_count == 0

    def test_login_is_throttled_per_ip(self, api_client):
        for _ in range(10):
            _login(api_client, "nobody", "wrong")

        response = _login(api_client, "nobody", "wrong")

        assert response.status_code == 429
        assert response.json()["error"]["code"] == "RATE_LIMITED"


@pytest.mark.django_db
class TestSession:
    def test_me_returns_current_admin(self, admin_client):
        response = admin_client.get("/api/auth/me")

        assert response.status_code == 200
        assert response.json()["username"] == "manager"

    def test_me_requires_auth(self, api_client):
        response = api_client.get("/api/auth/me")

        assert response.status_code == 401
        assert response.json()["error"]["code"] == "NOT_AUTHENTICATED"

    def test_logout_revokes_token(self, admin_client, admin_user):
        assert admin_client.post("/api/auth/logout").status_code == 204
        assert not Token.objects.filter(user=admin_user).exists()
        assert admin_client.get("/api/auth/me").status_code == 401


@pytest.mark.django_db
class TestChangePassword:
    URL = "/api/auth/change-password"

    def test_change_password_rotates_token_and_clears_flag(self, admin_client, admin_user):
        admin_user.must_change_password = True
        admin_user.save()
        old_token = Token.objects.get(user=admin_user).key

        response = admin_client.post(
            self.URL,
            {"current_password": "Str0ng-pass!", "new_password": "N3w-Secure-pass"},
            format="json",
        )

        assert response.status_code == 200
        body = response.json()
        assert body["token"] != old_token
        assert body["user"]["must_change_password"] is False
        admin_user.refresh_from_db()
        assert admin_user.check_password("N3w-Secure-pass")
        assert admin_client.get("/api/auth/me").status_code == 401  # old token revoked

    def test_wrong_current_password(self, admin_client):
        response = admin_client.post(
            self.URL,
            {"current_password": "nope", "new_password": "N3w-Secure-pass"},
            format="json",
        )

        assert response.status_code == 400
        assert "current_password" in response.json()["error"]["details"]

    def test_weak_new_password_is_rejected(self, admin_client):
        response = admin_client.post(
            self.URL,
            {"current_password": "Str0ng-pass!", "new_password": "1234"},
            format="json",
        )

        assert response.status_code == 400
        assert "new_password" in response.json()["error"]["details"]

    def test_same_password_is_rejected(self, admin_client):
        response = admin_client.post(
            self.URL,
            {"current_password": "Str0ng-pass!", "new_password": "Str0ng-pass!"},
            format="json",
        )

        assert response.status_code == 400
        assert "new_password" in response.json()["error"]["details"]
