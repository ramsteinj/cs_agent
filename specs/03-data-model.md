# 03. 데이터 모델

모든 모델은 Django ORM으로 정의한다. 공통 필드 `created_at(auto_now_add)`, `updated_at(auto_now)` 를 갖는 추상 모델 `common.models.TimeStampedModel` 을 상속한다 (User 제외).

## 1. ER 개요

```
User (AbstractUser)

Company 1 ──── N Product 1 ──── N ProductDocument (txt/docx/pdf 추출 텍스트)
   │                 │
   └──── N KnowledgeChunk N ────┘   (source_type + source_id 로 참조)

ChatSession 1 ──── N ChatMessage

SystemSetting (singleton, pk=1) ── 사용할 LLM 공급자, 챗봇 표시, RAG 튜닝 설정
LLMProviderConfig (공급자당 1행: anthropic / openai / gemini) ── 암호화된 API Key, 모델
```

## 2. accounts

### User — `accounts.User(AbstractUser)`
요구 사항: user, admin은 Django `AbstractUser`를 상속해 확장한다. 별도 모델 두 개가 아니라 **하나의 User 모델 + role 필드**로 구분한다.

| 필드 | 타입 | 설명 |
|---|---|---|
| (AbstractUser 기본) | | username, password, email, first_name, last_name, is_staff, is_active, is_superuser, last_login, date_joined |
| role | CharField(choices: `ADMIN`, `USER`), default `USER`, db_index | 관리자/일반 사용자 구분 |
| must_change_password | BooleanField, default False | 기본 비밀번호 사용 중 표시 |
| failed_login_count | PositiveIntegerField, default 0 | 로그인 실패 횟수 |
| locked_until | DateTimeField, null | 로그인 차단 해제 시각 |

- 프로퍼티: `is_admin_role -> role == ADMIN`
- 설정: `AUTH_USER_MODEL = "accounts.User"` (첫 migrate 전)
- 고객은 v1에서 익명이므로 `USER` role 레코드는 생성하지 않지만, 향후 확장을 위해 role을 유지한다.
- Django Admin(`/django-admin/`)에 User 등록 (개발 편의용, 선택).

## 3. knowledge

### Company
| 필드 | 타입 | 제약 |
|---|---|---|
| name | CharField(200) | 필수, unique |
| description | TextField | 필수 |
| website | URLField | 선택 |
| phone | CharField(50) | 선택 |
| email | EmailField | 선택 |
| address | CharField(300) | 선택 |
| business_hours | CharField(200) | 선택 |
| extra_info | TextField | 선택 (정책, FAQ 등) |

### Product
| 필드 | 타입 | 제약 |
|---|---|---|
| company | FK(Company, on_delete=CASCADE, related_name="products") | 필수 |
| name | CharField(200) | 필수, (company, name, category) unique — 이름이 같아도 카테고리가 다르면 등록 가능 |
| category | CharField(100) | 선택, db_index |
| summary | CharField(500) | 선택 |
| description | TextField | 선택 (직접 입력 또는 문서 업로드 중 하나 이상 — 프론트에서 검증) |
| price | CharField(100) | 선택 (자유 텍스트) |
| features | TextField | 선택 |
| usage_guide | TextField | 선택 |
| faq | TextField | 선택 |
| is_active | BooleanField, default True | db_index |

### ProductDocument (제품 정보 문서)
업로드한 Text/MS Word/PDF 파일에서 **추출한 텍스트만** 저장한다 (원본 파일은 보관하지 않음).

| 필드 | 타입 | 설명 |
|---|---|---|
| product | FK(Product, CASCADE, related_name="documents") | |
| title | CharField(200, blank) | 문서 제목(종류). 예: 사용자 매뉴얼, 빠른 설치 가이드. 비면 파일명으로 표시 |
| file_name | CharField(255) | 원본 파일명 (경로 제거) |
| file_type | CharField(choices: `txt`, `docx`, `pdf`) | |
| file_size | PositiveIntegerField | 바이트 |
| text | TextField | 추출 텍스트 (최대 1,000,000자) |

- 제한: 파일 10MB 이하, `.doc`(구형 Word)·암호화 PDF·텍스트가 없는 스캔 PDF는 거부.
- 색인: 제품 청크 생성 시 제품 필드 텍스트 다음에 문서별로 청킹한다 (specs/05 §2.1).

### KnowledgeChunk
| 필드 | 타입 | 설명 |
|---|---|---|
| source_type | CharField(choices: `company`, `product`) | 출처 종류 |
| source_id | PositiveIntegerField | 출처 PK |
| company | FK(Company, CASCADE) | 검색 필터/연쇄 삭제용 |
| product | FK(Product, CASCADE, null) | 제품 청크일 때만 |
| document | FK(ProductDocument, CASCADE, null) | 제품 문서에서 나온 청크일 때만 (출처 표시용) |
| chunk_index | PositiveIntegerField | 출처 내 순번 |
| content | TextField | 청크 원문 (프롬프트에 그대로 들어감) |
| embedding | `pgvector.django.VectorField(dimensions=EMBEDDING_DIM)` | 기본 384 |
| embedding_model | CharField(200) | 생성에 사용한 모델명 (SystemSetting.embedding_model, 테스트는 `fake`) |
| is_searchable | BooleanField, default True | 비활성 제품이면 False |

