from django.core.management.base import BaseCommand

from accounts.services import ensure_default_admin


class Command(BaseCommand):
    help = "Create the default admin account if no ADMIN user exists."

    def handle(self, *args, **options):
        if ensure_default_admin():
            self.stdout.write(self.style.SUCCESS("Default admin account created."))
        else:
            self.stdout.write("Admin account already exists. Nothing to do.")
