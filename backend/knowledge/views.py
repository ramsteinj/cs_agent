from django.conf import settings
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action, api_view
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response

from common.audit import audit
from settings_app.models import SystemSetting

from . import services
from .documents import extract_text
from .indexing import reindex_all, reindex_product
from .models import Company, KnowledgeChunk, Product, ProductDocument
from .serializers import (
    CompanySerializer,
    DocumentTitleSerializer,
    DocumentUploadSerializer,
    ProductDocumentSerializer,
    ProductSerializer,
)


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

    def perform_destroy(self, instance):
        audit("company_deleted", self.request.user, id=instance.pk, name=instance.name)
        instance.delete()


def _parse_bool(value):
    return {"true": True, "1": True, "false": False, "0": False}.get(str(value).lower())


class ProductViewSet(viewsets.ModelViewSet):
    serializer_class = ProductSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ["name"]

    def get_queryset(self):
        queryset = (
            Product.objects.select_related("company")
            .annotate(
                chunk_count=Count("chunks", distinct=True),
                document_count=Count("documents", distinct=True),
            )
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

    def perform_destroy(self, instance):
        audit("product_deleted", self.request.user, id=instance.pk, name=instance.name)
        instance.delete()

    @action(detail=False, methods=["get"])
    def categories(self, request):
        categories = (
            Product.objects.exclude(category="")
            .order_by("category")
            .values_list("category", flat=True)
            .distinct()
        )
        return Response(list(categories))

    @action(
        detail=True,
        methods=["get", "post"],
        url_path="documents",
        parser_classes=[MultiPartParser],
    )
    def documents(self, request, pk=None):
        """GET: list documents. POST (multipart `file`): extract text, store, reindex."""
        product = self.get_object()
        if request.method == "GET":
            return Response(ProductDocumentSerializer(product.documents.all(), many=True).data)

        upload = DocumentUploadSerializer(data=request.data)
        upload.is_valid(raise_exception=True)
        file_name, file_type, file_size, text = extract_text(upload.validated_data["file"])
        with transaction.atomic():
            document = ProductDocument.objects.create(
                product=product,
                title=upload.validated_data.get("title", "").strip(),
                file_name=file_name,
                file_type=file_type,
                file_size=file_size,
                text=text,
            )
            reindex_product(product)
        audit(
            "product_document_uploaded",
            request.user,
            product=product.pk,
            document=document.pk,
            name=file_name,
        )
        return Response(ProductDocumentSerializer(document).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["patch", "delete"], url_path=r"documents/(?P<document_id>\d+)")
    def document_detail(self, request, pk=None, document_id=None):
        """PATCH: change the document title. DELETE: remove it. Both reindex the product."""
        product = self.get_object()
        document = get_object_or_404(ProductDocument, pk=document_id, product=product)
        if request.method == "PATCH":
            serializer = DocumentTitleSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            with transaction.atomic():
                document.title = serializer.validated_data["title"].strip()
                document.save(update_fields=["title", "updated_at"])
                reindex_product(product)
            audit(
                "product_document_renamed",
                request.user,
                product=product.pk,
                document=document.pk,
                title=document.title,
            )
            return Response(ProductDocumentSerializer(document).data)

        with transaction.atomic():
            document.delete()
            reindex_product(product)
        audit(
            "product_document_deleted",
            request.user,
            product=product.pk,
            document=document_id,
            name=document.file_name,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["POST"])
def reindex(request):
    chunks = reindex_all()
    audit("knowledge_reindexed", request.user, chunks=chunks)
    return Response({"chunks": chunks})


@api_view(["GET"])
def stats(request):
    model = "fake" if settings.EMBEDDING_BACKEND == "fake" else SystemSetting.load().embedding_model
    return Response(
        {
            "companies": Company.objects.count(),
            "products": Product.objects.count(),
            "chunks": KnowledgeChunk.objects.count(),
            "embedding_model": model,
            "embedding_dim": settings.EMBEDDING_DIM,
        }
    )
