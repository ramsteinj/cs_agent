import pytest
from django.test import RequestFactory

from chat.services import client_ip

LOGIN = "/api/auth/login"


def _login(client, xff):
    return client.post(
        LOGIN, {"username": "x", "password": "y"}, format="json", HTTP_X_FORWARDED_FOR=xff
    )


@pytest.mark.django_db
def test_spoofed_x_forwarded_for_cannot_bypass_login_throttle(api_client):
    codes = [_login(api_client, f"10.0.0.{i}").status_code for i in range(11)]

    assert codes[-1] == 429


@pytest.mark.django_db
def test_behind_one_trusted_proxy_the_last_hop_is_used(api_client, settings):
    settings.REST_FRAMEWORK = {**settings.REST_FRAMEWORK, "NUM_PROXIES": 1}

    # A client faking the first entry still lands on the address the proxy appended.
    codes = [_login(api_client, f"10.0.0.{i}, 203.0.113.7").status_code for i in range(11)]

    assert codes[-1] == 429


def test_chat_client_ip_ignores_x_forwarded_for_by_default():
    request = RequestFactory().get("/", HTTP_X_FORWARDED_FOR="1.2.3.4", REMOTE_ADDR="9.9.9.9")

    assert client_ip(request) == "9.9.9.9"


def test_chat_client_ip_uses_trusted_proxy_hop(settings):
    settings.REST_FRAMEWORK = {**settings.REST_FRAMEWORK, "NUM_PROXIES": 1}
    request = RequestFactory().get(
        "/", HTTP_X_FORWARDED_FOR="1.2.3.4, 203.0.113.7", REMOTE_ADDR="10.0.0.1"
    )

    assert client_ip(request) == "203.0.113.7"
