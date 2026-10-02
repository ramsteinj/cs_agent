import logging

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command

from accounts.services import ensure_default_admin

User = get_user_model()


@pytest.fixture
def no_admins(db):
    # migrate (post_migrate) already created the default admin in the test DB
    User.objects.all().delete()


def test_default_admin_exists_after_migrate(db):
    admin = User.objects.get(username="admin")

    assert admin.role == User.Role.ADMIN
    assert admin.is_staff is True
    assert admin.must_change_password is True
    assert admin.check_password("admin1234!")


def test_creates_admin_on_empty_db(no_admins, caplog):
    with caplog.at_level(logging.INFO, logger="accounts"):
        created = ensure_default_admin()

    assert created is not None
    assert created.check_password("admin1234!")
    assert "Default admin account created" in caplog.text
    assert "admin1234!" not in caplog.text


def test_does_nothing_when_an_admin_exists(no_admins, admin_user):
    assert ensure_default_admin() is None
    assert not User.objects.filter(username="admin").exists()


def test_running_twice_does_not_duplicate_or_reset_password(no_admins):
    call_command("ensure_default_admin")
    admin = User.objects.get(username="admin")
    admin.set_password("Changed-pass-123")
    admin.save()

    call_command("ensure_default_admin")

    assert User.objects.filter(role=User.Role.ADMIN).count() == 1
    admin.refresh_from_db()
    assert admin.check_password("Changed-pass-123")


def test_non_admin_users_do_not_count_as_admin(no_admins, django_user_model):
    django_user_model.objects.create_user("guest", password="x")

    assert ensure_default_admin() is not None
