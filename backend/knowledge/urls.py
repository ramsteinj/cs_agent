from django.urls import path
from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter(trailing_slash=False)
router.register("companies", views.CompanyViewSet, basename="company")
router.register("products", views.ProductViewSet, basename="product")

# Mounted at /api/admin/
urlpatterns = [
    path("knowledge/reindex", views.reindex, name="knowledge-reindex"),
    path("knowledge/stats", views.stats, name="knowledge-stats"),
    *router.urls,
]
