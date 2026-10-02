from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from .models import Company, Product, ProductDocument


class CompanySerializer(serializers.ModelSerializer):
    name = serializers.CharField(
        max_length=200,
        validators=[
            UniqueValidator(queryset=Company.objects.all(), message="이미 등록된 회사명입니다.")
        ],
    )
    product_count = serializers.SerializerMethodField()
    chunk_count = serializers.SerializerMethodField()

    class Meta:
        model = Company
        fields = [
            "id",
            "name",
            "description",
            "website",
            "phone",
            "email",
            "address",
            "business_hours",
            "extra_info",
            "product_count",
            "chunk_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def get_product_count(self, obj):
        count = getattr(obj, "product_count", None)
        return obj.products.count() if count is None else count

    def get_chunk_count(self, obj):
        count = getattr(obj, "chunk_count", None)
        return obj.chunks.filter(product__isnull=True).count() if count is None else count


class ProductSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source="company.name", read_only=True)
    document_count = serializers.SerializerMethodField()
    chunk_count = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id",
            "company",
            "company_name",
            "name",
            "category",
            "summary",
            "description",
            "price",
            "features",
            "usage_guide",
            "faq",
            "is_active",
            "document_count",
            "chunk_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]
        validators = []  # (company, name) uniqueness is checked in validate() with a field error

    def get_chunk_count(self, obj):
        count = getattr(obj, "chunk_count", None)
        return obj.chunks.count() if count is None else count

    def get_document_count(self, obj):
        count = getattr(obj, "document_count", None)
        return obj.documents.count() if count is None else count

    def validate(self, attrs):
        company = attrs.get("company", getattr(self.instance, "company", None))
        name = attrs.get("name", getattr(self.instance, "name", None))
        category = attrs.get("category", getattr(self.instance, "category", ""))
        duplicates = Product.objects.filter(company=company, name=name, category=category)
        if self.instance:
            duplicates = duplicates.exclude(pk=self.instance.pk)
        if duplicates.exists():
            raise serializers.ValidationError(
                {
                    "name": [
                        "이 회사에 이름과 카테고리가 같은 제품이 이미 있습니다. "
                        "카테고리를 다르게 지정해 주세요."
                    ]
                },
                code="unique",
            )
        return attrs


class ProductDocumentSerializer(serializers.ModelSerializer):
    """Document metadata only: the full extracted text is not returned."""

    PREVIEW_CHARS = 200

    char_count = serializers.SerializerMethodField()
    preview = serializers.SerializerMethodField()
    display_name = serializers.CharField(read_only=True)

    class Meta:
        model = ProductDocument
        fields = [
            "id",
            "title",
            "display_name",
            "file_name",
            "file_type",
            "file_size",
            "char_count",
            "preview",
            "created_at",
        ]
        read_only_fields = fields

    def get_char_count(self, obj):
        return len(obj.text)

    def get_preview(self, obj):
        return obj.text[: self.PREVIEW_CHARS]


class DocumentUploadSerializer(serializers.Serializer):
    file = serializers.FileField(allow_empty_file=False)
    title = serializers.CharField(max_length=200, required=False, allow_blank=True)


class DocumentTitleSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=200, allow_blank=True)
