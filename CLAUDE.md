# CLAUDE.md

RAG 기반 Customer Support Chatbot (`cs_agent`). 이 파일은 Claude Code가 이 저장소에서 작업할 때 따라야 할 규칙이다.
상세 요구 사항은 `specs/` 폴더가 기준(Single Source of Truth)이며, 이 파일과 specs가 충돌하면 specs를 따른다.

## 문서 맵

| 파일 | 내용 |
|---|---|
| [specs/00-overview.md](specs/00-overview.md) | 제품 개요, 용어, 범위, 구현 로드맵(Phase) |
| [specs/01-functional-requirements.md](specs/01-functional-requirements.md) | 사용자/관리자 기능 요구 사항 + 인수 조건 |
| [specs/02-architecture.md](specs/02-architecture.md) | 시스템 구성, 디렉터리 구조, 기술 스택 버전 |
| [specs/03-data-model.md](specs/03-data-model.md) | Django 모델, pgvector 스키마, 마이그레이션 |
| [specs/04-api.md](specs/04-api.md) | REST/JSON API 명세 (요청/응답/에러) |
| [specs/05-rag-pipeline.md](specs/05-rag-pipeline.md) | 청킹, 임베딩, 검색, Claude 호출, 프롬프트 |
| [specs/06-frontend.md](specs/06-frontend.md) | Vue SPA 화면, 라우팅, 상태 관리, UI 규칙 |
| [specs/07-security.md](specs/07-security.md) | 인증/인가, API Key 암호화, 입력 검증 |
| [specs/08-dev-and-testing.md](specs/08-dev-and-testing.md) | 로컬 개발 환경, 환경 변수, 테스트 전략 |

작업 시작 전에 관련 spec 파일을 먼저 읽는다. 구현이 spec과 달라져야 하면 **spec을 먼저 수정**하고 코드를 바꾼다.

## 기술 스택 (변경 금지 — 변경 필요 시 사용자에게 먼저 확인)

- Frontend: Vue.js 3 (Composition API, `<script setup>`), Vite, Bootstrap 5.0, HTML5/CSS3, SPA
- Backend: Python 3.12, Django 5.x, Django ORM, Django REST Framework
- Database: PostgreSQL 16 + pgvector (`pgvector` Python 패키지의 `VectorField`)
- LLM: Anthropic Claude API (공식 `anthropic` Python SDK). API Key는 관리자 화면에서 입력 → DB에 암호화 저장
- Embedding: 로컬 `sentence-transformers` 모델 (Claude API는 임베딩을 제공하지 않음) — 상세는 specs/05

## 디렉터리 구조

```
cs_agent/
├── CLAUDE.md
├── README.md
├── docker-compose.yml        # PostgreSQL + pgvector
├── specs/                    # 요구 사항 문서
├── backend/                  # Django 프로젝트
│   ├── manage.py
│   ├── config/               # settings, urls, wsgi/asgi
│   ├── accounts/             # User(AbstractUser), 로그인, 기본 관리자 생성
│   ├── knowledge/            # Company, Product, KnowledgeChunk(pgvector), 임베딩
│   ├── chat/                 # 챗봇 API, RAG 파이프라인, Claude 연동
│   ├── settings_app/         # SystemSetting(API Key 등)
│   └── requirements.txt
└── frontend/                 # Vue 3 + Vite SPA
    ├── package.json
    └── src/
```

## 개발 명령어

```bash
# DB
docker compose up -d db

# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate          # post_migrate에서 기본 관리자 자동 생성
python manage.py runserver 8000
pytest                            # 백엔드 테스트

# Frontend
cd frontend
npm install
npm run dev                       # http://localhost:5173 (/api → :8000 프록시)
npm run test                      # Vitest
npm run lint
```

## 코딩 규칙

### 공통
- 사용자에게 보이는 UI 문구와 챗봇 기본 응답 언어는 **한국어**. 코드, 식별자, 커밋 메시지는 영어.
- 비밀 값(API Key, SECRET_KEY, DB 비밀번호)은 절대 코드/로그/응답/커밋에 남기지 않는다. 환경 변수 또는 DB(암호화)만 사용.
- 새 기능에는 테스트를 함께 작성한다. 작업 완료 전 `pytest`와 `npm run test`/`npm run lint`를 실행해 통과를 확인한다.
- 작은 단위로 구현하고, 하나의 Phase(specs/00 참조)를 끝낼 때마다 동작 확인 후 커밋한다.

### Backend (Django / DRF)
- 앱별로 `models.py`, `serializers.py`, `views.py`, `urls.py`, `services.py`(비즈니스 로직), `tests/` 구조를 유지한다. 뷰는 얇게, 로직은 `services.py`에.
- 모든 API는 `/api/` 하위, JSON 입출력. 에러 응답 형식은 specs/04의 공통 에러 포맷을 따른다.
- 사용자 모델은 `accounts.User`(AbstractUser 상속). `AUTH_USER_MODEL = "accounts.User"`는 **첫 마이그레이션 전에** 설정한다.
- 권한: 관리자 API는 `IsAdminRole` 권한 클래스, 챗봇 API는 `AllowAny` + rate limit.
- Claude 호출은 `chat/llm.py` 한 곳에서만 한다. 모델 ID는 SystemSetting 값을 사용하고 하드코딩하지 않는다(기본값 `claude-opus-5-5`).
- 임베딩 생성은 `knowledge/embeddings.py` 한 곳에서만 한다. 모델 로딩은 프로세스당 1회(lazy singleton).
- Company/Product 생성·수정·삭제 시 같은 트랜잭션 안에서 KnowledgeChunk를 재생성/삭제한다.

### Frontend (Vue 3)
- Composition API + `<script setup>`만 사용. 상태 관리는 Pinia, 라우팅은 Vue Router, HTTP는 `src/api/` 의 axios 인스턴스 하나로 통일.
- 스타일은 Bootstrap 5.0 클래스를 우선 사용하고, 커스텀 CSS는 컴포넌트 `<style scoped>`에 최소한으로.
- LLM 응답은 `v-html`로 렌더링하지 않는다(XSS). 마크다운 렌더링이 필요하면 sanitize 후 사용.

## README.md 유지 규칙

README.md는 **필요할 때마다 업데이트**한다. 다음 중 하나라도 바뀌면 같은 작업 안에서 README를 갱신한다:
- 설치/실행 방법, 필요한 환경 변수, 포트
- 새 기능 추가 또는 기능 동작 변경
- 프로젝트 구조, 의존성(주요 라이브러리) 변경
- 구현 진행 상황(Phase 완료)

## 하지 말 것
- specs에 없는 기능을 임의로 추가하지 않는다 (필요하면 제안만).
- 기본 관리자 비밀번호(`admin1234!`)를 프론트엔드나 로그에 노출하지 않는다.
- 프론트엔드에서 Claude API를 직접 호출하지 않는다. API Key는 브라우저로 내려가지 않는다(마스킹 값만).
- `--no-verify`, 테스트 skip, 마이그레이션 파일 수동 삭제 금지.
