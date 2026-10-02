"""Pick the sources an answer actually used (specs/05 §4.4).

Retrieval always returns the top-K chunks, and with e5 embeddings unrelated chunks are
nearly as close as relevant ones, so listing every retrieved chunk shows products the
answer never mentioned. A retrieved source is shown only if the answer refers to it:
  - product chunk: the product name appears in the answer
  - company chunk: the company name, phone number, email or website appears
If nothing matches (e.g. names translated in an English answer), the most relevant
retrieved source is shown alone.
"""

import re
from urllib.parse import urlparse

_BRACKETED = re.compile(r"\s*[(\[（][^)\]）]*[)\]）]\s*")
_PHONE_LIKE = re.compile(r"\+?\d[\d\-.\s()]{5,}\d")
MIN_NAME_LENGTH = 2


def _norm(text):
    return re.sub(r"\s+", "", text or "").casefold()


def _name_variants(name):
    """Full name and the name without bracketed notes: "오케이테크 (샘플)" -> "오케이테크"."""
    variants = {_norm(name), _norm(_BRACKETED.sub(" ", name or ""))}
    return {v for v in variants if len(v) >= MIN_NAME_LENGTH}


def _phone_numbers(text):
    return {re.sub(r"\D", "", match) for match in _PHONE_LIKE.findall(text or "")}


def _host(url):
    host = urlparse(url if "//" in (url or "") else f"//{url}").netloc
    return host.casefold().removeprefix("www.")


class _Answer:
    def __init__(self, text):
        self.norm = _norm(text)
        self.phones = _phone_numbers(text)

    def mentions_any(self, values):
        return any(value in self.norm for value in values)

    def mentions_phone(self, phone):
        digits = re.sub(r"\D", "", phone or "")
        return len(digits) >= 7 and any(digits in found for found in self.phones)


def _is_used(chunk, answer):
    if chunk.product_id:
        return answer.mentions_any(_name_variants(chunk.product.name))
    company = chunk.company
    contacts = {_norm(company.email)} if company.email else set()
    host = _host(company.website) if company.website else ""
    if host:
        contacts.add(host)
    return (
        answer.mentions_any(_name_variants(company.name))
        or answer.mentions_any(contacts)
        or answer.mentions_phone(company.phone)
    )


def _source(chunk):
    title = chunk.product.name if chunk.product_id else chunk.company.name
    return {"type": chunk.source_type, "id": chunk.source_id, "title": title}


def select_sources(chunks, answer_text, limit):
    """Sources used by the answer, in retrieval (relevance) order, at most `limit`."""
    if limit <= 0 or not chunks:
        return []
    first_chunk_per_source = {}
    for chunk in chunks:  # chunks are nearest first
        first_chunk_per_source.setdefault((chunk.source_type, chunk.source_id), chunk)
    candidates = list(first_chunk_per_source.values())

    answer = _Answer(answer_text)
    used = [chunk for chunk in candidates if _is_used(chunk, answer)] or candidates[:1]
    return [_source(chunk) for chunk in used[:limit]]
