# 04. REST API 명세

- Base URL: `/api`
- 형식: JSON (`Content-Type: application/json; charset=utf-8`), 필드명 snake_case
- 인증: 관리자 API는 `Authorization: Token <token>` 헤더 필요 (specs/07)
- 시간: ISO 8601, UTC (`2026-10-02T09:00:00Z`)

## 공통 에러 포맷

DRF `EXCEPTION_HANDLER`를 커스텀(`common.exceptions.api_exception_handler`)하여 모든 에러를 다음 형식으로 반환한다.

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "입력값을 확인해 주세요.",
    "details": { "name": ["이 필드는 필수입니다."] }
  }
}
```

| HTTP | code | 상황 |
|---|---|---|
| 400 | `VALIDATION_ERROR` | 입력 검증 실패 (`details`에 필드별 메시지) |
| 400 | `INVALID_API_KEY` | API Key 검증 실패 |
| 400 | `API_KEY_REQUIRED` | 키가 없는 공급자의 모델 목록 요청 |
| 400 | `UNSUPPORTED_FILE` | 지원하지 않는 파일 (txt/docx/pdf 외, 구형 .doc, 암호화 PDF) |
| 400 | `DOCUMENT_PARSE_ERROR` | 파일에서 텍스트를 추출할 수 없음 (손상, 스캔 PDF 등) |
| 413 | `FILE_TOO_LARGE` | 파일 10MB 초과 또는 추출 텍스트 200,000자 초과 |
| 401 | `NOT_AUTHENTICATED` / `INVALID_CREDENTIALS` | 미인증 / 로그인 실패 |
| 403 | `PERMISSION_DENIED` | 관리자 아님 |
| 404 | `NOT_FOUND` | |
| 409 | `CONFLICT` | 중복(unique), 재색인 진행 중 |
| 423 | `ACCOUNT_LOCKED` | 로그인 차단 상태 |
| 429 | `RATE_LIMITED` | 요청 제한 |
| 502 | `LLM_ERROR` | LLM API 오류 (Claude / ChatGPT / Gemini) |
| 503 | `CHATBOT_DISABLED` | 선택된 LLM 공급자의 API Key 또는 모델 미설정 |
| 503 | `EMBEDDING_ERROR` | 임베딩 생성 실패 (저장 내용은 롤백됨) |
| 500 | `SERVER_ERROR` | 처리되지 않은 서버 오류 (상세 내용 미노출) |

---

## 1. Health
| Method | Path | 인증 | 설명 |
|---|---|---|---|
| GET | `/api/health` | 없음 | `{"status": "ok"}` |

## 2. 인증 (`accounts`)

| Method | Path | 인증 | 설명 |
|---|---|---|---|
| POST | `/api/auth/login` | 없음 | 관리자 로그인 |
| POST | `/api/auth/logout` | Admin | 토큰 폐기 |
| GET | `/api/auth/me` | Admin | 현재 사용자 |
| POST | `/api/auth/change-password` | Admin | 비밀번호 변경 |

**POST /api/auth/login**
```json
// request
{ "username": "admin", "password": "admin1234!" }
// 200
{ "token": "9944b0...", "user": { "id": 1, "username": "admin", "role": "ADMIN", "must_change_password": true } }
```

**POST /api/auth/change-password**
```json
{ "current_password": "...", "new_password": "..." }   // 200 → 새 토큰 반환 {"token": "..."}
```

## 3. 회사 (`knowledge`) — 모두 Admin

| Method | Path | 설명 |
|---|---|---|
| GET | `/api/admin/companies` | 목록 (`?search=`), 페이지네이션 |
| POST | `/api/admin/companies` | 생성 → 201 |
| GET | `/api/admin/companies/{id}` | 상세 |
| PUT / PATCH | `/api/admin/companies/{id}` | 수정 |
| DELETE | `/api/admin/companies/{id}` | 삭제 → 204 (제품·청크 연쇄 삭제) |

Company 응답 예:
```json
{
  "id": 1, "name": "OK컴퍼니", "description": "...", "website": "https://...",
  "phone": "02-000-0000", "email": "help@example.com", "address": "...",
  "business_hours": "평일 09:00-18:00", "extra_info": "...",
  "product_count": 3, "chunk_count": 2,
  "created_at": "...", "updated_at": "..."
}
```

## 4. 제품 (`knowledge`) — 모두 Admin

| Method | Path | 설명 |
|---|---|---|
| GET | `/api/admin/products` | 목록 `?search=&company=&category=&is_active=&page=` |
| POST | `/api/admin/products` | 생성 → 201 |
| GET | `/api/admin/products/{id}` | 상세 |
| PUT / PATCH | `/api/admin/products/{id}` | 수정 |
| DELETE | `/api/admin/products/{id}` | 삭제 → 204 |
| GET | `/api/admin/products/categories` | 등록된 카테고리 목록 (필터용) |

Product 응답 예 (`description`은 선택 — 문서만으로 등록 가능):
```json
{
  "id": 10, "company": 1, "company_name": "OK컴퍼니", "name": "OK클라우드",
  "category": "SaaS", "summary": "...", "description": "...", "price": "월 9,900원",
  "features": "...", "usage_guide": "...", "faq": "...", "is_active": true,
  "document_count": 2, "chunk_count": 4, "created_at": "...", "updated_at": "..."
}
```

### 4.1 제품 문서 (Text / MS Word / PDF)

| Method | Path | 설명 |
|---|---|---|
| GET | `/api/admin/products/{id}/documents` | 문서 목록 |
| POST | `/api/admin/products/{id}/documents` | `multipart/form-data`, 필드 `file` 1개 → 텍스트 추출 → 201, 제품 재색인 |
| DELETE | `/api/admin/products/{id}/documents/{document_id}` | 삭제 → 204, 제품 재색인 |

Document 응답 예 (본문 전체는 반환하지 않음):
```json
{ "id": 3, "file_name": "가격표.pdf", "file_type": "pdf", "file_size": 183204,
  "char_count": 5120, "preview": "앞 200자...", "created_at": "..." }
