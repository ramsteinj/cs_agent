from django.db import transaction

from .indexing import reindex_company, reindex_product


def save_company(serializer):
    """Create/update a company and re-chunk it (and its products) atomically."""
    with transaction.atomic():
        company = serializer.save()
        reindex_company(company)
    return company


def save_product(serializer):
    with transaction.atomic():
        product = serializer.save()
        reindex_product(product)
    return product
