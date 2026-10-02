"""Audit log for admin actions (specs/07-security.md §6).

One line per event: `event=<name> user=<username> key=value ...`. Values are repr()-quoted
so user-supplied text (e.g. a typed username) cannot inject fake log lines.
Never pass secrets (passwords, API Keys, tokens).
"""

import logging

logger = logging.getLogger("audit")

_MAX_VALUE = 150


def _quote(value):
    return repr(str(value)[:_MAX_VALUE])


def audit(event, user=None, **fields):
    username = getattr(user, "username", user)
    parts = [f"event={event}", f"user={_quote(username) if username else '-'}"]
    parts += [f"{key}={_quote(value)}" for key, value in fields.items()]
    logger.info(" ".join(parts))
