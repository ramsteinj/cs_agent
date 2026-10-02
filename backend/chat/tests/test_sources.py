from types import SimpleNamespace

import pytest

from chat.sources import select_sources

COMPANY = SimpleNamespace(
    name="오케이테크 (샘플)",
    phone="02-1234-5678",
    email="support@example.com",
    website="https://example.com",
)


def _product_chunk(pk, name):
    return SimpleNamespace(
        source_type="product",
        source_id=pk,
        product_id=pk,
        product=SimpleNamespace(name=name),
        company=COMPANY,
    )


def _company_chunk():
    return SimpleNamespace(
        source_type="company", source_id=1, product_id=None, product=None, company=COMPANY
    )


DRIVE = _product_chunk(1, "오케이드라이브")
CALENDAR = _product_chunk(2, "오케이캘린더")
COMPANY_CHUNK = _company_chunk()


def titles(chunks, answer, limit=3):
    return [s["title"] for s in select_sources(chunks, answer, limit)]


# Answers below are trimmed versions of real Claude Opus 5.5 answers (2026-10-02).
def test_price_answer_drops_the_unmentioned_product():
    answer = (
        "오케이드라이브는 요금제에 따라 가격이 다릅니다.\n- 기본 요금제: 사용자당 월 5,000원\n"
        "자세한 상담은 아래로 문의해 주세요.\n- 전화: 02-1234-5678 (평일 09:00-18:00)"
    )

    assert titles([DRIVE, COMPANY_CHUNK, CALENDAR], answer) == [
        "오케이드라이브",
        "오케이테크 (샘플)",
    ]


def test_english_answer_with_korean_name_in_parentheses():
    answer = "OK Calendar (오케이캘린더) pricing: 3,000 KRW per user. Email: support@example.com"

    assert titles([CALENDAR, DRIVE, COMPANY_CHUNK], answer) == ["오케이캘린더", "오케이테크 (샘플)"]


def test_company_matched_by_name_without_bracketed_note():
    assert titles([COMPANY_CHUNK, DRIVE], "오케이테크의 환불 정책은 7일 이내입니다.") == [
        "오케이테크 (샘플)"
    ]
    assert titles([DRIVE, COMPANY_CHUNK], "오케이테크의 정책입니다.") == [
        "오케이드라이브",
        "오케이테크 (샘플)",
    ]


@pytest.mark.parametrize(
    "answer",
    [
        "문의: 0212345678",
        "전화 02 1234 5678로 연락 주세요",
        "support@EXAMPLE.com 으로 메일 주세요",
        "자세한 내용은 example.com 을 참고하세요",
    ],
)
def test_company_matched_by_contact_details(answer):
    assert titles([CALENDAR, COMPANY_CHUNK], answer) == ["오케이캘린더", "오케이테크 (샘플)"]


def test_unrelated_numbers_do_not_match_the_phone():
    assert "오케이테크 (샘플)" not in titles(
        [DRIVE, COMPANY_CHUNK], "오케이드라이브 5,000원, 1,234명"
    )


def test_names_ignore_spacing():
    # CALENDAR is not the top hit, so it is shown only because "오케이 캘린더" matches.
    assert titles([DRIVE, CALENDAR], "오케이 캘린더는 14일 무료 체험을 제공합니다.") == [
        "오케이드라이브",
        "오케이캘린더",
    ]


def test_most_relevant_source_is_always_shown():
    # Real Opus 5.5 answer to "오케이드라이브에서 이전 버전으로 되돌릴 수 있나요?"
    # (the manual chunk was the top hit; the answer never repeats the product name)
    manual = SimpleNamespace(
        source_type="product",
        source_id=1,
        product_id=1,
        document_id=8,
        document=SimpleNamespace(display_name="사용자 매뉴얼"),
        product=SimpleNamespace(name="오케이드라이브"),
        company=COMPANY,
    )
    answer = (
        "네, 가능합니다. 파일 정보에서 30일 이내 버전으로 복원할 수 있습니다. 전화: 02-1234-5678"
    )

    assert titles([manual, CALENDAR, COMPANY_CHUNK], answer) == [
        "오케이드라이브 · 사용자 매뉴얼",
        "오케이테크 (샘플)",
    ]


def test_translated_names_keep_only_the_most_relevant_source():
    assert titles([CALENDAR, DRIVE], "It has a 14-day free trial.") == ["오케이캘린더"]


def test_keeps_retrieval_order_dedupes_and_limits():
    second_drive_chunk = _product_chunk(1, "오케이드라이브")
    answer = "오케이캘린더와 오케이드라이브, 오케이테크 모두 안내드립니다."

    assert titles([CALENDAR, DRIVE, second_drive_chunk, COMPANY_CHUNK], answer, limit=2) == [
        "오케이캘린더",
        "오케이드라이브",
    ]


def test_empty_inputs():
    assert select_sources([], "아무 답", 3) == []
    assert select_sources([DRIVE], "오케이드라이브", 0) == []


def test_document_chunk_source_shows_the_document_title():
    guide = SimpleNamespace(display_name="빠른 설치 가이드")
    chunk = SimpleNamespace(
        source_type="product",
        source_id=1,
        product_id=1,
        document_id=7,
        document=guide,
        product=SimpleNamespace(name="오케이드라이브"),
        company=COMPANY,
    )

    assert titles([chunk, DRIVE], "오케이드라이브는 3단계로 설치합니다.") == [
        "오케이드라이브 · 빠른 설치 가이드"
    ]


def test_same_name_products_show_their_category():
    tv = SimpleNamespace(
        source_type="product",
        source_id=5,
        product_id=5,
        document_id=None,
        product=SimpleNamespace(name="SC95A", category="Quick Install Guide"),
        company=COMPANY,
    )
    manual = SimpleNamespace(
        source_type="product",
        source_id=6,
        product_id=6,
        document_id=9,
        document=SimpleNamespace(display_name="Smart TV E-Manual"),
        product=SimpleNamespace(name="SC95A", category="E-Manual"),
        company=COMPANY,
    )

    sources = select_sources([manual, tv], "SC95A의 설치 방법입니다.", 3, frozenset({5, 6}))

    assert [s["title"] for s in sources] == [
        "SC95A (E-Manual) · Smart TV E-Manual",
        "SC95A (Quick Install Guide)",
    ]
