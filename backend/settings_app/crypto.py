"""Fernet encryption for secrets stored in the DB (specs/07-security.md §3).

The key comes from FIELD_ENCRYPTION_KEY and is never stored in the DB, so a DB backup
alone cannot decrypt the API Key.
"""

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


def get_fernet():
    key = settings.FIELD_ENCRYPTION_KEY
    if not key:
        raise ImproperlyConfigured(
            "FIELD_ENCRYPTION_KEY is not set. Generate one with: "
            'python -c "from cryptography.fernet import Fernet; '
            'print(Fernet.generate_key().decode())"'
        )
    try:
        return Fernet(key)
    except (ValueError, TypeError) as exc:
        raise ImproperlyConfigured(
            "FIELD_ENCRYPTION_KEY is not a valid Fernet key (32 url-safe base64-encoded bytes)."
        ) from exc


def encrypt(plaintext: str) -> str:
    return get_fernet().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    """Raises cryptography.fernet.InvalidToken if the key changed or data is corrupt."""
    return get_fernet().decrypt(ciphertext.encode()).decode()


__all__ = ["InvalidToken", "decrypt", "encrypt", "get_fernet"]