- 인덱스:
  - `HnswIndex(name="chunk_embedding_hnsw", fields=["embedding"], m=16, ef_construction=64, opclasses=["vector_cosine_ops"])`
  - `(source_type, source_id)` 복합 인덱스
- 제약: `(source_type, source_id, document, chunk_index)` unique (NULL document도 같은 값으로 취급). `chunk_index`는 구역(제품 필드 / 각 문서)마다 0부터 매긴다 — 문서를 따로 색인할 수 있게.

### pgvector 확장 활성화
`knowledge` 앱의 **첫 마이그레이션** 맨 앞에 `pgvector.django.VectorExtension()` 오퍼레이션을 넣어 `CREATE EXTENSION IF NOT EXISTS vector` 를 실행한다.

## 4. chat

### ChatSession
| 필드 | 타입 | 설명 |
|---|---|---|
| id | UUIDField(primary_key, default uuid4) | 프론트가 보관하는 세션 ID |
| client_ip_hash | CharField(64) | rate limit/통계용, SHA-256 해시 (원본 IP 저장 금지) |
| last_activity_at | DateTimeField | |

### ChatMessage
| 필드 | 타입 | 설명 |
|---|---|---|
| session | FK(ChatSession, CASCADE, related_name="messages") | |
| role | CharField(choices: `user`, `assistant`) | |
| content | TextField | |
| retrieved_chunk_ids | JSONField(default list) | 답변 근거로 사용한 청크 ID (assistant만) |
| model | CharField(100, blank) | 응답 생성 모델 |
| input_tokens / output_tokens | PositiveIntegerField(null) | 사용량 |
| status | CharField(choices: `ok`, `error`), default ok | |

- 보존 정책: 마지막 활동 후 30일 지난 세션은 `cleanup_chat_sessions` 커맨드로 삭제.

## 5. settings_app

### SystemSetting (싱글턴)
| 필드 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| id | 항상 1 | | |
| llm_provider | CharField(choices: `anthropic`, `openai`, `gemini`) | `anthropic` | 챗봇이 사용할 LLM (Claude / ChatGPT / Gemini) |
| bot_name | CharField(100) | `고객지원 챗봇` | |
| welcome_message | TextField | `안녕하세요! 회사와 제품에 대해 궁금한 점을 물어보세요.` | |
| system_prompt | TextField(max 10000) | specs/05 §4.3 기본 문구 (`chat.prompts.default_system_prompt`) | LLM 시스템 프롬프트. `{bot_name}` 치환 |
| extra_instructions | TextField(max 2000, blank) | "" | 시스템 프롬프트 뒤에 "운영자 추가 지시"로 덧붙임 |
| embedding_model | CharField(200) | `intfloat/multilingual-e5-small` | RAG: 임베딩 모델 (EMBEDDING_DIM 차원이어야 함) |
| chunk_max_chars | PositiveIntegerField | 500 | RAG: 청크 최대 길이 (100~4000) |
| chunk_overlap_chars | PositiveIntegerField | 100 | RAG: 청크 겹침 (0 이상, chunk_max_chars 미만) |
| retrieval_top_k | PositiveIntegerField | 5 | RAG: 검색할 청크 수 (1~20) |
| retrieval_max_distance | FloatField | 0.6 | RAG: 코사인 거리 상한 (0~2) |
| search_with_previous_question | BooleanField | True | RAG: 검색어에 직전 질문 포함 |
| history_messages | PositiveIntegerField | 10 | RAG: LLM에 보낼 이전 메시지 수 (0~50) |
| max_sources | PositiveIntegerField | 3 | RAG: 답변 아래 표시할 출처 수 (0~10) |
| llm_max_output_tokens | PositiveIntegerField | 4096 | 답변 최대 출력 토큰 (256~32000) |

- 클래스 메서드 `SystemSetting.load()` → `get_or_create(pk=1)`
- `save()` 에서 pk를 1로 고정, `delete()` 금지
- 프로퍼티 `active_provider_config` (llm_provider의 LLMProviderConfig), `chatbot_enabled` (선택된 공급자의 키와 모델이 모두 설정됨)
- 환경 변수로 남는 값: `EMBEDDING_BACKEND`(테스트용 fake), `EMBEDDING_DIM`(DB 스키마), 입력 길이·요청 횟수 제한(보안 설정, specs/07)

### LLMProviderConfig (공급자별 1행)
| 필드 | 타입 | 기본값 |
|---|---|---|
| provider | CharField(choices: `anthropic`, `openai`, `gemini`), unique | |
| api_key_encrypted | TextField(blank) | "" — Fernet 암호문 |
| api_key_hint | CharField(32, blank) | 마스킹 표시용 (예: `sk-ant-...abcd`) |
| api_key_updated_at | DateTimeField(null) | |
| model | CharField(100, blank) | anthropic: `claude-opus-5-5`, openai/gemini: "" (관리자가 목록에서 선택) |
| temperature | FloatField(null) | null — 모델 기본값 사용. 지원하지 않는 모델이면 저장돼 있어도 무시 |

- `LLMProviderConfig.get(provider)` → `get_or_create` (기본 모델 적용)
- 메서드 `set_api_key(plain)`, `get_api_key() -> str | None`(복호화 실패 시 None), `clear_api_key()`, 프로퍼티 `api_key_configured`, `ready`(키와 모델 모두 있음)
- 공급자를 바꿔도 다른 공급자의 키와 모델은 그대로 유지된다.
