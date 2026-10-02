from rest_framework.permissions import BasePermission


class IsAdminRole(BasePermission):
    """Allows access only to active users whose role is ADMIN."""

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and user.is_active
            and getattr(user, "is_admin_role", False)
        )
