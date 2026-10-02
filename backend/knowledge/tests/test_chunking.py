from types import SimpleNamespace

import pytest

from knowledge.chunking import chunk_text, company_document, product_document

HEADER = "[제품] 테스트 (회사)"


def _company(**overrides):
    fields = dict(
        name="오케이테크",
        description="소개 문장입니다.",
        website="",
        phone="02-1",
        email="",
        address="",
        business_hours="평일 9-18",
        extra_info="",
    )
    fields.update(overrides)
    return SimpleNamespace(**fields)


def test_company_document_skips_empty_fields():
    header, body = company_document(_company())

    assert header == "[회사] 오케이테크"
    assert body.splitlines() == ["소개: 소개 문장입니다.", "전화: 02-1", "운영 시간: 평일 9-18"]


def test_product_document_header_includes_company_and_category():
    product = SimpleNamespace(
        name="드라이브",
        company=SimpleNamespace(name="오케이테크"),
        category="문서",
        summary="",
        description="설명",
        price="월 5,000원",
        features="",
        usage_guide="",
        faq="",
    )

    header, body = product_document(product)

    assert header == "[제품] 드라이브 (오케이테크) / 카테고리: 문서"
    assert body == "설명: 설명\n가격: 월 5,000원"


def test_product_document_without_category():
    product = SimpleNamespace(
        name="드라이브",
        company=SimpleNamespace(name="오케이"),
        category="",
        summary="",
        description="d",
        price="",
        features="",
        usage_guide="",
        faq="",
    )

    assert product_document(product)[0] == "[제품] 드라이브 (오케이)"


def test_short_body_is_one_chunk_with_header():
    assert chunk_text(HEADER, "짧은 내용입니다.") == [f"{HEADER}\n짧은 내용입니다."]


def test_empty_body_still_yields_header_chunk():
    assert chunk_text(HEADER, "") == [HEADER]


def test_long_body_is_split_within_limit_and_every_chunk_has_header():
    sentences = [f"{i}번째 문장은 제품의 특징을 설명하는 문장입니다." for i in range(60)]

    chunks = chunk_text(HEADER, " ".join(sentences), max_chars=200, overlap=50)

    assert len(chunks) > 1
    for chunk in chunks:
        header, body = chunk.split("\n", 1)
        assert header == HEADER
        assert len(body) <= 200


def test_consecutive_chunks_overlap():
    sentences = [f"문장{i:02d} 내용입니다." for i in range(40)]

    chunks = [c.split("\n", 1)[1] for c in chunk_text(HEADER, " ".join(sentences), 120, 40)]

    for previous, current in zip(chunks, chunks[1:], strict=False):
        first_sentence = current.split(". ")[0]
        assert first_sentence in previous


def test_all_sentences_are_kept():
    sentences = [f"고유문장{i:03d}." for i in range(80)]

    joined = "\n".join(chunk_text(HEADER, " ".join(sentences), 150, 30))

    for sentence in sentences:
        assert sentence in joined


def test_oversized_sentence_is_hard_split():
    long_sentence = "가" * 1200

    chunks = chunk_text(HEADER, long_sentence, max_chars=500, overlap=100)

    assert all(len(c.split("\n", 1)[1]) <= 500 for c in chunks)
    assert len(chunks) >= 3


def test_overlap_must_be_smaller_than_max():
    with pytest.raises(ValueError):
        chunk_text(HEADER, "x", max_chars=100, overlap=100)
