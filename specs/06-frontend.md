# 06. Frontend (Vue.js 3 SPA)

## 1. 공통 레이아웃 (`App.vue`)

```
┌───────────────────────────────────────────────────────────────┐
│ [로고] {bot_name}                     [관리자 로그인]           │  ← Bootstrap navbar
│                                       (로그인 시: admin ▾       │
│                                         - 관리자 페이지          │
│                                         - 로그아웃)              │
├───────────────────────────────────────────────────────────────┤
│                      <router-view />                          │
└───────────────────────────────────────────────────────────────┘
```
- 로그인 버튼/사용자 메뉴는 navbar **우측 정렬**(`ms-auto`).
- 반응형: 모바일(<768px)에서도 채팅이 화면 전체를 사용하고 navbar는 collapse.

## 2. 라우팅 (`router/index.js`, history 모드)

| Path | View | 권한 |
|---|---|---|
| `/` | `ChatView` | 공개 |
| `/admin` | → `/admin/companies` 리다이렉트 | Admin |
| `/admin/companies` | `CompanyListView` | Admin |
| `/admin/companies/new`, `/admin/companies/:id/edit` | `CompanyFormView` | Admin |
| `/admin/products` | `ProductListView` | Admin |
| `/admin/products/new`, `/admin/products/:id/edit` | `ProductFormView` | Admin |
| `/admin/settings` | `SettingsView` (API Key, 챗봇 설정, 재색인, 비밀번호 변경) | Admin |
| `*` | `NotFoundView` | 공개 |

- 라우트 meta `requiresAdmin: true` + 전역 `beforeEach` 가드. 미인증이면 `/` 로 이동하고 로그인 모달 오픈(`auth.openLoginModal(redirectPath)`), 로그인 성공 시 원래 경로로 이동.
- 관리자 화면 좌측(데스크톱) 또는 상단 탭(모바일) 메뉴: 회사 관리 / 제품 관리 / 시스템 설정.

## 3. 상태 관리 (Pinia)

### `stores/auth.js`
- state: `token`, `user`, `loginModalOpen`, `redirectPath`
- token은 `localStorage` 에 저장(키 `cs_agent_token`), 앱 시작 시 있으면 `/api/auth/me` 로 검증, 실패 시 제거.
- actions: `login`, `logout`, `fetchMe`, `changePassword`
- getters: `isAdmin`, `mustChangePassword`

### `stores/chat.js`
- state: `enabled`, `botName`, `welcomeMessage`, `sessionId`, `messages[]`, `streaming`, `error`
- `sessionId` 는 `sessionStorage` 에 저장 (탭 단위 대화 유지). 새로고침 시 메시지 목록 복원.
- actions: `loadStatus`, `ensureSession`, `send(text)`, `reset()`

## 4. API 클라이언트 (`src/api/client.js`)
- axios 인스턴스 `baseURL: "/api"`, 요청 인터셉터로 `Authorization: Token ...` 추가.
- 응답 인터셉터: 401이면 auth store 초기화. 공통 에러 포맷의 `error.message` 를 꺼내 쓰는 헬퍼 제공.
- **SSE 채팅은 axios가 아닌 `fetch` + `ReadableStream`** 으로 처리 (POST 본문이 필요하므로 EventSource 불가). `src/api/chat.js` 의 `streamMessage(sessionId, text, { onDelta, onDone, onError, signal })`.

## 5. 화면 상세

### 5.1 ChatView (`/`)
- 상단: 봇 이름, "새 대화" 버튼.
- 메시지 영역: 첫 화면에 환영 메시지(assistant 말풍선). 사용자 말풍선 우측(primary), 봇 말풍선 좌측(light). 새 메시지 시 자동 스크롤.
- 봇 응답 스트리밍 중 타이핑 표시, 답변 아래 출처(`참고: ...`) 작은 글씨.
- 입력: `textarea`(자동 높이, 최대 5줄) + 전송 버튼. Enter 전송, Shift+Enter 줄바꿈, IME 조합 중(`isComposing`) Enter는 무시(한국어 입력 필수 처리). 글자 수 표시 `n/1000`.
- **비활성(`enabled=false`)**: textarea, 전송 버튼 `disabled`, placeholder "현재 상담 서비스를 준비 중입니다.", 메시지 영역에 `alert-secondary` 안내.
- 응답 렌더링: 텍스트로 출력하고 줄바꿈은 CSS `white-space: pre-wrap`. 마크다운 지원 시 `marked` + `DOMPurify` 로 sanitize.
- 오류: 해당 봇 말풍선을 오류 스타일로 바꾸고 "다시 시도" 버튼.

### 5.2 LoginModal
- Bootstrap modal, 필드: 아이디, 비밀번호, 로그인 버튼. 로딩 중 버튼 비활성 + spinner.
- 실패 시 모달 내부 `alert-danger` 에 서버 메시지 표시. 성공 시 모달 닫기 + toast "로그인되었습니다."

### 5.3 CompanyListView / ProductListView
- Bootstrap table, 상단 검색창 + "새로 등록" 버튼. 제품 목록은 회사/카테고리/활성 필터, 페이지네이션.
- 각 행: 수정, 삭제 버튼. 삭제는 `ConfirmDialog` 컴포넌트로 확인 (회사 삭제 시 "소속 제품 N개도 함께 삭제됩니다").

### 5.4 CompanyFormView / ProductFormView
- 생성/수정 겸용. 필수 항목에 `*` 표시. 서버 검증 오류는 `is-invalid` + `invalid-feedback` 로 필드 아래 표시.
- 저장 중 버튼 비활성("저장 중... 임베딩 생성"), 성공 시 목록으로 이동 + toast.
- 변경 사항이 있는 상태에서 이탈 시 확인(`onBeforeRouteLeave`).

### 5.5 SettingsView
카드 4개:
1. **Claude API Key**: 상태 배지(등록됨/미등록), 마스킹 키, 등록 일시. `type=password` 입력 + "저장"(검증 진행 표시) / "삭제"(확인 다이얼로그). 미등록 시 "API Key를 등록해야 챗봇이 활성화됩니다." 경고.
2. **챗봇 설정**: 모델 select, 챗봇 이름, 환영 메시지, 추가 지시사항(textarea, 2000자 카운터).
3. **지식 색인**: 통계(회사/제품/청크 수, 임베딩 모델), "전체 재색인" 버튼.
4. **비밀번호 변경**: 현재/새/새 비밀번호 확인.
- `must_change_password` 이면 관리자 레이아웃 상단에 `alert-warning` 배너 + 설정 페이지 링크.

## 6. 공통 컴포넌트
`LoginModal`, `ConfirmDialog`, `ToastContainer`, `ChatMessage`, `ChatInput`, `LoadingButton`, `Pagination`, `AdminLayout`

## 7. UI/접근성 규칙
- 모든 문구 한국어. 폼 요소에 `label` 연결, 아이콘 버튼에 `aria-label`.
- 채팅 메시지 목록에 `aria-live="polite"`.
- Bootstrap 5.0 기본 테마 사용, 커스텀 색상은 CSS 변수로 `src/assets/main.css` 한 곳에서 정의.
