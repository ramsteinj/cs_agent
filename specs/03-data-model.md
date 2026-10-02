# 03. 데이터 모델

모든 모델은 Django ORM으로 정의한다. 공통 필드 `created_at(auto_now_add)`, `updated_at(auto_now)` 를 갖는 추상 모델 `common.models.TimeStampedModel` 을 상속한다 (User 제외).

## 1. ER 개요

```
User (AbstractUser)

Company 1 ──── N Product
   │                 │
   └──── N KnowledgeChunk N ────┘   (source_type + source_id 로 참조)

ChatSession 1 ──── N ChatMessage

SystemSetting (singleton, pk=1)
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
| name | CharField(200) | 필수, (company, name) unique |
| category | CharField(100) | 선택, db_index |
| summary | CharField(500) | 선택 |
| description | TextField | 필수 |
| price | CharField(100) | 선택 (자유 텍스트) |
| features | TextField | 선택 |
| usage_guide | TextField | 선택 |
| faq | TextField | 선택 |
| is_active | BooleanField, default True | db_index |

### KnowledgeChunk
| 필드 | 타입 | 설명 |
|---|---|---|
| source_type | CharField(choices: `company`, `product`) | 출처 종류 |
| source_id | PositiveIntegerField | 출처 PK |
| company | FK(Company, CASCADE) | 검색 필터/연쇄 삭제용 |
| product | FK(Product, CASCADE, null) | 제품 청크일 때만 |
| chunk_index | PositiveIntegerField | 출처 내 순번 |
| content | TextField | 청크 원문 (프롬프트에 그대로 들어감) |
| embedding | `pgvector.django.VectorField(dimensions=EMBEDDING_DIM)` | 기본 384 |
| embedding_model | CharField(200) | 생성에 사용한 모델명 |
| is_searchable | BooleanField, default True | 비활성 제품이면 False |

- 인덱스:
  - `HnswIndex(name="chunk_embedding_hnsw", fields=["embedding"], m=16, ef_construction=64, opclasses=["vector_cosine_ops"])`
  - `(source_type, source_id)` 복합 인덱스
- 제약: `(source_type, source_id, chunk_index)` unique

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
| 필드 | 타입 | 기본값 |
|---|---|---|
| id | 항상 1 | |
| anthropic_api_key_encrypted | TextField(blank) | "" — Fernet 암호문 |
| api_key_last4 | CharField(4, blank) | 마스킹 표시용 |
| api_key_updated_at | DateTimeField(null) | |
| claude_model | CharField(100) | `claude-opus-5-5` |
| bot_name | CharField(100) | `고객지원 챗봇` |
| welcome_message | TextField | `안녕하세요! 회사와 제품에 대해 궁금한 점을 물어보세요.` |
| extra_instructions | TextField(max 2000, blank) | "" |

- 클래스 메서드 `SystemSetting.load()` → `get_or_create(pk=1)`
- `save()` 에서 pk를 1로 고정, `delete()` 금지
- 메서드 `set_api_key(plain)`, `get_api_key() -> str | None`, `clear_api_key()`, 프로퍼티 `chatbot_enabled`
