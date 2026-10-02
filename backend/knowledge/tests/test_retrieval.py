import pytest

from knowledge.retrieval import search

from .factories import make_company, make_product


@pytest.fixture
def catalog(db):
    company = make_company(name="오케이테크", description="협업 소프트웨어 회사입니다.")
    drive = make_product(
        company,
        name="드라이브",
        description="문서 저장 클라우드 드라이브 서비스",
        price="월 5,000원",
    )
    calendar = make_product(
        company,
        name="캘린더",
        description="일정 관리 회의실 예약 캘린더",
        price="월 3,000원",
    )
    retired = make_product(
        company,
        name="미팅",
        description="화상 회의 녹화 서비스",
        is_active=False,
    )
    return {"company": company, "drive": drive, "calendar": calendar, "retired": retired}


def test_most_relevant_chunk_comes_first(catalog):
    results = search("일정 관리 캘린더 회의실 예약", max_distance=1.0)

    assert results[0].product_id == catalog["calendar"].pk
    assert results == sorted(results, key=lambda chunk: chunk.distance)


def test_inactive_products_are_excluded(catalog):
    results = search("화상 회의 녹화 서비스", max_distance=2.0)

    assert catalog["retired"].pk not in {chunk.product_id for chunk in results}


def test_max_distance_filters_unrelated_chunks(catalog):
    assert search("전혀 관계없는 질문 xyz", max_distance=0.1) == []


def test_top_k_limit(catalog):
    assert len(search("서비스", top_k=1, max_distance=2.0)) == 1


def test_blank_query_returns_nothing(catalog):
    assert search("   ") == []
