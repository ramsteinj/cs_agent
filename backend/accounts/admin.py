from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ["username", "role", "is_active", "must_change_password", "last_login"]
    list_filter = ["role", "is_active"]
    fieldsets = UserAdmin.fieldsets + (
        (
            "cs_agent",
            {"fields": ("role", "must_change_password", "failed_login_count", "locked_until")},
        ),
    )
