import logging
from unittest import mock

import pytest

from common.audit import audit
from knowledge.tests.factories import make_company, make_product


@pytest.fixture
def audit_log(caplog):
    caplog.set_level(logging.INFO, logger="audit")
    return caplog


def _lines(caplog):
    return [r.getMessage() for r in caplog.records if r.name == "audit"]


def test_values_are_quoted_against_log_injection(audit_log):
    audit("login_failed", "evil\nevent=login_success user='admin'")

    (line,) = _lines(audit_log)
    assert "\n" not in line
    assert line.startswith("event=login_failed user=")


@pytest.mark.django_db
def test_login_events(api_client, audit_log):
    api_client.post("/api/auth/login", {"username": "admin", "password": "bad"}, format="json")
    api_client.post(
        "/api/auth/login", {"username": "admin", "password": "admin1234!"}, format="json"
    )

    lines = _lines(audit_log)
    assert lines[0] == "event=login_failed user='admin' reason='INVALID_CREDENTIALS'"
    assert lines[1] == "event=login_success user='admin'"
    assert "admin1234!" not in audit_log.text
    assert "bad" not in " ".join(lines)


@pytest.mark.django_db
def test_api_key_events_never_contain_the_key(admin_client, audit_log):
    key = "sk-ant-api03-audit-secret-WXYZ"
    with mock.patch("llm.anthropic_provider.anthropic.Anthropic"):
        admin_client.put(
            "/api/admin/settings/providers/anthropic/api-key", {"api_key": key}, format="json"
        )
    admin_client.delete("/api/admin/settings/providers/anthropic/api-key")
    admin_client.patch(
        "/api/admin/settings/providers/anthropic", {"model": "claude-sonnet-5-5"}, format="json"
    )

    lines = _lines(audit_log)
    assert "event=api_key_updated user='manager' provider='anthropic'" in lines
    assert "event=api_key_deleted user='manager' provider='anthropic'" in lines
    assert (
        "event=llm_model_updated user='manager' provider='anthropic' model='claude-sonnet-5-5'"
        in lines
    )
    assert key not in audit_log.text


@pytest.mark.django_db
def test_delete_and_reindex_events(admin_client, audit_log):
    company = make_company(name="감사회사")
    product = make_product(company, name="감사제품")

    admin_client.delete(f"/api/admin/products/{product.pk}")
    admin_client.delete(f"/api/admin/companies/{company.pk}")
    admin_client.post("/api/admin/knowledge/reindex")

    lines = _lines(audit_log)
    assert f"event=product_deleted user='manager' id='{product.pk}' name='감사제품'" in lines
    assert f"event=company_deleted user='manager' id='{company.pk}' name='감사회사'" in lines
    assert "event=knowledge_reindexed user='manager' chunks='0'" in lines
