# 00. 개요

## 1. 목적
회사 및 제품 정보를 기반으로 고객 문의에 자동 응답하는 **RAG(Retrieval-Augmented Generation) 기반 Customer Support Chatbot**을 만든다.
관리자가 등록한 회사/제품 정보를 pgvector에 임베딩으로 저장하고, 고객 질문과 유사한 정보를 검색해 Claude API로 답변을 생성한다.

## 2. 사용자 유형

| 유형 | 인증 | 할 수 있는 일 |
|---|---|---|
| 고객 (Visitor) | 없음 (익명) | 채팅 UI로 회사/제품 문의, 답변 수신 |
| 관리자 (Admin) | ID/비밀번호 로그인 | 회사·제품 정보 CRUD, Claude API Key 등록/변경, 시스템 설정 |

## 3. 용어

| 용어 | 의미 |
|---|---|
| Knowledge | 챗봇 답변의 근거가 되는 회사/제품 정보 |
| Chunk | Knowledge를 검색 단위로 자른 텍스트 조각 (`KnowledgeChunk`) |
| Embedding | Chunk 텍스트를 벡터로 변환한 값 (pgvector `vector` 컬럼) |
| Retrieval | 질문 임베딩과 코사인 유사도가 높은 Chunk 상위 K개 검색 |
| SystemSetting | API Key, 모델명 등 관리자가 설정하는 전역 설정 (싱글턴 레코드) |
| 챗봇 활성 상태 | 유효한 API Key가 저장되어 있는 상태. 비활성 시 채팅 입력 불가 |

## 4. 범위

### 포함 (In Scope)
- 익명 채팅 UI (대화 맥락 유지 — 같은 브라우저 세션 내)
- 관리자 로그인/로그아웃 (화면 상단 우측)
- 앱 시작 시 기본 관리자 계정 자동 생성 (`admin` / `admin1234!`)
- 회사 정보, 제품 정보 생성/조회/수정/삭제 + 자동 임베딩
- Claude API Key 등록/변경/삭제 (DB에 암호화 저장, 화면에는 마스킹)
- API Key 미등록 시 채팅 비활성화

### 제외 (Out of Scope, v1)
- 고객 회원가입/로그인
- 파일(PDF, DOCX) 업로드를 통한 지식 등록
- 상담원 연결(Human handoff), 다국어 UI 전환
- 운영 배포 자동화(CI/CD), 멀티 테넌트

## 5. 구현 로드맵 (Phase)

각 Phase 완료 시 테스트 통과 확인 → README 갱신 → 커밋.

| Phase | 내용 | 완료 조건 |
|---|---|---|
| 1. 기반 구성 | 로컬 PostgreSQL 18 + pgvector 설정, Django 프로젝트 + 앱 5개 골격, **`accounts.User` 모델과 `AUTH_USER_MODEL`(첫 migrate 전)**, `common` 공통 모듈, Vue+Vite 프로젝트, `/api/health` | 프론트에서 health 호출 성공, 첫 마이그레이션이 `accounts.User` 기준 |
| 2. 계정 | 기본 관리자 생성, 로그인/로그아웃/me/비밀번호 변경 API, 상단 우측 로그인 UI, SettingsView(비밀번호 카드) | specs/01 F-A1~A3 인수 조건 통과 |
| 3. 시스템 설정 | `SystemSetting`, API Key 암호화 저장/검증/마스킹, `GET /api/chat/status`, 채팅 비활성 UI | F-A6~A7 통과, F-U2 중 status/UI 부분 통과 |
| 4. 지식 관리 | Company/Product CRUD API + 관리자 화면, 청킹·임베딩·pgvector 저장, 검색, 재색인(F-A8), `load_sample_knowledge` | F-A4~A5, F-A8 통과 |
| 5. 챗봇 | 검색 + Claude 스트리밍 응답, 채팅 UI, 채팅 API 커스텀 rate limit | F-U1, F-U3~U5, F-U2(503) 통과 |
| 6. 마무리 | 에러 처리, rate limit 점검, 접근성, `cleanup_chat_sessions`, 감사 로그, 운영 보안 설정, README 최종화 | 전체 인수 조건 통과 |

> Phase 배정 조정 이유: `AUTH_USER_MODEL`은 첫 migrate 전에 설정해야 하므로 User 모델을 Phase 1로 옮겼다. chat 앱 골격은 Phase 1에서 만들고 status API만 Phase 3에서 구현한다. 채팅 메시지 API(503 확인 포함)는 Phase 5에 있다.
