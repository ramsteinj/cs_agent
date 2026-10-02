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
| 3 | 시스템 설정 (API Key 암호화 저장, 챗봇 설정, 채팅 활성 상태) | ✅ 완료 |
| 4 | 지식 관리 (회사/제품 CRUD, 임베딩·pgvector 색인, 검색, 재색인) | ✅ 완료 |
| 5 | 챗봇 (RAG + Claude 스트리밍, 채팅 UI) | ✅ 완료 |
| 6 | 마무리 (보안 설정, 감사 로그, 세션 정리, 모바일·접근성 점검) | ✅ 완료 |

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
pip install -r requirements.txt     # CPU 전용 PyTorch 포함 (약 1.5GB)
cp .env.example .env                # DJANGO_SECRET_KEY, DATABASE_URL, FIELD_ENCRYPTION_KEY 설정
# FIELD_ENCRYPTION_KEY 생성 (없거나 잘못되면 서버가 시작되지 않음):
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
python manage.py migrate
python manage.py runserver 8000
```

### 3. 프론트엔드 (Vue 3 + Vite, http://localhost:5173)

```bash
cd frontend
npm install
npm run dev                         # /api 요청은 Django(8000)로 프록시
```

브라우저에서 http://localhost:5173 을 열면 채팅 화면이 표시됩니다. API Key가 등록되기 전에는 "현재 상담 서비스를 준비 중입니다."가 표시되고 입력창이 비활성화됩니다.

### 고객 채팅

- 로그인 없이 질문하면 등록된 회사·제품 정보에서 관련 내용을 검색해 Claude가 답변을 스트리밍으로 보여 줍니다. 답변 아래에 참고한 회사·제품이 표시됩니다.
- Enter 전송, Shift+Enter 줄바꿈, 최대 1,000자. 같은 탭에서는 새로고침해도 대화가 유지되고, **새 대화** 버튼으로 초기화합니다.
- 직전 대화(최대 10개 메시지)를 함께 보내 "그거 가격은?" 같은 후속 질문을 이해합니다.
- 오류 시 "다시 시도" 버튼이 표시됩니다. IP당 분당 20회, 대화당 200개 메시지로 제한됩니다.
- 서버 시작 후 첫 질문은 임베딩 모델을 메모리에 올리느라 수 초 더 걸립니다.

### 관리자 로그인

- `migrate` 직후 관리자 계정이 없으면 기본 관리자(`admin` / `admin1234!`)가 자동 생성됩니다. 수동 실행: `python manage.py ensure_default_admin`
- 화면 상단 우측 **관리자 로그인** → 로그인 후 사용자 메뉴에서 **관리자 페이지**로 이동합니다.
- 기본 비밀번호 사용 중에는 경고 배너가 표시됩니다. **시스템 설정 → 비밀번호 변경**에서 바꿔 주세요.
- 같은 아이디로 5회 연속 실패하면 5분간 로그인이 차단되며, 로그인 요청은 IP당 분당 10회로 제한됩니다.

### 회사·제품 정보 관리 (지식)

- **관리자 페이지 → 회사 관리 / 제품 관리**에서 정보를 등록·수정·삭제합니다. 저장하면 내용을 청크로 나누고 임베딩을 만들어 pgvector(`KnowledgeChunk`)에 저장합니다.
- 회사를 삭제하면 소속 제품과 청크도 함께 삭제됩니다. **판매 중**을 끈 제품은 챗봇 답변 근거에서 제외됩니다.
- 임베딩 모델 `intfloat/multilingual-e5-small`(384차원)은 첫 사용 시 Hugging Face에서 자동으로 내려받습니다(약 470MB, `~/.cache/huggingface`).
- **시스템 설정 → 지식 색인**에서 통계를 보고 전체 재색인을 실행할 수 있습니다.
- 데모용 가상 데이터(회사 1개, 제품 3개): `python manage.py load_sample_knowledge` (다시 만들려면 `--reset`)

### Claude API Key 및 챗봇 설정

- **관리자 페이지 → 시스템 설정 → Claude API Key**에 Anthropic API Key를 입력하면, 저장 전에 Anthropic API로 유효성을 확인합니다.
- 키는 `FIELD_ENCRYPTION_KEY`로 암호화되어 PostgreSQL에 저장되며, 화면에는 `sk-ant-...abcd` 형태로만 표시됩니다. `FIELD_ENCRYPTION_KEY`를 바꾸면 기존 키를 복호화할 수 없으므로 다시 입력해야 합니다.
- 키를 등록하면 고객 채팅이 활성화되고, 삭제하면 즉시 비활성화됩니다.
- **챗봇 설정**에서 Claude 모델(`claude-opus-5-5` 기본, `claude-sonnet-5-5`, `claude-haiku-4-5`), 챗봇 이름, 환영 메시지, 추가 지시사항(최대 2,000자)을 바꿀 수 있습니다.

### 테스트 및 린트

```bash
cd backend && pytest && ruff check . && ruff format --check .
cd frontend && npm run test && npm run lint && npm run build
```

테스트는 Anthropic API를 호출하지 않으며(LLM은 mock), 임베딩은 결정적 가짜 백엔드(`EMBEDDING_BACKEND=fake`)를 씁니다.

## 운영 배포 참고

`DJANGO_DEBUG=False`이면 HTTPS 리다이렉트, HSTS, Secure 쿠키, `X-Frame-Options: DENY`가 켜집니다. TLS는 리버스 프록시(Nginx)에서 종료하고 `X-Forwarded-Proto`를 넘긴다고 가정합니다.

| 환경 변수 | 기본값 | 설명 |
| --- | --- | --- |
| `DJANGO_DEBUG` | `False` | 운영에서는 반드시 `False` |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1` | 서비스 도메인 |
| `DJANGO_NUM_PROXIES` | `0` | 앞단 신뢰 프록시 수. Nginx 1대 뒤라면 `1`. `0`이면 `X-Forwarded-For`를 무시(위조 방지) |
| `DJANGO_SECURE_SSL_REDIRECT` | `True` | 프록시가 이미 리다이렉트하면 `False` |
| `DJANGO_SECURE_HSTS_SECONDS` | `31536000` | HSTS 유지 시간 |
| `DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS` | `False` | 모든 서브도메인이 HTTPS일 때만 `True` |

