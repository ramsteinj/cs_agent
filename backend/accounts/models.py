from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Single user model for admins and (future) customers, split by role (specs/03)."""

    class Role(models.TextChoices):
        ADMIN = "ADMIN", "관리자"
        USER = "USER", "사용자"

    role = models.CharField(max_length=10, choices=Role.choices, default=Role.USER, db_index=True)
    must_change_password = models.BooleanField(default=False)
    failed_login_count = models.PositiveIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)

    @property
    def is_admin_role(self):
        return self.role == self.Role.ADMIN
