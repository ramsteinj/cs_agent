from knowledge.indexing import reindex_company, reindex_product
from knowledge.models import Company, Product


def make_company(name="오케이테크", index=True, **fields):
    data = {"description": "클라우드 협업 도구를 만드는 회사입니다.", "phone": "02-123-4567"}
    data.update(fields)
    company = Company.objects.create(name=name, **data)
    if index:
        reindex_company(company)
    return company


def make_product(company, name="오케이드라이브", index=True, **fields):
    data = {"description": "팀 문서를 저장하는 클라우드 드라이브입니다.", "price": "월 5,000원"}
    data.update(fields)
    product = Product.objects.create(company=company, name=name, **data)
    if index:
        reindex_product(product)
    return product
