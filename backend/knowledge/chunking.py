"""Turn Company / Product records into search chunks (specs/05-rag-pipeline.md §2.1-2.2).

Pure functions: no DB, no embeddings.
"""

import re

_SENTENCE_END = re.compile(r"(?<=[.!?。])\s+|\n")


def _field_lines(pairs):
    """'label: value' lines, skipping empty values."""
    return [f"{label}: {value.strip()}" for label, value in pairs if value and value.strip()]


def company_document(company):
    """Return (header, body) for a Company."""
    header = f"[회사] {company.name}"
    contact = " / ".join(
        _field_lines(
            [("웹사이트", company.website), ("전화", company.phone), ("이메일", company.email)]
        )
    )
    location = " / ".join(
        _field_lines([("주소", company.address), ("운영 시간", company.business_hours)])
    )
    lines = _field_lines([("소개", company.description)])
    lines += [line for line in (contact, location) if line]
    lines += _field_lines([("기타 안내", company.extra_info)])
    return header, "\n".join(lines)


def product_document(product):
    """Return (header, body) for a Product."""
    header = f"[제품] {product.name} ({product.company.name})"
    if product.category:
        header += f" / 카테고리: {product.category}"
    lines = _field_lines(
        [
            ("요약", product.summary),
            ("설명", product.description),
            ("가격", product.price),
            ("주요 기능", product.features),
            ("사용 방법", product.usage_guide),
            ("FAQ", product.faq),
        ]
    )
    return header, "\n".join(lines)


def _sentences(body):
    """Split into sentences, keeping paragraph breaks as boundaries."""
    parts = []
    for paragraph in re.split(r"\n\s*\n", body):
        parts += [s.strip() for s in _SENTENCE_END.split(paragraph) if s and s.strip()]
    return parts


def _hard_split(text, max_chars, overlap):
    step = max_chars - overlap
    return [text[i : i + max_chars] for i in range(0, max(len(text) - overlap, 1), step)]


def _tail(pieces, overlap):
    """Trailing pieces whose combined length fits in `overlap` chars."""
    tail, size = [], 0
    for piece in reversed(pieces):
        if size + len(piece) + 1 > overlap:
            break
        tail.insert(0, piece)
        size += len(piece) + 1
    return tail


def chunk_text(header, body, max_chars=500, overlap=100):
    """Split body into ~max_chars chunks with ~overlap chars carried over.

    Every chunk is prefixed with the header line (header not counted in max_chars).
    """
    if overlap >= max_chars:
        raise ValueError("overlap must be smaller than max_chars")

    pieces = []
    for sentence in _sentences(body):
        pieces += (
            _hard_split(sentence, max_chars, overlap) if len(sentence) > max_chars else [sentence]
        )

    chunks, current = [], []
    for piece in pieces:
        candidate = " ".join([*current, piece])
        if current and len(candidate) > max_chars:
            chunks.append(" ".join(current))
            current = _tail(current, overlap)
            if len(" ".join([*current, piece])) > max_chars:
                current = []
        current.append(piece)
    if current:
        chunks.append(" ".join(current))

    if not chunks:
        return [header]
    return [f"{header}\n{chunk}" for chunk in chunks]
