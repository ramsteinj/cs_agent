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
| 1 | 기반 구성 (DB, Django, Vue, User 모델) | ✅ 완료 |
| 2 | 계정 (로그인, 기본 관리자) | ⏳ 예정 |
| 3 | 시스템 설정 (API Key) | ⏳ 예정 |
| 4 | 지식 관리 (회사/제품 CRUD, 임베딩) | ⏳ 예정 |
| 5 | 챗봇 (RAG + Claude 스트리밍) | ⏳ 예정 |
| 6 | 마무리 | ⏳ 예정 |

## 실행 방법

요구 사항: Docker, Python 3.12, Node.js 20+

### 1. 데이터베이스 (PostgreSQL 16 + pgvector)

```bash
docker compose up -d db
```

호스트의 5432 포트가 이미 사용 중이면 루트에 `.env`를 만들어 다른 포트를 지정합니다. 이 경우 `backend/.env`의 `DATABASE_URL` 포트도 같게 맞춥니다.

```bash
echo "POSTGRES_PORT=5433" > .env
```

### 2. 백엔드 (Django, http://localhost:8000)

```bash
cd backend
python3.12 -m venv .venv            # python3.12-venv가 없으면: uv venv --python 3.12 .venv
source .venv/bin/activate
pip install -r requirements.txt     # uv 사용 시: uv pip install -r requirements.txt
cp .env.example .env                # DJANGO_SECRET_KEY, DATABASE_URL 설정
python manage.py migrate
python manage.py runserver 8000
```

### 3. 프론트엔드 (Vue 3 + Vite, http://localhost:5173)

```bash
cd frontend
npm install
npm run dev                         # /api 요청은 Django(8000)로 프록시
```

브라우저에서 http://localhost:5173 을 열면 "서버 연결: 정상"이 표시됩니다. 이 화면은 Phase 1 연결 확인용이며, 이후 Phase에서 채팅 화면으로 바뀝니다.

### 테스트 및 린트

```bash
cd backend && pytest && ruff check . && ruff format --check .
cd frontend && npm run test && npm run lint && npm run build
```

## 프로젝트 구조

```text
cs_agent/
├── docker-compose.yml   # PostgreSQL 16 + pgvector
├── specs/               # 요구 사항 문서
├── backend/             # Django + DRF
│   ├── config/          # settings, urls
│   ├── common/          # 공통 에러 형식, 권한(IsAdminRole), 페이지네이션, health API
│   ├── accounts/        # User(AbstractUser + role)
│   ├── knowledge/       # (Phase 4) 회사·제품, pgvector
│   ├── chat/            # (Phase 3, 5) 챗봇
│   └── settings_app/    # (Phase 3) API Key 등 시스템 설정
└── frontend/            # Vue 3 + Vite + Bootstrap 5.0 SPA
    └── src/             # api/, router/, views/, assets/
```

## 문서

- [CLAUDE.md](CLAUDE.md) — Claude Code 작업 규칙
- [specs/](specs/) — 상세 요구 사항
  - [00 개요·로드맵](specs/00-overview.md) · [01 기능 요구 사항](specs/01-functional-requirements.md) · [02 아키텍처](specs/02-architecture.md) · [03 데이터 모델](specs/03-data-model.md)
  - [04 API](specs/04-api.md) · [05 RAG 파이프라인](specs/05-rag-pipeline.md) · [06 프론트엔드](specs/06-frontend.md) · [07 보안](specs/07-security.md) · [08 개발·테스트](specs/08-dev-and-testing.md)
