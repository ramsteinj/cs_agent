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
- 응답 렌더링: **봇 답변은 마크다운**(`marked`, GFM, 줄바꿈 유지)을 `DOMPurify`로 sanitize한 HTML로 표시한다 (`src/utils/markdown.js`). 고객 메시지와 환영 메시지는 텍스트 그대로(`white-space: pre-wrap`).
  - 허용 태그: p, br, strong/b, em/i, del/s, ul/ol/li, blockquote, hr, h1~h6, code, pre, table 계열, a. 속성은 href, title만.
  - 이미지·iframe·form·style 등은 제거한다 (문서에 숨긴 지시로 외부 추적 이미지를 띄우는 것 방지).
  - 링크는 `http(s):`, `mailto:`, `tel:`만 허용하고 `target="_blank" rel="noopener noreferrer nofollow"`.
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
카드 5개:
1. **LLM 연동**: 사용할 LLM 선택(Claude / ChatGPT / Gemini 라디오, 저장 즉시 반영). 공급자마다 탭 또는 구역으로
   - API Key 상태 배지(등록됨/미등록), 마스킹 키, 등록 일시, `type=password` 입력 + "저장"(검증 진행 표시) / "삭제"(확인 다이얼로그)
   - 모델 select: `GET .../providers/{p}/models`로 채움. Claude는 키가 없어도 권장 목록 표시(기본 `claude-opus-5-5`). ChatGPT·Gemini는 키 등록 후 목록 표시, 모델 미선택 시 경고
   - Temperature: "모델 기본값 사용" 스위치 + 숫자 입력(범위 표시) + 저장. 현재 모델이 지원하지 않으면 입력 전체를 비활성화하고 "선택한 모델(…)은 temperature 설정을 지원하지 않습니다" 표시. 모델을 바꾸면 즉시 다시 판단한다.
   - 선택된 공급자에 키 또는 모델이 없으면 "챗봇이 비활성화되어 있습니다" 경고
2. **챗봇 설정**: 챗봇 이름, 환영 메시지, 시스템 프롬프트(textarea, 10000자 카운터, "기본값으로 되돌리기" 버튼, `{bot_name}` 안내와 안전 규칙을 지우지 말라는 권고), 추가 지시사항(textarea, 2000자 카운터).
3. **RAG 설정**: specs/05 §1.1의 값 입력(숫자 입력은 범위 표시), 항목별 짧은 설명. 저장 시 재색인이 필요한 값이 바뀌었으면 확인 다이얼로그("전체 재색인이 실행됩니다") 후 저장, 완료 toast에 청크 수 표시.
4. **지식 색인**: 통계(회사/제품/청크 수, 임베딩 모델), "전체 재색인" 버튼.
5. **비밀번호 변경**: 현재/새/새 비밀번호 확인.
- `must_change_password` 이면 관리자 레이아웃 상단에 `alert-warning` 배너 + 설정 페이지 링크.

### 5.6 ProductFormView 문서 영역
- "제품 문서 (Text / Word / PDF)" 구역: 파일 선택(`accept=".txt,.docx,.pdf"`, 여러 개), 선택한 파일 목록(문서 제목 입력·이름·크기, 제거 버튼), 등록된 문서 목록(제목·파일명·형식·크기·글자 수, 제목 변경, 삭제 버튼 + 확인).
- 문서 제목 입력은 자주 쓰는 종류를 제안한다(datalist): 사용자 매뉴얼, 빠른 설치 가이드, 제품 소개서, 가격표, FAQ, 릴리스 노트, 기술 사양서.
- 새 파일은 "저장" 시 제품 저장 후 하나씩 업로드한다. 실패한 파일은 파일명과 오류 메시지를 표시하고 화면에 남는다(성공한 파일과 제품 저장은 유지).
- 상세 설명이 비어 있으면 등록된 문서 또는 새 파일이 1개 이상 있어야 저장 버튼이 활성화된다.

## 6. 공통 컴포넌트
`LoginModal`, `ConfirmDialog`, `ToastContainer`, `ChatMessage`, `ChatInput`, `LoadingButton`, `Pagination`, `AdminLayout`

## 7. UI/접근성 규칙
- 모든 문구 한국어. 폼 요소에 `label` 연결, 아이콘 버튼에 `aria-label`.
- 채팅 메시지 목록에 `aria-live="polite"`.
- Bootstrap 5.0 기본 테마 사용, 커스텀 색상은 CSS 변수로 `src/assets/main.css` 한 곳에서 정의.
