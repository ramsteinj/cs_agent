from django.conf import settings
from django.db import models
from pgvector.django import HnswIndex, VectorField

from common.models import TimeStampedModel


class Company(TimeStampedModel):
    name = models.CharField(max_length=200, unique=True)
    description = models.TextField()
    website = models.URLField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    address = models.CharField(max_length=300, blank=True)
    business_hours = models.CharField(max_length=200, blank=True)
    extra_info = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Product(TimeStampedModel):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="products")
    name = models.CharField(max_length=200)
    category = models.CharField(max_length=100, blank=True, db_index=True)
    summary = models.CharField(max_length=500, blank=True)
    description = models.TextField(blank=True)  # optional: documents can carry the content
    price = models.CharField(max_length=100, blank=True)
    features = models.TextField(blank=True)
    usage_guide = models.TextField(blank=True)
    faq = models.TextField(blank=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "name"], name="uniq_product_name_per_company"
            )
        ]

    def __str__(self):
        return self.name


class ProductDocument(TimeStampedModel):
    """Text extracted from an uploaded .txt / .docx / .pdf (the file itself is not kept)."""

    class FileType(models.TextChoices):
        TXT = "txt", "Text"
        DOCX = "docx", "MS Word"
        PDF = "pdf", "PDF"

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="documents")
    file_name = models.CharField(max_length=255)
    file_type = models.CharField(max_length=10, choices=FileType.choices)
    file_size = models.PositiveIntegerField()
    text = models.TextField()

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self):
        return self.file_name


class KnowledgeChunk(TimeStampedModel):
    class SourceType(models.TextChoices):
        COMPANY = "company", "회사"
        PRODUCT = "product", "제품"

    source_type = models.CharField(max_length=10, choices=SourceType.choices)
    source_id = models.PositiveIntegerField()
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="chunks")
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, null=True, blank=True, related_name="chunks"
    )
    chunk_index = models.PositiveIntegerField()
    content = models.TextField()
    embedding = VectorField(dimensions=settings.EMBEDDING_DIM)
    embedding_model = models.CharField(max_length=200)
    is_searchable = models.BooleanField(default=True)

    class Meta:
        ordering = ["source_type", "source_id", "chunk_index"]
        indexes = [
            HnswIndex(
                name="chunk_embedding_hnsw",
                fields=["embedding"],
                m=16,
                ef_construction=64,
                opclasses=["vector_cosine_ops"],
            ),
            models.Index(fields=["source_type", "source_id"], name="chunk_source_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["source_type", "source_id", "chunk_index"], name="uniq_chunk_per_source"
            )
        ]

    def __str__(self):
        return f"{self.source_type}:{self.source_id}#{self.chunk_index}"
