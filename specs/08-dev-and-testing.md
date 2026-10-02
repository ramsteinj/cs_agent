# 08. 개발 환경 및 테스트

## 1. 로컬 개발 환경

### 데이터베이스 (로컬 PostgreSQL 18 + pgvector)
로컬에 설치된 PostgreSQL 18 클러스터(포트 5432)를 사용한다 (Docker 미사용).

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

### 환경 변수 (`backend/.env`, 템플릿은 `backend/.env.example` 로 커밋)
| 변수 | 예시 | 설명 |
|---|---|---|
| `DJANGO_SECRET_KEY` | (랜덤) | 필수 |
| `DJANGO_DEBUG` | `True` | |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1` | |
| `DATABASE_URL` | `postgres://cs_agent:cs_agent@localhost:5432/cs_agent` | 로컬 PostgreSQL 18 |
| `FIELD_ENCRYPTION_KEY` | (Fernet 키) | 필수, API Key 암호화 |
| `DJANGO_NUM_PROXIES` | `0` | 신뢰하는 리버스 프록시 수 (Nginx 1대 뒤면 `1`). `0`이면 `X-Forwarded-For` 무시 |
| `DJANGO_SECURE_SSL_REDIRECT` / `DJANGO_SECURE_HSTS_SECONDS` / `DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS` | `True` / `31536000` / `False` | `DJANGO_DEBUG=False`일 때만 적용 |
| `EMBEDDING_BACKEND` | `sentence_transformers` / `fake` | 테스트는 `fake` |
| `EMBEDDING_MODEL` | `intfloat/multilingual-e5-small` | |
| `EMBEDDING_DIM` | `384` | 마이그레이션 차원과 일치해야 함 |
| `RAG_TOP_K` | `5` | |
| `RAG_MAX_DISTANCE` | `0.6` | |

> Anthropic API Key는 환경 변수가 아니라 **관리자 화면에서 입력 → DB 저장**이 요구 사항이다. `ANTHROPIC_API_KEY` 환경 변수는 사용하지 않는다.

### 실행 순서
1. 로컬 PostgreSQL에 pgvector 설치 및 DB 생성 (위 "데이터베이스" 참조, 최초 1회)
2. `cd backend && python3.12 -m venv .venv && pip install -r requirements.txt && cp .env.example .env` (키 생성 후 기입)
3. `python manage.py migrate` → pgvector 확장 생성 + 기본 관리자 생성
4. `python manage.py runserver 8000`
5. `cd frontend && npm install && npm run dev` → http://localhost:5173
6. 관리자 로그인(`admin`/`admin1234!`) → 시스템 설정에서 API Key 등록 → 회사/제품 등록 → 채팅 테스트

### 샘플 데이터
`python manage.py load_sample_knowledge` — 가상의 회사 1개, 제품 3개를 생성하고 색인 (개발/데모용).

## 2. 테스트 전략

### Backend (pytest + pytest-django)
- 테스트 DB도 로컬 PostgreSQL(pgvector) 사용 (pytest-django가 `test_cs_agent` 생성) — SQLite 금지(벡터 필드 때문).
- `EMBEDDING_BACKEND=fake` : 텍스트 해시 기반 결정적 벡터 (같은 텍스트 → 같은 벡터).
- Claude 호출은 `chat/llm.py` 를 mock 하여 네트워크 없이 테스트. 실제 API 호출 테스트는 `@pytest.mark.live` 로 분리, 기본 실행에서 제외.

필수 테스트 목록:
| 영역 | 테스트 |
|---|---|
| accounts | 기본 관리자 생성(빈 DB/기존 관리자 있음/2회 실행), 로그인 성공·실패·잠금, me, 로그아웃 후 401, 비밀번호 변경 시 플래그 해제 |
| 권한 | 모든 `/api/admin/*` 가 비인증 401, 비관리자 403 |
| knowledge | CRUD 검증, 생성/수정/삭제 시 청크 동기화, 비활성 제품 청크 `is_searchable=False`, 청킹 함수 단위 테스트 |
| retrieval | fake 임베딩으로 관련 청크가 상위에 오는지, 비활성 제외, 거리 임계값 |
| settings | API Key 저장 시 검증 호출(mock), 암호문 저장, 마스킹, 평문 미노출, 삭제 후 챗봇 비활성 |
| chat | status enabled/disabled, 비활성 시 503, SSE 이벤트 순서(start→delta→done), LLM 오류 시 error 이벤트, 길이 제한 400, 히스토리 10개 제한, rate limit 429 |

### Frontend (Vitest + @vue/test-utils)
- `ChatInput`: disabled 상태, Enter/Shift+Enter, IME 조합 중 Enter 무시, 1000자 제한
- `ChatView`: status `enabled=false` 시 안내 문구 및 disabled
- `stores/auth`: 로그인/로그아웃 토큰 저장·제거
- 라우터 가드: 비인증 `/admin/*` 접근 시 리다이렉트 + 모달 오픈
- SSE 파서: 청크가 이벤트 경계와 다르게 잘려 와도 올바르게 파싱

### 수동 E2E 체크리스트 (Phase 6)
- [ ] 빈 DB에서 전체 실행 순서대로 진행 시 오류 없음
- [ ] API Key 미등록 상태 채팅 비활성 → 등록 후 활성
- [ ] 제품 등록 → 질문 → 답변에 반영 → 제품 수정 → 답변 변경 → 제품 삭제 → 더 이상 답변하지 않음
- [ ] 모바일 폭(375px)에서 채팅/관리자 화면 사용 가능

## 3. 품질 도구
- Backend: `ruff`(lint+format), 설정은 `backend/pyproject.toml`
- Frontend: ESLint(`eslint-plugin-vue`) + Prettier
- 커밋 전: `ruff check . && pytest`, `npm run lint && npm run test`
