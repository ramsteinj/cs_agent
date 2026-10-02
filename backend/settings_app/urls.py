from django.urls import path

from . import views

# Mounted at /api/admin/
urlpatterns = [
    path("settings", views.system_settings, name="admin-settings"),
    path("settings/api-key", views.api_key, name="admin-settings-api-key"),
]