- 배포 전 점검: `DJANGO_DEBUG=False python manage.py check --deploy`
- Nginx에서 `/api/chat/messages`는 SSE이므로 응답 버퍼링을 끕니다(서버가 `X-Accel-Buffering: no`를 보냄). 프론트엔드는 `npm run build`의 `dist/`를 정적 서빙하고, 모든 경로를 `index.html`로 돌려 SPA 라우팅을 지원합니다.
- **감사 로그**: 관리자 로그인 성공/실패, 로그아웃, 비밀번호 변경, API Key 등록/삭제, 설정 변경, 회사·제품 삭제, 전체 재색인이 `audit` 로거로 `... AUDIT event=... user=...` 형식으로 기록됩니다. 비밀번호와 API Key는 기록하지 않습니다.
- **Claude 호출 실패 로그**: `Claude API call failed (model=...): status=400 type=invalid_request_error request_id=req_...` 형식으로 남습니다. 요청 ID로 Anthropic Console 로그를 찾거나 지원팀에 문의할 수 있습니다. 예를 들어 크레딧 부족은 `status=400 type=invalid_request_error`로 나타납니다.
- **대화 보관 정책**: 마지막 활동 후 30일이 지난 대화를 지우려면 주기적으로 실행합니다. 예: `0 3 * * * cd /path/backend && .venv/bin/python manage.py cleanup_chat_sessions` (`--days N`, `--dry-run` 지원)

## 남은 작업

- 실제 Anthropic API Key로 [specs/05](specs/05-rag-pipeline.md) §5 답변 품질 체크리스트 확인
- 검색 거리 임계값 `RAG_MAX_DISTANCE` 조정: e5 모델은 관련·무관 질문 모두 코사인 거리 0.13~0.23 범위라 기본값 0.6으로는 무관한 문서가 걸러지지 않음 (답변은 시스템 프롬프트가 근거 없는 내용을 막지만, 출처 표시에 무관한 항목이 섞일 수 있음)

## 프로젝트 구조

```text
cs_agent/
├── specs/               # 요구 사항 문서
├── backend/             # Django + DRF
│   ├── config/          # settings, urls
│   ├── common/          # 공통 에러 형식(404/500 포함), 권한(IsAdminRole), 페이지네이션, 감사 로그, health API
│   ├── accounts/        # User(AbstractUser + role), 로그인/로그아웃/비밀번호 변경, 기본 관리자 생성
│   ├── knowledge/       # 회사·제품 CRUD, 청킹·임베딩·pgvector 색인, 벡터 검색
│   ├── chat/            # 챗봇 상태·세션·SSE 메시지 API, RAG 오케스트레이션, Claude 호출(llm.py)
│   └── settings_app/    # SystemSetting: 암호화된 API Key, 모델·챗봇 설정
└── frontend/            # Vue 3 + Vite + Bootstrap 5.0 SPA
    └── src/             # api/, stores/, router/, views/, components/, composables/, assets/
```

## 문서

- [CLAUDE.md](CLAUDE.md) — Claude Code 작업 규칙
- [specs/](specs/) — 상세 요구 사항
  - [00 개요·로드맵](specs/00-overview.md) · [01 기능 요구 사항](specs/01-functional-requirements.md) · [02 아키텍처](specs/02-architecture.md) · [03 데이터 모델](specs/03-data-model.md)
  - [04 API](specs/04-api.md) · [05 RAG 파이프라인](specs/05-rag-pipeline.md) · [06 프론트엔드](specs/06-frontend.md) · [07 보안](specs/07-security.md) · [08 개발·테스트](specs/08-dev-and-testing.md)
