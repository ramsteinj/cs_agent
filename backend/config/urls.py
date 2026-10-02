from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("api/", include("common.urls")),
    path("api/auth/", include("accounts.urls")),
    path("api/admin/", include("settings_app.urls")),
    path("api/admin/", include("knowledge.urls")),
    path("api/chat/", include("chat.urls")),
]

handler404 = "common.views.not_found"
handler500 = "common.views.server_error"
