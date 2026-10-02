from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from chat.models import ChatSession


class Command(BaseCommand):
    help = "Delete chat sessions (and their messages) inactive for N days (default 30)."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=30)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        if options["days"] < 1:
            self.stderr.write("--days must be at least 1")
            return
        cutoff = timezone.now() - timedelta(days=options["days"])
        stale = ChatSession.objects.filter(last_activity_at__lt=cutoff)
        count = stale.count()
        if options["dry_run"]:
            self.stdout.write(f"{count} session(s) would be deleted.")
            return
        stale.delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted {count} chat session(s)."))
