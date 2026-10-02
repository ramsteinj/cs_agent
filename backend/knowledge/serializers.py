from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from .models import Company, Product


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
            "chunk_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]
        validators = []  # (company, name) uniqueness is checked in validate() with a field error

    def get_chunk_count(self, obj):
        count = getattr(obj, "chunk_count", None)
        return obj.chunks.count() if count is None else count

    def validate(self, attrs):
        company = attrs.get("company", getattr(self.instance, "company", None))
        name = attrs.get("name", getattr(self.instance, "name", None))
        duplicates = Product.objects.filter(company=company, name=name)
        if self.instance:
            duplicates = duplicates.exclude(pk=self.instance.pk)
        if duplicates.exists():
            raise serializers.ValidationError(
                {"name": ["이 회사에 같은 이름의 제품이 이미 있습니다."]}, code="unique"
            )
        return attrs
