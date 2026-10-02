from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("api/", include("common.urls")),
    path("api/auth/", include("accounts.urls")),
]