```
- 허용: `.txt`(UTF-8, 실패 시 CP949), `.docx`, `.pdf`. 확장자와 파일 시그니처를 모두 확인한다.
- 오류: `UNSUPPORTED_FILE`(400), `DOCUMENT_PARSE_ERROR`(400), `FILE_TOO_LARGE`(413), 임베딩 실패 `EMBEDDING_ERROR`(503, 문서 저장도 롤백).

페이지네이션 응답 형식 (DRF PageNumberPagination, page_size=20, `?page_size=` 최대 100 — 관리자 드롭다운용):
```json
{ "count": 42, "next": "...", "previous": null, "results": [ ... ] }
```

## 5. 지식 재색인 — Admin

| Method | Path | 설명 |
|---|---|---|
| POST | `/api/admin/knowledge/reindex` | 전체 재색인 실행 → 200 `{"chunks": 123}` (진행 중이면 409) |
| GET | `/api/admin/knowledge/stats` | `{"companies": 2, "products": 15, "chunks": 80, "embedding_model": "...", "embedding_dim": 384}` |

v1은 동기 실행(데이터 규모가 작다고 가정). DB advisory lock 또는 캐시 락으로 중복 실행 방지.

## 6. 시스템 설정 (`settings_app`) — Admin

| Method | Path | 설명 |
|---|---|---|
| GET | `/api/admin/settings` | 설정 조회 (사용할 LLM, 공급자별 키 상태·모델, 챗봇 표시) |
| PATCH | `/api/admin/settings` | `llm_provider`, `bot_name`, `welcome_message`, `extra_instructions` 변경 |
| PUT | `/api/admin/settings/providers/{provider}/api-key` | 해당 공급자 API Key 등록·변경 (공급자 API로 검증 후 저장) |
| DELETE | `/api/admin/settings/providers/{provider}/api-key` | API Key 삭제 → 204 |
| PATCH | `/api/admin/settings/providers/{provider}` | 모델·temperature 변경 `{"model": "claude-haiku-4-5", "temperature": 0.3}` (temperature `null` = 모델 기본값) |
| GET | `/api/admin/settings/providers/{provider}/models` | 선택 가능한 모델 목록 (등록된 키로 공급자 모델 목록 API 조회) |
| GET | `/api/admin/settings/rag` | RAG 튜닝 설정 조회 |
| PATCH | `/api/admin/settings/rag` | RAG 튜닝 설정 변경 (청크·임베딩 설정이 바뀌면 전체 재색인) |

`{provider}`: `anthropic`(Claude), `openai`(ChatGPT), `gemini`(Gemini).

GET `/api/admin/settings` 응답:
```json
{
  "llm_provider": "anthropic",
  "chatbot_enabled": true,
  "providers": [
    { "provider": "anthropic", "label": "Claude", "api_key_configured": true,
      "api_key_masked": "sk-ant-...abcd", "api_key_updated_at": "2026-10-02T09:00:00Z",
      "model": "claude-opus-5-5", "default_model": "claude-opus-5-5",
      "temperature": null, "temperature_supported": false, "temperature_range": [0.0, 1.0] },
    { "provider": "openai", "label": "ChatGPT", "api_key_configured": false,
      "api_key_masked": "", "api_key_updated_at": null, "model": "", "default_model": "" },
    { "provider": "gemini", "label": "Gemini", "api_key_configured": false,
      "api_key_masked": "", "api_key_updated_at": null, "model": "", "default_model": "" }
  ],
  "bot_name": "고객지원 챗봇",
  "welcome_message": "...",
  "extra_instructions": ""
}
```
- PUT api-key 요청: `{ "api_key": "..." }` → 200 (GET과 동일 형식) / 400 `INVALID_API_KEY` / 502 `LLM_ERROR`(검증 불가)
- GET models 응답: `{"models": ["claude-opus-5-5", "claude-sonnet-5-5", ...], "default_model": "claude-opus-5-5"}`
  - Claude: 권장 목록(`claude-opus-5-5`, `claude-sonnet-5-5`, `claude-haiku-4-5`) + 키가 있으면 Anthropic 모델 목록. 키가 없어도 권장 목록 반환.
  - ChatGPT / Gemini: 키 필수(없으면 400 `API_KEY_REQUIRED`). 대화형 텍스트 모델만 걸러서 반환 (임베딩·음성·이미지 모델 제외).
- PATCH 공급자: `model`은 공백 없는 1~100자 문자열. `temperature`는 `null` 또는 `temperature_range` 안의 숫자이며, (변경 후) 모델이 temperature를 지원하지 않으면 숫자 값은 400 `VALIDATION_ERROR`(`details.temperature`).
- `temperature_supported`: 현재 모델이 temperature를 지원하는지 (specs/05 §4.1 규칙). 관리자 화면은 false이면 입력을 비활성화한다.

GET/PATCH `/api/admin/settings/rag`:
```json
{
  "embedding_model": "intfloat/multilingual-e5-small",
  "embedding_dim": 384,
  "chunk_max_chars": 500,
  "chunk_overlap_chars": 100,
  "retrieval_top_k": 5,
  "retrieval_max_distance": 0.6,
  "search_with_previous_question": true,
  "history_messages": 10,
  "max_sources": 3,
  "llm_max_output_tokens": 4096,
  "reindexed_chunks": null
}
```
- `embedding_dim`은 읽기 전용 (DB 스키마 값).
- `embedding_model`, `chunk_max_chars`, `chunk_overlap_chars` 중 하나라도 바뀌면 같은 요청 안에서 전체 재색인하고 `reindexed_chunks`에 청크 수를 넣는다. 재색인이 실패하면 설정 변경도 롤백한다.
- 임베딩 모델의 차원이 `embedding_dim`과 다르면 400 `VALIDATION_ERROR` (`details.embedding_model`).

## 7. 챗봇 (`chat`) — 인증 없음

| Method | Path | 설명 |
|---|---|---|
| GET | `/api/chat/status` | 챗봇 활성 여부 및 표시 정보 |
| POST | `/api/chat/sessions` | 새 세션 생성 → 201 `{"session_id": "uuid"}` |
| POST | `/api/chat/messages` | 질문 전송, **SSE 스트리밍** 응답 |
| GET | `/api/chat/sessions/{session_id}/messages` | 세션 메시지 목록 (새로고침 복원용) |

**GET /api/chat/status**
```json
{ "enabled": true, "bot_name": "고객지원 챗봇", "welcome_message": "안녕하세요! ..." }
```
`enabled=false` 일 때도 200으로 응답한다 (프론트가 비활성 UI 표시). `enabled`는 선택된 LLM 공급자의 API Key와 모델이 모두 설정되어 있는지를 뜻한다.

**POST /api/chat/messages**
```json
// request
{ "session_id": "3f2a...", "message": "OK클라우드 가격이 어떻게 되나요?" }
```
응답: `Content-Type: text/event-stream`. 이벤트 형식(각 줄 `data: <json>\n\n`):
```
data: {"type": "start", "message_id": 55}
data: {"type": "delta", "text": "OK클라우드는 "}
data: {"type": "delta", "text": "월 9,900원입니다."}
data: {"type": "done", "sources": [{"type": "product", "id": 10, "title": "OK클라우드"}]}
```
오류 발생 시: `data: {"type": "error", "code": "LLM_ERROR", "message": "일시적인 오류가 발생했습니다..."}` 후 스트림 종료.

`done` 이벤트에 `replace_text`가 있으면 클라이언트는 지금까지 표시한 delta 대신 그 텍스트로 답변을 교체한다 (예: 일부 출력 후 거절(refusal)된 경우 안내 문구로 교체). 이때 `sources`는 빈 배열이다.

- 스트리밍 시작 **전**에 검출되는 오류(검증 실패, 챗봇 비활성, 존재하지 않는 세션, rate limit)는 일반 JSON 에러 응답(공통 포맷)으로 반환한다.
- 존재하지 않는 `session_id` → 404. 세션은 프론트가 `POST /api/chat/sessions`로 먼저 생성한다.
- 구현: DRF 뷰가 아닌 Django `StreamingHttpResponse` 기반 함수 뷰 + `X-Accel-Buffering: no` 헤더. 입력 검증은 DRF Serializer 재사용.
