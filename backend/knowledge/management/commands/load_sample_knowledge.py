from django.core.management.base import BaseCommand
from django.db import transaction

from knowledge.indexing import reindex_company
from knowledge.models import Company, Product

SAMPLE_COMPANY = {
    "name": "오케이테크 (샘플)",
    "description": (
        "오케이테크는 중소기업을 위한 클라우드 협업 도구를 만드는 가상의 소프트웨어 회사입니다. "
        "2018년에 설립되었으며 문서 관리, 일정 관리, 화상 회의 제품을 제공합니다."
    ),
    "website": "https://example.com",
    "phone": "02-1234-5678",
    "email": "support@example.com",
    "address": "서울특별시 강남구 테헤란로 123",
    "business_hours": "평일 09:00-18:00 (주말·공휴일 휴무)",
    "extra_info": (
        "환불 정책: 결제 후 7일 이내에는 전액 환불됩니다. 7일이 지나면 남은 기간에 대해 "
        "일할 계산하여 환불합니다.\n\n"
        "기술 지원: 이메일 문의는 영업일 기준 1일 이내에 답변합니다."
    ),
}

SAMPLE_PRODUCTS = [
    {
        "name": "오케이드라이브",
        "category": "문서 관리",
        "summary": "팀 문서를 안전하게 저장하고 공유하는 클라우드 드라이브",
        "description": (
            "오케이드라이브는 팀의 문서를 한곳에 모아 관리하는 클라우드 저장소입니다. "
            "폴더별 권한 설정과 버전 기록을 지원합니다."
        ),
        "price": "사용자당 월 5,000원 (1TB 저장 공간 포함)",
        "features": "폴더별 권한 설정\n파일 버전 기록 30일 보관\n외부 공유 링크와 만료일 설정",
        "usage_guide": "관리자 콘솔에서 팀원을 초대한 뒤, 공유 폴더를 만들고 권한을 지정합니다.",
        "faq": "Q. 저장 공간을 늘릴 수 있나요?\nA. 100GB 단위로 월 1,000원에 추가할 수 있습니다.",
        "is_active": True,
    },
    {
        "name": "오케이캘린더",
        "category": "일정 관리",
        "summary": "팀 일정과 회의실 예약을 함께 관리하는 캘린더",
        "description": (
            "오케이캘린더는 팀 공유 일정과 회의실 예약을 한 화면에서 관리합니다. "
            "구글 캘린더, 아웃룩 일정과 동기화할 수 있습니다."
        ),
        "price": "사용자당 월 3,000원",
        "features": "공유 캘린더\n회의실 예약과 중복 방지\n외부 캘린더 양방향 동기화",
        "usage_guide": "설정 > 연동 메뉴에서 구글 또는 아웃룩 계정을 연결합니다.",
        "faq": "Q. 무료 체험이 있나요?\nA. 14일 무료 체험을 제공합니다.",
        "is_active": True,
    },
    {
        "name": "오케이미팅",
        "category": "화상 회의",
        "summary": "판매 종료된 화상 회의 서비스",
        "description": "오케이미팅은 최대 50명이 참여하는 화상 회의 서비스였습니다.",
        "price": "판매 종료",
        "features": "화면 공유\n회의 녹화",
        "usage_guide": "",
        "faq": "",
        "is_active": False,
    },
]


class Command(BaseCommand):
    help = "Create a fictional sample company with 3 products and index them (dev/demo)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset", action="store_true", help="Delete and recreate the sample data."
        )

    def handle(self, *args, **options):
        name = SAMPLE_COMPANY["name"]
        existing = Company.objects.filter(name=name)
        if existing.exists():
            if not options["reset"]:
                self.stdout.write("Sample data already exists. Use --reset to recreate it.")
                return
            existing.delete()

        with transaction.atomic():
            company = Company.objects.create(**SAMPLE_COMPANY)
            for product in SAMPLE_PRODUCTS:
                Product.objects.create(company=company, **product)
            chunks = reindex_company(company)

        self.stdout.write(
            self.style.SUCCESS(
                f"Created '{name}' with {len(SAMPLE_PRODUCTS)} products ({chunks} chunks)."
            )
        )
