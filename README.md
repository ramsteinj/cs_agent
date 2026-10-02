# cs_agent

Customer support agent created by vibe coding.

회사·제품 정보를 기반으로 고객 문의에 답하는 **RAG 기반 Customer Support Chatbot**입니다.
관리자가 등록한 회사/제품 정보를 pgvector에 임베딩으로 저장하고, 고객 질문과 관련된 정보를 검색해 Claude API로 답변을 생성합니다.

## 주요 기능

### 고객

- 로그인 없이 채팅으로 회사/제품 문의 (스트리밍 답변, 대화 맥락 유지)
- 관리자가 API Key를 등록하지 않은 경우 채팅 비활성화

### 관리자

- 화면 상단 우측 ID/비밀번호 로그인
- 최초 실행 시 기본 관리자 계정 자동 생성 (`admin` / `admin1234!` — 로그인 후 반드시 변경)
- 회사·제품 정보 생성/수정/삭제 (pgvector 자동 색인)
- Claude API Key 등록 (PostgreSQL에 암호화 저장), 모델·챗봇 설정

## 아키텍처

```text
Vue.js 3 SPA (Vite, Bootstrap 5.0)
        │  HTTP / JSON (채팅은 SSE)
        v
Django + Django REST Framework ── Claude API (anthropic SDK)
        │  Django ORM               └ sentence-transformers (로컬 임베딩)
        v
PostgreSQL 16 + pgvector
```

## 진행 상황

| Phase | 내용 | 상태 |
| --- | --- | --- |
| 0 | 요구 사항 정의 (`CLAUDE.md`, `specs/`) | ✅ 완료 |
| 1 | 기반 구성 (DB, Django, Vue) | ⏳ 예정 |
| 2 | 계정 (로그인, 기본 관리자) | ⏳ 예정 |
| 3 | 시스템 설정 (API Key) | ⏳ 예정 |
| 4 | 지식 관리 (회사/제품 CRUD, 임베딩) | ⏳ 예정 |
| 5 | 챗봇 (RAG + Claude 스트리밍) | ⏳ 예정 |
| 6 | 마무리 | ⏳ 예정 |

## 실행 방법

> 구현이 진행되면 이 섹션을 갱신합니다. 예정된 절차는 [specs/08-dev-and-testing.md](specs/08-dev-and-testing.md)를 참고하세요.

요구 사항: Docker, Python 3.12, Node.js 20+

```bash
docker compose up -d db

cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # DJANGO_SECRET_KEY, FIELD_ENCRYPTION_KEY 설정
python manage.py migrate
python manage.py runserver 8000

cd ../frontend
npm install
npm run dev                 # http://localhost:5173
```

## 문서

- [CLAUDE.md](CLAUDE.md) — Claude Code 작업 규칙
- [specs/](specs/) — 상세 요구 사항
  - [00 개요·로드맵](specs/00-overview.md) · [01 기능 요구 사항](specs/01-functional-requirements.md) · [02 아키텍처](specs/02-architecture.md) · [03 데이터 모델](specs/03-data-model.md)
  - [04 API](specs/04-api.md) · [05 RAG 파이프라인](specs/05-rag-pipeline.md) · [06 프론트엔드](specs/06-frontend.md) · [07 보안](specs/07-security.md) · [08 개발·테스트](specs/08-dev-and-testing.md)
