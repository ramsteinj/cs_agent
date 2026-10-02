from .services import ensure_default_admin


def create_default_admin(sender, **kwargs):
    """post_migrate receiver: make sure an admin exists right after migrate."""
    ensure_default_admin()
