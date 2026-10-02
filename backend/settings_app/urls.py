from django.urls import path

from . import views

# Mounted at /api/admin/
urlpatterns = [
    path("settings", views.system_settings, name="admin-settings"),
    path("settings/rag", views.rag_settings, name="admin-settings-rag"),
    path("settings/providers/<str:provider>", views.provider_config, name="admin-provider"),
    path(
        "settings/providers/<str:provider>/api-key",
        views.provider_api_key,
        name="admin-provider-api-key",
    ),
    path(
        "settings/providers/<str:provider>/models",
        views.provider_models,
        name="admin-provider-models",
    ),
]
