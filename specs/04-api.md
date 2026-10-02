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
| 401 | `NOT_AUTHENTICATED` / `INVALID_CREDENTIALS` | 미인증 / 로그인 실패 |
| 403 | `PERMISSION_DENIED` | 관리자 아님 |
| 404 | `NOT_FOUND` | |
| 409 | `CONFLICT` | 중복(unique), 재색인 진행 중 |
| 423 | `ACCOUNT_LOCKED` | 로그인 차단 상태 |
| 429 | `RATE_LIMITED` | 요청 제한 |
| 502 | `LLM_ERROR` | Claude API 오류 |
| 503 | `CHATBOT_DISABLED` | API Key 미등록 |
| 503 | `EMBEDDING_ERROR` | 임베딩 생성 실패 (저장 내용은 롤백됨) |

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

Product 응답 예:
```json
{
  "id": 10, "company": 1, "company_name": "OK컴퍼니", "name": "OK클라우드",
  "category": "SaaS", "summary": "...", "description": "...", "price": "월 9,900원",
  "features": "...", "usage_guide": "...", "faq": "...", "is_active": true,
  "chunk_count": 4, "created_at": "...", "updated_at": "..."
}
```

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
| GET | `/api/admin/settings` | 설정 조회 |
| PATCH | `/api/admin/settings` | 모델/챗봇 이름/환영 메시지/추가 지시 변경 |
| PUT | `/api/admin/settings/api-key` | API Key 등록·변경 (검증 후 저장) |
| DELETE | `/api/admin/settings/api-key` | API Key 삭제 → 204 |

GET 응답:
```json
{
  "api_key_configured": true,
  "api_key_masked": "sk-ant-...abcd",
  "api_key_updated_at": "2026-10-02T09:00:00Z",
  "claude_model": "claude-opus-5-5",
  "available_models": ["claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-4-5"],
  "bot_name": "고객지원 챗봇",
  "welcome_message": "...",
  "extra_instructions": ""
}
```

PUT api-key 요청: `{ "api_key": "sk-ant-..." }` → 200 (GET과 동일 형식) / 400 `INVALID_API_KEY`

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
`enabled=false` 일 때도 200으로 응답한다 (프론트가 비활성 UI 표시).

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
