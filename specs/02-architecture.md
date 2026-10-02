# 02. 아키텍처

## 1. 시스템 구성

```
 ┌──────────────────────┐
 │  Vue.js 3 SPA (Vite) │   고객 채팅 UI / 관리자 화면
 └──────────┬───────────┘
            │ HTTP / JSON (채팅 응답은 SSE 스트리밍)
            v
 ┌──────────────────────────────────────────────┐
 │  Django + Django REST Framework              │
 │  ├─ accounts     : 사용자/인증               │
 │  ├─ knowledge    : 회사·제품 CRUD, 임베딩     │──── sentence-transformers (로컬 임베딩)
 │  ├─ chat         : RAG 파이프라인            │──── llm/: Claude · ChatGPT · Gemini API (HTTPS)
 │  └─ settings_app : LLM·RAG 시스템 설정        │
 └──────────┬───────────────────────────────────┘
            │ Django ORM
            v
 ┌──────────────────────┐
 │ PostgreSQL 18        │
 │  + pgvector 확장      │
 └──────────────────────┘
```

- 개발 환경: Vite dev server(5173)가 `/api` 요청을 Django(8000)로 프록시 → 같은 출처처럼 동작, CORS 불필요.
- 운영(참고): `npm run build` 결과물을 Nginx가 정적 서빙하고 `/api`는 gunicorn(Django)으로 리버스 프록시.

## 2. 기술 스택 및 버전

| 영역 | 기술 | 버전/비고 |
|---|---|---|
| Frontend | Vue.js | 3.x, Composition API, `<script setup>` |
| | Vite | 5.x 이상 |
| | Bootstrap | **5.0.x** (`bootstrap@5.0.2`), JS 번들 포함 |
| | Vue Router | 4.x (history 모드) |
| | Pinia | 2.x |
| | axios | 1.x |
| | Vitest + @vue/test-utils | 단위 테스트 |
| Backend | Python | 3.12 |
| | Django | 5.x |
| | djangorestframework | 3.15+ |
| | djangorestframework authtoken | 토큰 인증 (specs/07) |
| | psycopg | 3.x (`psycopg[binary]`) |
| | pgvector | Python 패키지 (`pgvector.django`) |
| | anthropic | Claude 공식 Python SDK |
| | openai | ChatGPT 공식 Python SDK (Responses API) |
| | google-genai | Gemini 공식 Python SDK |
| | python-docx / pypdf | 제품 문서(.docx / .pdf) 텍스트 추출 |
| | sentence-transformers | 로컬 임베딩 |
| | cryptography | Fernet (API Key 암호화) |
| | django-environ | 환경 변수 로딩 |
| | pytest, pytest-django | 테스트 |
| Database | PostgreSQL | 18 (로컬 설치, 포트 5432) + `postgresql-18-pgvector` |

## 3. 디렉터리 구조

```
backend/
├── manage.py
├── requirements.txt
├── pytest.ini
├── config/
│   ├── settings.py          # django-environ 으로 .env 로딩
│   ├── urls.py              # /api/ 하위 앱 URL include
│   └── wsgi.py / asgi.py
├── common/                  # 공통 예외 핸들러, 권한 클래스, 페이지네이션
├── accounts/
│   ├── models.py            # User(AbstractUser)
│   ├── signals.py           # post_migrate → ensure_default_admin
│   ├── services.py
│   └── management/commands/ensure_default_admin.py
├── knowledge/
│   ├── models.py            # Company, Product, ProductDocument, KnowledgeChunk
│   ├── documents.py         # txt/docx/pdf 텍스트 추출
│   ├── embeddings.py        # 임베딩 모델 로딩/인코딩 (유일한 진입점)
│   ├── chunking.py
│   ├── indexing.py          # 소스 → 청크 생성/삭제
│   └── retrieval.py         # 벡터 검색
├── llm/                     # LLM 공급자 (유일한 LLM 호출 지점, Django 앱 아님)
│   ├── base.py              # 공통 인터페이스, FinalReply, LLMError, InvalidAPIKey
│   ├── anthropic_provider.py / openai_provider.py / gemini_provider.py
├── chat/
│   ├── models.py            # ChatSession, ChatMessage
│   ├── prompts.py           # 시스템 프롬프트 템플릿
│   └── services.py          # RAG 오케스트레이션
└── settings_app/
    ├── models.py            # SystemSetting (싱글턴), LLMProviderConfig
    └── crypto.py            # Fernet 암복호화

frontend/
├── index.html
├── vite.config.js           # /api 프록시
└── src/
    ├── main.js              # bootstrap css/js import
    ├── App.vue              # 상단 네비게이션(우측 로그인)
    ├── router/index.js
    ├── stores/              # auth.js, chat.js, toast.js(알림)
    ├── api/                 # client.js(axios), auth.js, knowledge.js, chat.js, settings.js, sse.js(SSE 파서)
    ├── views/               # ChatView, admin/*View
    ├── components/          # LoginModal, ChatMessage, ChatInput, ConfirmDialog ...
    └── composables/         # useUnsavedGuard (폼 이탈 확인)
```

## 4. 주요 설계 결정

| 결정 | 이유 |
|---|---|
| 임베딩은 로컬 sentence-transformers | Claude API는 임베딩 엔드포인트가 없음. 관리자가 입력하는 키는 Anthropic 키 하나뿐이므로 추가 외부 키 없이 동작해야 함 |
| 다국어 임베딩 모델 `intfloat/multilingual-e5-small` (384차원) | 한국어 지원, CPU에서도 빠름. 환경 변수로 교체 가능 |
| 회사/제품은 정규 테이블 + 별도 `KnowledgeChunk` 벡터 테이블 | CRUD 화면은 구조화 데이터로, 검색은 청크 단위로 분리 |
| 채팅 응답은 SSE 스트리밍 | 긴 답변의 체감 대기 시간 감소 |
| 인증은 DRF Token | SPA에서 단순, CSRF 이슈 없음 |
| SystemSetting 싱글턴(pk=1) | 전역 설정(사용할 LLM, RAG 튜닝 값)을 DB에 저장해야 한다는 요구 사항 |
| LLM 공급자별 설정 행 + `backend/llm/` 공통 인터페이스 | 공급자를 바꿔도 키가 유지되고, 채팅 코드는 공급자를 몰라도 됨 |
| ChatGPT·Gemini 모델은 공급자 모델 목록에서 선택 | 모델 ID가 자주 바뀌어 코드에 고정하면 낡음 |
| 문서는 추출 텍스트만 DB 저장 | 원본 보관 요구 없음, 파일 저장소 불필요 |
