from django.db import transaction

from .indexing import (
    reindex_company,
    reindex_product,
    reindex_product_fields,
    set_product_searchable,
)

# In every chunk header of the product (fields and documents) -> all chunks are rebuilt.
HEADER_FIELDS = ("name", "company_id")
# Only in the product-field chunks (category is in that header only).
TEXT_FIELDS = ("category", "summary", "description", "price", "features", "usage_guide", "faq")


def save_company(serializer):
    """Create/update a company and re-chunk it (and its products) atomically."""
    with transaction.atomic():
        company = serializer.save()
        reindex_company(company)
    return company


def save_product(serializer):
    """Save a product and re-embed only what changed (specs/05 §2.4).

    Large documents take tens of seconds to embed, so a price edit must not touch them.
    """
    instance = serializer.instance
    before = (
        {f: getattr(instance, f) for f in (*HEADER_FIELDS, *TEXT_FIELDS, "is_active")}
        if instance
        else None
    )
    with transaction.atomic():
        product = serializer.save()
        if before is None or any(getattr(product, f) != before[f] for f in HEADER_FIELDS):
            reindex_product(product)
        else:
            if any(getattr(product, f) != before[f] for f in TEXT_FIELDS):
                reindex_product_fields(product)
            if product.is_active != before["is_active"]:
                set_product_searchable(product)
    return product
