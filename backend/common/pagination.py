from rest_framework.pagination import PageNumberPagination


class StandardPagination(PageNumberPagination):
    page_size = 20
    # Lets admin dropdowns (e.g. company select) fetch a larger page.
    page_size_query_param = "page_size"
    max_page_size = 100
