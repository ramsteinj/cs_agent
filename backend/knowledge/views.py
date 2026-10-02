from django.conf import settings
from django.db.models import Count, Q
from rest_framework import filters, viewsets
from rest_framework.decorators import action, api_view
from rest_framework.response import Response

from . import services
from .indexing import reindex_all
from .models import Company, KnowledgeChunk, Product
from .serializers import CompanySerializer, ProductSerializer


class CompanyViewSet(viewsets.ModelViewSet):
    serializer_class = CompanySerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ["name"]

    def get_queryset(self):
        # Explicit order_by: Meta.ordering is ignored once Count() adds a GROUP BY.
        return Company.objects.annotate(
            product_count=Count("products", distinct=True),
            chunk_count=Count("chunks", filter=Q(chunks__product__isnull=True), distinct=True),
        ).order_by("name", "id")

    def perform_create(self, serializer):
        services.save_company(serializer)

    def perform_update(self, serializer):
        services.save_company(serializer)


def _parse_bool(value):
    return {"true": True, "1": True, "false": False, "0": False}.get(str(value).lower())


class ProductViewSet(viewsets.ModelViewSet):
    serializer_class = ProductSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ["name"]

    def get_queryset(self):
        queryset = (
            Product.objects.select_related("company")
            .annotate(chunk_count=Count("chunks", distinct=True))
            .order_by("name", "id")
        )
        params = self.request.query_params
        if params.get("company"):
            queryset = queryset.filter(company_id=params["company"])
        if params.get("category"):
            queryset = queryset.filter(category=params["category"])
        is_active = _parse_bool(params.get("is_active", ""))
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active)
        return queryset

    def perform_create(self, serializer):
        services.save_product(serializer)

    def perform_update(self, serializer):
        services.save_product(serializer)

    @action(detail=False, methods=["get"])
    def categories(self, request):
        categories = (
            Product.objects.exclude(category="")
            .order_by("category")
            .values_list("category", flat=True)
            .distinct()
        )
        return Response(list(categories))


@api_view(["POST"])
def reindex(request):
    return Response({"chunks": reindex_all()})


@api_view(["GET"])
def stats(request):
    model = "fake" if settings.EMBEDDING_BACKEND == "fake" else settings.EMBEDDING_MODEL
    return Response(
        {
            "companies": Company.objects.count(),
            "products": Product.objects.count(),
            "chunks": KnowledgeChunk.objects.count(),
            "embedding_model": model,
            "embedding_dim": settings.EMBEDDING_DIM,
        }
    )
