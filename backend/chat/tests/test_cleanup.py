from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone

from chat.models import ChatMessage, ChatSession


def _session(days_ago):
    session = ChatSession.objects.create()
    ChatSession.objects.filter(pk=session.pk).update(
        last_activity_at=timezone.now() - timedelta(days=days_ago)
    )
    ChatMessage.objects.create(session=session, role="user", content="q")
    return session


@pytest.mark.django_db
def test_deletes_sessions_inactive_for_30_days():
    old = _session(31)
    recent = _session(29)

    out = StringIO()
    call_command("cleanup_chat_sessions", stdout=out)

    assert not ChatSession.objects.filter(pk=old.pk).exists()
    assert ChatSession.objects.filter(pk=recent.pk).exists()
    assert ChatMessage.objects.count() == 1  # cascaded
    assert "Deleted 1 chat session(s)." in out.getvalue()


@pytest.mark.django_db
def test_days_option_and_dry_run():
    _session(8)

    out = StringIO()
    call_command("cleanup_chat_sessions", "--days", "7", "--dry-run", stdout=out)

    assert "1 session(s) would be deleted." in out.getvalue()
    assert ChatSession.objects.count() == 1

    call_command("cleanup_chat_sessions", "--days", "7", stdout=StringIO())
    assert ChatSession.objects.count() == 0
