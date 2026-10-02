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
PostgreSQL 18 + pgvector
```

## 진행 상황

| Phase | 내용 | 상태 |
| --- | --- | --- |
| 0 | 요구 사항 정의 (`CLAUDE.md`, `specs/`) | ✅ 완료 |
| 1 | 기반 구성 (DB, Django, Vue, User 모델) | ✅ 완료 |
| 2 | 계정 (로그인, 기본 관리자, 비밀번호 변경) | ✅ 완료 |
| 3 | 시스템 설정 (API Key) | ⏳ 예정 |
| 4 | 지식 관리 (회사/제품 CRUD, 임베딩) | ⏳ 예정 |
| 5 | 챗봇 (RAG + Claude 스트리밍) | ⏳ 예정 |
| 6 | 마무리 | ⏳ 예정 |

## 실행 방법

요구 사항: PostgreSQL 18(로컬, 포트 5432), Python 3.12(`python3.12-venv`), Node.js 20+

### 1. 데이터베이스 (로컬 PostgreSQL 18 + pgvector, 최초 1회)

```bash
# 1) pgvector 설치 (PostgreSQL 18용)
sudo apt install -y postgresql-18-pgvector
# 2) template1에 vector 확장 생성 → 이후 만드는 DB(cs_agent, pytest의 test_cs_agent)에 자동 포함
sudo -u postgres psql -d template1 -c "CREATE EXTENSION IF NOT EXISTS vector;"
# 3) 앱 계정(CREATEDB: pytest가 테스트 DB를 만들 수 있도록)과 DB 생성
sudo -u postgres psql -c "CREATE ROLE cs_agent LOGIN PASSWORD 'cs_agent' CREATEDB;"
sudo -u postgres psql -c "CREATE DATABASE cs_agent OWNER cs_agent;"
# 확인
psql postgres://cs_agent:cs_agent@localhost:5432/cs_agent -c "\dx vector"
```

### 2. 백엔드 (Django, http://localhost:8000)

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
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

브라우저에서 http://localhost:5173 을 열면 "서버 연결: 정상"이 표시됩니다(채팅 화면은 Phase 3/5에서 구현).

### 관리자 로그인

- `migrate` 직후 관리자 계정이 없으면 기본 관리자(`admin` / `admin1234!`)가 자동 생성됩니다. 수동 실행: `python manage.py ensure_default_admin`
- 화면 상단 우측 **관리자 로그인** → 로그인 후 사용자 메뉴에서 **관리자 페이지**로 이동합니다.
- 기본 비밀번호 사용 중에는 경고 배너가 표시됩니다. **시스템 설정 → 비밀번호 변경**에서 바꿔 주세요.
- 같은 아이디로 5회 연속 실패하면 5분간 로그인이 차단되며, 로그인 요청은 IP당 분당 10회로 제한됩니다.

### 테스트 및 린트

```bash
cd backend && pytest && ruff check . && ruff format --check .
cd frontend && npm run test && npm run lint && npm run build
```

## 프로젝트 구조

```text
cs_agent/
├── specs/               # 요구 사항 문서
├── backend/             # Django + DRF
│   ├── config/          # settings, urls
│   ├── common/          # 공통 에러 형식, 권한(IsAdminRole), 페이지네이션, health API
│   ├── accounts/        # User(AbstractUser + role), 로그인/로그아웃/비밀번호 변경, 기본 관리자 생성
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
