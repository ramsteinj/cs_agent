import logging
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import update_last_login
from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.authtoken.models import Token

from common.audit import audit
from common.exceptions import ApiError

logger = logging.getLogger(__name__)

INVALID_CREDENTIALS_MESSAGE = "아이디 또는 비밀번호가 올바르지 않습니다."
ACCOUNT_LOCKED_MESSAGE = "로그인 시도가 너무 많습니다. 잠시 후 다시 시도해 주세요."


def ensure_default_admin():
    """Create the default admin if no ADMIN user exists. Idempotent (specs/01 F-A2).

    Returns the created user, or None when an admin already exists.
    """
    User = get_user_model()
    if User.objects.filter(role=User.Role.ADMIN).exists():
        return None

    user = User(
        username=settings.DEFAULT_ADMIN_USERNAME,
        role=User.Role.ADMIN,
        is_staff=True,
        must_change_password=True,
    )
    # Fixed value from the requirements, so password validators are intentionally skipped.
    user.set_password(settings.DEFAULT_ADMIN_PASSWORD)
    user.save()
    logger.info("Default admin account created")
    return user


def _invalid_credentials():
    return ApiError(
        "INVALID_CREDENTIALS", INVALID_CREDENTIALS_MESSAGE, status.HTTP_401_UNAUTHORIZED
    )


def _record_failure(user):
    user.failed_login_count += 1
    if user.failed_login_count >= settings.LOGIN_MAX_FAILED_ATTEMPTS:
        user.locked_until = timezone.now() + timedelta(minutes=settings.LOGIN_LOCK_MINUTES)
        user.failed_login_count = 0
    user.save(update_fields=["failed_login_count", "locked_until"])


def login_admin(username, password):
    """Authenticate an ADMIN user and return (user, token key).

    Raises ApiError INVALID_CREDENTIALS (401) or ACCOUNT_LOCKED (423).
    The failure message never reveals whether the username or the password was wrong.
    """
    User = get_user_model()
    # Decide inside the transaction, raise after it commits: raising inside atomic()
    # would roll back the failure counter and the lock would never trigger.
    error = None
    with transaction.atomic():
        user = User.objects.select_for_update().filter(username=username).first()
        if user is None:
            error = _invalid_credentials()
        elif user.locked_until and user.locked_until > timezone.now():
            error = ApiError("ACCOUNT_LOCKED", ACCOUNT_LOCKED_MESSAGE, 423)
        elif not user.check_password(password):
            _record_failure(user)
            error = _invalid_credentials()
        elif not (user.is_active and user.is_admin_role):
            error = _invalid_credentials()
        else:
            user.failed_login_count = 0
            user.locked_until = None
            user.save(update_fields=["failed_login_count", "locked_until"])

    if error:
        reason = getattr(error, "error_code", "INVALID_CREDENTIALS")
        audit("login_failed", username, reason=reason)
        raise error

    update_last_login(None, user)
    audit("login_success", user)
    token, _ = Token.objects.get_or_create(user=user)
    return user, token.key


def logout(user):
    Token.objects.filter(user=user).delete()
    audit("logout", user)


def change_password(user, new_password):
    """Set a new password, clear the default-password flag and rotate the token."""
    with transaction.atomic():
        user.set_password(new_password)
        user.must_change_password = False
        user.save(update_fields=["password", "must_change_password"])
        Token.objects.filter(user=user).delete()
        token = Token.objects.create(user=user)
    audit("password_changed", user)
    return token.key
