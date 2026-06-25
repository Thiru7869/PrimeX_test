# 07 — Backend Folder Structure

**Document:** PrimeX AI Implementation Documentation
**Version:** 1.0.0
**Status:** Approved — Implementation Ready
**Scope:** Complete FastAPI backend application architecture, module definitions, layer boundaries, and dependency rules

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Backend Design Philosophy](#2-backend-design-philosophy)
3. [FastAPI Architecture Overview](#3-fastapi-architecture-overview)
4. [Complete Backend Tree](#4-complete-backend-tree)
5. [Core Layer](#5-core-layer)
6. [API Layer](#6-api-layer)
7. [Domain Modules](#7-domain-modules)
   - [7.1 Authentication Module](#71-authentication-module)
   - [7.2 Users Module](#72-users-module)
   - [7.3 Chat Module](#73-chat-module)
   - [7.4 AI Gateway Module](#74-ai-gateway-module)
   - [7.5 Files Module](#75-files-module)
   - [7.6 Knowledge Bases Module](#76-knowledge-bases-module)
   - [7.7 RAG Module](#77-rag-module)
   - [7.8 Memory Module](#78-memory-module)
   - [7.9 Search Module](#79-search-module)
   - [7.10 Analytics Module](#710-analytics-module)
   - [7.11 Admin Module](#711-admin-module)
8. [Services Layer](#8-services-layer)
9. [Repository Layer](#9-repository-layer)
10. [Models Layer](#10-models-layer)
11. [Schemas Layer](#11-schemas-layer)
12. [AI Gateway Layer](#12-ai-gateway-layer)
13. [File Processing Layer](#13-file-processing-layer)
14. [Background Jobs](#14-background-jobs)
15. [Middleware](#15-middleware)
16. [Observability](#16-observability)
17. [Security Architecture](#17-security-architecture)
18. [Dependency Rules](#18-dependency-rules)
19. [Scaling Strategy](#19-scaling-strategy)
20. [Anti-Patterns](#20-anti-patterns)
21. [Conclusion](#21-conclusion)

---

## 1. Executive Summary

The PrimeX AI backend is a **FastAPI application** organized around a **layered domain module architecture**. It is not a microservices system, but it is designed so that any domain module can be extracted into an independent service in a future phase without restructuring existing code.

Every architectural decision in this document is made against a specific criterion: will this still be correct in Year 3 of PrimeX AI's development?

**Core structural decisions made in this document:**

| Decision | Choice | Rationale |
|---|---|---|
| Module pattern | Domain-first within each module | Feature cohesion; engineer knows exactly where to look |
| SQLAlchemy models | Centralized in `app/models/` | Avoids circular imports; Alembic requires full model import graph |
| Pydantic schemas | Centralized in `app/schemas/` | Single source of schema truth; DRY across module boundaries |
| Repository layer | Dedicated `app/repositories/` layer | Decouples persistence from business logic; testable |
| AI Gateway | Isolated in `app/gateway/` | Zero other module may call AI providers directly |
| File processing | Isolated in `app/processing/` | Stateless parsers; composable; independently testable |
| Background jobs | Isolated in `app/jobs/` | Async workloads never block the request lifecycle |
| Middleware | Isolated in `app/middleware/` | Applied globally in `main.py`; no business logic |

**What this architecture is not:**
- It is not hexagonal architecture. The extra abstraction layers of ports-and-adapters are not justified for a solo/small-team project.
- It is not Clean Architecture in the strict Uncle Bob sense. Dependency inversion is applied pragmatically, not dogmatically.
- It is not a microservices system. All modules share one database, one deployment, one process.

---

## 2. Backend Design Philosophy

### 2.1 Layers Enforce Correctness

The backend is divided into strict layers. Each layer has one job. The order of layers is the order of data flow:

```
HTTP Request
    ↓
[Middleware]         — Authentication, logging, rate limiting (no business logic)
    ↓
[API Layer]          — HTTP parsing, validation, routing (no business logic)
    ↓
[Module Service]     — Business logic ONLY (no HTTP, no SQL)
    ↓
[Repository Layer]   — Database access ONLY (no business logic)
    ↓
[Model Layer]        — SQLAlchemy ORM definitions (no logic)
    ↓
PostgreSQL / R2
```

This layering is enforced by code review and tested by the lack of `Request` objects in service functions and the lack of SQL queries in API route handlers.

### 2.2 Modules Are Features

A "module" in PrimeX AI maps to a feature domain, not a technical concern. The `auth` module owns everything related to authentication: its service, its repository, its FastAPI dependencies (like `get_current_user`), and its exceptions. An engineer working on authentication works only in `app/modules/auth/`. They do not touch `app/services/`, `app/utils/`, or any other module.

The exception to this rule: SQLAlchemy models and Pydantic schemas are centralized (see Sections 10 and 11). This is a pragmatic concession to Python's import system and Alembic's requirements.

### 2.3 The AI Gateway Is Sacred

No module in PrimeX AI calls an AI provider (Gemini, Groq, OpenRouter) directly. All AI requests flow through `app/gateway/`. This is a hard architectural rule, not a preference.

**Why this matters:** AI providers change APIs, deprecate models, and have different rate limits. When Gemini updates its streaming API, the change happens in one file (`app/gateway/providers/gemini.py`) and every module that uses AI automatically benefits. Without this rule, the same change would require hunting through the entire codebase.

### 2.4 Repositories Are Thin

Repository functions do exactly one thing: translate business queries into database queries and return domain objects. They do not contain conditional logic ("if the user has premium, query differently"), they do not call services, and they do not log business events. They query the database. That is all.

### 2.5 Generous Schema, Lazy Code

This is PrimeX AI's core philosophy applied to the backend: design the database schema to accommodate future phases, but write only the code needed for the current phase. A `files` table has a `metadata` JSONB column — it is always available for future structured metadata — but the application does not write to it until a phase requires it.

---

## 3. FastAPI Architecture Overview

### 3.1 Application Bootstrap Sequence

The FastAPI application starts in `app/main.py`. The bootstrap sequence is:

1. **Configuration loaded** — `app/config.py` reads all environment variables and validates them using Pydantic Settings. If any required variable is missing, the application fails immediately with a clear error message. No silent defaults for production-critical values.

2. **Database connection established** — SQLAlchemy engine and session factory are created in `app/core/database.py`. Alembic handles all schema migrations before the application starts; the application never calls `Base.metadata.create_all()` in production.

3. **Middleware registered** — CORS, authentication, logging, and rate limiting middleware are applied in `app/main.py`. Order matters: authentication middleware runs before logging so user context is available in logs.

4. **Routers mounted** — All domain module routers are imported and mounted at their versioned prefixes (`/api/v1/auth`, `/api/v1/chat`, etc.) via the aggregate router in `app/api/v1/router.py`.

5. **Health check registered** — A `/health` endpoint is registered at the root level (not under `/api/v1/`) for infrastructure health monitoring.

6. **Sentry initialized** — Error reporting is configured in the startup event handler.

### 3.2 Request Lifecycle

Every authenticated request in PrimeX AI follows this exact lifecycle:

```
POST /api/v1/chat/messages
    ↓ CORSMiddleware validates origin
    ↓ AuthMiddleware extracts JWT, validates, attaches User to request state
    ↓ LoggingMiddleware records request start
    ↓ FastAPI routes to chat.router.create_message()
    ↓ Pydantic validates request body (CreateMessageRequest)
    ↓ get_current_user dependency confirms user is active
    ↓ chat.router calls chat.service.create_message(user_id, request)
    ↓ chat.service validates business rules (session exists, user owns it)
    ↓ chat.service calls gateway.complete(messages, provider_config)
    ↓ gateway.router selects provider, calls provider, handles fallback
    ↓ chat.service calls chat.repository.save_message(session_id, message)
    ↓ chat.repository executes INSERT via SQLAlchemy session
    ↓ chat.router returns MessageResponse
    ↓ LoggingMiddleware records response duration and status
```

### 3.3 Versioning Strategy

All API routes are prefixed with `/api/v1/`. When breaking changes are required (Phase 5+), routes are added under `/api/v2/` while `/api/v1/` remains available. The version prefix is a router namespace; the underlying service logic is shared across versions wherever possible.

---

## 4. Complete Backend Tree

```
apps/api/
│
├── .env.example                     # All required environment variables documented
├── .env                             # [gitignored] Local values
├── .dockerignore
├── Dockerfile                       # Development image (fast rebuild)
├── pyproject.toml                   # Poetry + ruff + mypy + pytest configuration
├── poetry.lock
├── alembic.ini                      # Alembic configuration (points to DATABASE_URL)
│
├── app/
│   ├── __init__.py
│   ├── main.py                      # FastAPI app factory, middleware, router mount
│   ├── config.py                    # Pydantic Settings — all env vars
│   ├── dependencies.py              # Shared FastAPI dependencies (db session, current user)
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── database.py              # Engine, SessionLocal, Base, get_db dependency
│   │   ├── security.py              # JWT encode/decode, password hashing (bcrypt)
│   │   ├── exceptions.py            # Custom exception classes + global handlers
│   │   └── events.py                # Startup and shutdown event handlers
│   │
│   ├── api/
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── router.py            # Aggregates all module routers
│   │       ├── auth.py              # HTTP routes: /auth/register, /auth/login, /auth/refresh
│   │       ├── users.py             # HTTP routes: /users/me, /users/{id}
│   │       ├── chat.py              # HTTP routes: /chat/sessions, /chat/messages (SSE)
│   │       ├── files.py             # HTTP routes: /files/upload, /files/{id}
│   │       ├── knowledge.py         # HTTP routes: /knowledge/collections, /knowledge/documents
│   │       ├── memory.py            # HTTP routes: /memory, /memory/{id}
│   │       ├── search.py            # HTTP routes: /search
│   │       ├── analytics.py         # HTTP routes: /analytics/usage
│   │       └── admin.py             # HTTP routes: /admin/users, /admin/system
│   │
│   ├── modules/
│   │   ├── auth/
│   │   │   ├── __init__.py
│   │   │   ├── service.py           # register(), login(), refresh_token(), logout()
│   │   │   ├── dependencies.py      # get_current_user(), require_admin()
│   │   │   └── exceptions.py        # InvalidCredentials, TokenExpired, UserNotFound
│   │   │
│   │   ├── users/
│   │   │   ├── __init__.py
│   │   │   ├── service.py           # get_profile(), update_profile(), get_preferences()
│   │   │   └── exceptions.py        # UserAlreadyExists, ProfileNotFound
│   │   │
│   │   ├── chat/
│   │   │   ├── __init__.py
│   │   │   ├── service.py           # create_session(), send_message(), stream_response()
│   │   │   ├── streaming.py         # SSE generator; assembles stream from gateway chunks
│   │   │   └── exceptions.py        # SessionNotFound, SessionExpired, MessageTooLong
│   │   │
│   │   ├── files/
│   │   │   ├── __init__.py
│   │   │   ├── service.py           # upload_file(), get_file(), delete_file(), list_files()
│   │   │   ├── pipeline.py          # Orchestrates: validate → upload R2 → parse → embed
│   │   │   └── exceptions.py        # UnsupportedFileType, FileTooLarge, ParseFailure
│   │   │
│   │   ├── knowledge/
│   │   │   ├── __init__.py
│   │   │   ├── service.py           # create_collection(), add_document(), list_collections()
│   │   │   └── exceptions.py        # CollectionNotFound, DocumentAlreadyInCollection
│   │   │
│   │   ├── rag/
│   │   │   ├── __init__.py
│   │   │   ├── service.py           # query_collection(), augment_prompt(), retrieve_chunks()
│   │   │   ├── chunker.py           # Text chunking strategies (fixed, semantic, hierarchical)
│   │   │   ├── embedder.py          # Embedding generation (calls AI Gateway)
│   │   │   └── retriever.py         # pgvector similarity search + reranking
│   │   │
│   │   ├── memory/
│   │   │   ├── __init__.py
│   │   │   ├── service.py           # save_memory(), recall_memory(), list_memories()
│   │   │   ├── extractor.py         # Extract memory-worthy facts from conversations
│   │   │   └── exceptions.py        # MemoryNotFound, MemoryLimitExceeded
│   │   │
│   │   ├── search/
│   │   │   ├── __init__.py
│   │   │   ├── service.py           # search(), search_with_citations(), hybrid_search()
│   │   │   └── ranker.py            # Result scoring, deduplication, citation assembly
│   │   │
│   │   ├── analytics/
│   │   │   ├── __init__.py
│   │   │   └── service.py           # get_usage_stats(), get_token_consumption(), get_costs()
│   │   │
│   │   └── admin/
│   │       ├── __init__.py
│   │       ├── service.py           # list_users(), suspend_user(), get_system_health()
│   │       └── exceptions.py        # AdminActionForbidden, CannotSuspendSelf
│   │
│   ├── models/                      # SQLAlchemy ORM models (ALL models centralized here)
│   │   ├── __init__.py              # Imports every model so Alembic can see the full graph
│   │   ├── base.py                  # DeclarativeBase, TimestampMixin, UUIDMixin
│   │   ├── user.py                  # User, UserSession
│   │   ├── chat.py                  # ChatSession, ChatMessage
│   │   ├── file.py                  # UploadedFile, FileChunk
│   │   ├── knowledge.py             # Collection, CollectionDocument, KnowledgeDocument
│   │   ├── memory.py                # Memory
│   │   ├── search.py                # SearchHistory
│   │   └── analytics.py             # UsageRecord, TokenConsumption
│   │
│   ├── schemas/                     # Pydantic schemas (ALL schemas centralized here)
│   │   ├── __init__.py
│   │   ├── common.py                # PaginatedResponse[T], ApiError, UUIDStr, OrderBy
│   │   ├── auth.py                  # RegisterRequest, LoginRequest, TokenResponse, TokenPayload
│   │   ├── users.py                 # UserProfile, UpdateProfileRequest, UserPreferences
│   │   ├── chat.py                  # CreateSessionRequest, CreateMessageRequest, MessageResponse, StreamChunk
│   │   ├── files.py                 # FileUploadResponse, FileDetail, FileListResponse
│   │   ├── knowledge.py             # CreateCollectionRequest, CollectionDetail, AddDocumentRequest
│   │   ├── memory.py                # SaveMemoryRequest, MemoryDetail, RecallQuery
│   │   ├── search.py                # SearchQuery, SearchResult, SearchResponse
│   │   ├── analytics.py             # UsageStats, ProviderMetrics, CostSummary
│   │   └── admin.py                 # AdminUserList, SystemHealth, SuspendUserRequest
│   │
│   ├── repositories/                # Data access layer (one repository per domain)
│   │   ├── __init__.py
│   │   ├── base.py                  # GenericRepository[T] — CRUD helpers
│   │   ├── user.py                  # UserRepository: find_by_email(), find_by_id(), create()
│   │   ├── chat.py                  # ChatRepository: create_session(), save_message(), get_history()
│   │   ├── file.py                  # FileRepository: save_file(), save_chunks(), get_file()
│   │   ├── knowledge.py             # KnowledgeRepository: create_collection(), add_document()
│   │   ├── memory.py                # MemoryRepository: save(), search_by_embedding(), list()
│   │   ├── search.py                # SearchRepository: save_history(), get_recent()
│   │   └── analytics.py             # AnalyticsRepository: record_usage(), aggregate_by_period()
│   │
│   ├── gateway/                     # AI Gateway — isolated from all domain modules
│   │   ├── __init__.py
│   │   ├── gateway.py               # AIGateway: public interface for all AI calls
│   │   ├── router.py                # Provider selection logic, priority, health check
│   │   ├── tracker.py               # Token and usage tracking (writes to analytics)
│   │   ├── health.py                # Provider health probe, circuit breaker state
│   │   ├── exceptions.py            # AllProvidersUnavailable, TokenLimitExceeded
│   │   └── providers/
│   │       ├── __init__.py
│   │       ├── base.py              # AIProvider ABC: complete(), stream(), embed()
│   │       ├── gemini.py            # Gemini implementation (primary)
│   │       ├── groq.py              # Groq implementation (fallback)
│   │       └── openrouter.py        # OpenRouter implementation (Phase 5)
│   │
│   ├── processing/                  # File processing pipeline — stateless parsers
│   │   ├── __init__.py
│   │   ├── pipeline.py              # FileProcessingPipeline: orchestrates parse → chunk → embed
│   │   ├── parsers/
│   │   │   ├── __init__.py
│   │   │   ├── base.py              # FileParser ABC: parse(file_bytes) → ParsedDocument
│   │   │   ├── pdf.py               # PDF parser (pdfplumber)
│   │   │   ├── docx.py              # DOCX parser (python-docx)
│   │   │   ├── txt.py               # Plain text parser
│   │   │   ├── csv.py               # CSV parser (Phase 7)
│   │   │   ├── xlsx.py              # XLSX parser (Phase 7)
│   │   │   └── pptx.py              # PPTX parser (Phase 7)
│   │   └── extractors/
│   │       ├── __init__.py
│   │       ├── metadata.py          # Extracts title, author, page count, word count
│   │       └── structure.py         # Extracts headings, sections, table of contents
│   │
│   ├── storage/                     # Cloudflare R2 storage client
│   │   ├── __init__.py
│   │   ├── client.py                # R2Client: boto3 S3-compatible client wrapper
│   │   └── operations.py            # upload(), download(), delete(), generate_presigned_url()
│   │
│   ├── jobs/                        # Background task definitions
│   │   ├── __init__.py
│   │   ├── worker.py                # FastAPI BackgroundTasks coordinator
│   │   └── tasks/
│   │       ├── __init__.py
│   │       ├── process_file.py      # Async file processing after upload confirmation
│   │       ├── generate_summary.py  # Async document summarization
│   │       └── extract_memory.py    # Async memory extraction from conversations
│   │
│   ├── middleware/
│   │   ├── __init__.py
│   │   ├── auth.py                  # JWT extraction and validation
│   │   ├── cors.py                  # CORS configuration
│   │   ├── logging.py               # Structured request/response logging
│   │   └── rate_limit.py            # Per-user rate limiting (Phase 1)
│   │
│   └── observability/
│       ├── __init__.py
│       ├── logger.py                # Structured logger (structlog)
│       ├── metrics.py               # Custom metrics definitions
│       └── sentry.py                # Sentry initialization and custom fingerprinting
│
├── migrations/                      # Alembic migration files
│   ├── env.py                       # Alembic environment (reads DATABASE_URL, imports all models)
│   ├── script.py.mako               # Migration file template
│   └── versions/
│       ├── 0001_initial_schema.py   # Users, sessions
│       └── 0002_add_chat_tables.py  # ChatSession, ChatMessage
│
└── tests/
    ├── __init__.py
    ├── conftest.py                  # Fixtures: test client, test database, mock user
    ├── factories/
    │   ├── user.py                  # UserFactory (faker-based)
    │   ├── chat.py                  # ChatSessionFactory, ChatMessageFactory
    │   └── file.py                  # UploadedFileFactory
    ├── unit/
    │   ├── modules/
    │   │   ├── test_auth_service.py
    │   │   ├── test_chat_service.py
    │   │   ├── test_file_service.py
    │   │   └── test_rag_service.py
    │   ├── gateway/
    │   │   ├── test_gateway_router.py
    │   │   └── test_provider_fallback.py
    │   └── processing/
    │       ├── test_pdf_parser.py
    │       └── test_chunker.py
    └── integration/
        ├── test_auth_api.py
        ├── test_chat_api.py
        ├── test_files_api.py
        └── test_search_api.py
```

---

## 5. Core Layer

**Location:** `app/core/`

The core layer is the application's infrastructure foundation. It provides the building blocks that all other layers depend on. It has no knowledge of business logic.

### 5.1 `database.py`

Owns the SQLAlchemy engine, session factory, and the database dependency.

**Responsibilities:**
- Create the SQLAlchemy engine using `DATABASE_URL` from config
- Configure connection pool settings (pool size, overflow, timeout)
- Provide `SessionLocal` — a session factory for repository use
- Provide `get_db()` — a FastAPI dependency that yields a database session and guarantees cleanup

**Critical rule:** `Base` (the `DeclarativeBase` instance) is defined here. All SQLAlchemy models import from `app.core.database`. There is exactly one `Base` in the application.

```
get_db() dependency flow:
  yield SessionLocal()
  → on success: session.commit()
  → on exception: session.rollback()
  → always: session.close()
```

### 5.2 `security.py`

Owns all cryptographic operations. This file knows about JWT and bcrypt, nothing else.

**Responsibilities:**
- `hash_password(plain: str) → str` — bcrypt hash generation
- `verify_password(plain: str, hashed: str) → bool` — bcrypt verification
- `create_access_token(data: dict, expires_delta: timedelta) → str` — JWT creation
- `decode_access_token(token: str) → dict` — JWT decoding and validation
- `create_refresh_token(user_id: UUID) → str` — Longer-lived token for session refresh

**No other module implements cryptography.** If a module needs to check a password, it calls `security.verify_password()`. If it needs a token, it calls `security.create_access_token()`.

### 5.3 `exceptions.py`

Defines the application exception hierarchy and registers global exception handlers with FastAPI.

**Exception hierarchy:**
```
PrimeXException (base)
  ├── NotFoundError (404)
  ├── ValidationError (422)
  ├── AuthenticationError (401)
  ├── AuthorizationError (403)
  ├── ConflictError (409)
  ├── RateLimitError (429)
  └── ServiceUnavailableError (503)
```

Each domain module extends these base exceptions with specific types (e.g., `SessionNotFound(NotFoundError)`). The global handler in `exceptions.py` catches any `PrimeXException` and returns a structured JSON error response that matches the `ApiError` schema.

### 5.4 `events.py`

Contains startup and shutdown event handlers registered with the FastAPI application.

**Startup:** Verify database connectivity, initialize Sentry, warm up the AI Gateway (test provider connectivity), log application start with version and environment.

**Shutdown:** Close database connection pool, flush any pending logs, close storage client connections.

---

## 6. API Layer

**Location:** `app/api/v1/`

The API layer is responsible for exactly three things:
1. Parsing HTTP request parameters (path, query, body) via Pydantic
2. Calling the appropriate module service
3. Returning an HTTP response

The API layer contains **no business logic**. A route handler that is more than 10 lines long is a sign that business logic has leaked into the API layer.

### 6.1 `router.py` — Aggregate Router

`app/api/v1/router.py` imports every domain router and mounts them with their prefixes:

```
/api/v1/auth         → auth.py router
/api/v1/users        → users.py router
/api/v1/chat         → chat.py router
/api/v1/files        → files.py router
/api/v1/knowledge    → knowledge.py router
/api/v1/memory       → memory.py router
/api/v1/search       → search.py router
/api/v1/analytics    → analytics.py router
/api/v1/admin        → admin.py router
```

`main.py` mounts only this single aggregate router. Adding a new domain requires adding one line to `router.py`.

### 6.2 Route Handler Standard

Every route handler follows this exact pattern:

```python
@router.post("/messages", response_model=MessageResponse, status_code=201)
async def create_message(
    request: CreateMessageRequest,
    session_id: UUID = Path(...),
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
) -> MessageResponse:
    return await service.create_message(
        user_id=current_user.id,
        session_id=session_id,
        request=request,
    )
```

**Rules enforced by code review:**
- Route handlers are `async`
- Dependencies are injected via `Depends()`
- Route handlers call exactly one service method
- Route handlers never access the database directly
- Route handlers never contain `if/else` business logic
- Streaming routes use `StreamingResponse` with an `async_generator`

---

## 7. Domain Modules

Domain modules live in `app/modules/`. Each module owns the business logic for one feature domain. Modules communicate with each other only through their service interfaces — never through repositories or models directly.

---

### 7.1 Authentication Module

**Location:** `app/modules/auth/`

**Purpose:** Everything related to user identity — registration, login, token management, and session lifecycle.

**Folder structure:**
```
app/modules/auth/
├── __init__.py
├── service.py
├── dependencies.py
└── exceptions.py
```

**`service.py` responsibilities:**
- `register(request: RegisterRequest) → TokenResponse` — Create user, hash password, issue tokens
- `login(request: LoginRequest) → TokenResponse` — Verify credentials, issue tokens, record session
- `refresh_token(refresh_token: str) → TokenResponse` — Validate refresh token, issue new access token
- `logout(user_id: UUID, session_id: UUID) → None` — Invalidate session record
- `revoke_all_sessions(user_id: UUID) → None` — Security: invalidate all active sessions for a user

**`dependencies.py` responsibilities:**
- `get_current_user(token: str = Header()) → User` — Decode JWT, load user from database, verify user is active. This is the most commonly imported function in the entire backend — every authenticated route depends on it.
- `require_admin(user: User = Depends(get_current_user)) → User` — Verify user has admin role. Raises `AuthorizationError` if not.

**`exceptions.py` contents:**
- `InvalidCredentials(AuthenticationError)` — Wrong email or password
- `TokenExpired(AuthenticationError)` — JWT past its expiry time
- `TokenInvalid(AuthenticationError)` — Malformed or tampered JWT
- `AccountDisabled(AuthenticationError)` — User account is suspended

**Allowed dependencies:**
- `app.core.security` — Password hashing and token operations
- `app.repositories.user` — User record access
- `app.schemas.auth` — Request/response types
- `app.models.user` — User and UserSession models

**Forbidden dependencies:**
- Any other module's service or repository
- `app.gateway` — Auth does not call AI
- `app.processing` — Auth does not process files

---

### 7.2 Users Module

**Location:** `app/modules/users/`

**Purpose:** User profile management, preferences, and account settings. Distinct from authentication — auth handles identity and sessions; users handles profile data.

**Folder structure:**
```
app/modules/users/
├── __init__.py
├── service.py
└── exceptions.py
```

**`service.py` responsibilities:**
- `get_profile(user_id: UUID) → UserProfile` — Return the user's current profile data
- `update_profile(user_id: UUID, request: UpdateProfileRequest) → UserProfile` — Update display name, avatar URL, timezone
- `get_preferences(user_id: UUID) → UserPreferences` — Return stored user preferences (JSONB field)
- `update_preferences(user_id: UUID, preferences: dict) → UserPreferences` — Merge preference updates (additive, not replacement)
- `delete_account(user_id: UUID) → None` — Soft-delete user data (sets `deleted_at`, does not destroy records)

**`exceptions.py` contents:**
- `UserAlreadyExists(ConflictError)` — Email already registered
- `ProfileNotFound(NotFoundError)` — User ID not found (should be rare; indicates data integrity issue)

**Allowed dependencies:**
- `app.repositories.user`
- `app.schemas.users`
- `app.models.user`

**Forbidden dependencies:**
- `app.modules.auth` — Users module does not verify passwords or issue tokens
- `app.gateway` — Profile updates do not call AI providers
- Any other module's service

---

### 7.3 Chat Module

**Location:** `app/modules/chat/`

**Purpose:** Chat session management, message persistence, and response streaming. This is PrimeX AI's highest-traffic module.

**Folder structure:**
```
app/modules/chat/
├── __init__.py
├── service.py
├── streaming.py
└── exceptions.py
```

**`service.py` responsibilities:**
- `create_session(user_id: UUID, title: str | None) → ChatSession` — Initialize a new conversation context
- `list_sessions(user_id: UUID, page: int, per_page: int) → PaginatedResponse[ChatSession]` — Paginated session history
- `get_session(user_id: UUID, session_id: UUID) → ChatSession` — Retrieve a specific session (validates ownership)
- `delete_session(user_id: UUID, session_id: UUID) → None` — Soft-delete session and its messages
- `send_message(user_id: UUID, session_id: UUID, content: str) → AsyncGenerator[StreamChunk, None]` — Core method. Saves user message, calls AI gateway, streams response, saves assistant message
- `get_messages(user_id: UUID, session_id: UUID) → list[ChatMessage]` — Retrieve session message history for context

**`streaming.py` responsibilities:**
This file is responsible for the SSE (Server-Sent Events) stream from the chat endpoint. It wraps the gateway's async generator and formats each chunk as an SSE event, adds metadata (token count, provider name, finish reason), handles stream errors gracefully, and sends a `[DONE]` terminator.

```
Streaming flow:
  client → POST /chat/messages
  → service.send_message() returns AsyncGenerator
  → streaming.py wraps in SSE format
  → StreamingResponse yields to client
  → client receives chunks in real-time
  → final chunk includes full token count
```

**`exceptions.py` contents:**
- `SessionNotFound(NotFoundError)` — Session ID does not exist or belongs to another user
- `SessionExpired(ValidationError)` — Session is too old and has been archived
- `MessageTooLong(ValidationError)` — Input exceeds configured token limit
- `SessionLimitReached(ConflictError)` — User has reached maximum active session count

**Allowed dependencies:**
- `app.gateway` — Chat is the primary consumer of the AI Gateway
- `app.repositories.chat`
- `app.schemas.chat`
- `app.models.chat`

**Forbidden dependencies:**
- Direct AI provider calls (only through `app.gateway`)
- `app.modules.files` — Chat does not process files (files module triggers its own pipeline)
- `app.repositories.user` — Chat never directly queries user records; user ownership is validated by the auth dependency before reaching the service

---

### 7.4 AI Gateway Module

The AI Gateway is both a layer (`app/gateway/`) and conceptually a module. It is fully documented in [Section 12](#12-ai-gateway-layer).

---

### 7.5 Files Module

**Location:** `app/modules/files/`

**Purpose:** File upload orchestration, lifecycle management, and status tracking. The files module does not parse content itself — it delegates to `app/processing/`.

**Folder structure:**
```
app/modules/files/
├── __init__.py
├── service.py
├── pipeline.py
└── exceptions.py
```

**`service.py` responsibilities:**
- `upload_file(user_id: UUID, file: UploadFile) → FileUploadResponse` — Validate type and size, generate storage key, hand off to pipeline
- `get_file(user_id: UUID, file_id: UUID) → FileDetail` — Retrieve file metadata and current processing status
- `list_files(user_id: UUID, status: FileStatus | None) → PaginatedResponse[FileDetail]` — Paginated file listing, optionally filtered by processing status
- `delete_file(user_id: UUID, file_id: UUID) → None` — Soft-delete file record, schedule R2 deletion in background job
- `get_file_content(user_id: UUID, file_id: UUID) → str` — Retrieve extracted text (for Q&A, summaries). Only available when status is `COMPLETED`.
- `get_download_url(user_id: UUID, file_id: UUID) → str` — Generate a time-limited presigned R2 URL for direct download

**`pipeline.py` responsibilities:**
Orchestrates the multi-step file processing workflow. This is called by the background job `jobs/tasks/process_file.py`:

```
Step 1: Update file status → PROCESSING
Step 2: Download file bytes from R2 (uploaded raw)
Step 3: Detect MIME type, select appropriate parser from app.processing.parsers
Step 4: Parse file → ParsedDocument (title, raw text, metadata, page structure)
Step 5: Save parsed text back to R2 as {file_id}_content.txt
Step 6: Generate embeddings via RAG module's embedder
Step 7: Save chunks + embeddings to FileChunk table
Step 8: Update file status → COMPLETED
Step 9 (on any failure): Update file status → FAILED, record error details
```

**`exceptions.py` contents:**
- `UnsupportedFileType(ValidationError)` — MIME type not in allowed list
- `FileTooLarge(ValidationError)` — Exceeds configured max file size (default: 50MB)
- `ParseFailure(ServiceUnavailableError)` — Parser raised an exception
- `FileNotFound(NotFoundError)` — File ID not found or belongs to another user
- `FileNotReady(ValidationError)` — Attempting to access content before processing completes

**Allowed dependencies:**
- `app.storage` — R2 upload and download
- `app.processing` — File parsers
- `app.modules.rag` — Embedding generation
- `app.repositories.file`
- `app.schemas.files`
- `app.models.file`

**Forbidden dependencies:**
- `app.gateway` — Files module does not call AI directly (RAG module handles this)
- `app.modules.knowledge` — File upload is not collection-aware; adding to a collection is a knowledge module operation

---

### 7.6 Knowledge Bases Module

**Location:** `app/modules/knowledge/`

**Purpose:** Organizing files into named collections for structured Q&A and retrieval. A collection is a named group of documents that can be queried together.

**Folder structure:**
```
app/modules/knowledge/
├── __init__.py
├── service.py
└── exceptions.py
```

**`service.py` responsibilities:**
- `create_collection(user_id: UUID, name: str, description: str) → CollectionDetail` — Create a new named collection
- `list_collections(user_id: UUID) → list[CollectionDetail]` — All user collections with document counts
- `get_collection(user_id: UUID, collection_id: UUID) → CollectionDetail` — Single collection with full document list
- `delete_collection(user_id: UUID, collection_id: UUID) → None` — Delete collection record (does not delete the documents)
- `add_document(user_id: UUID, collection_id: UUID, file_id: UUID) → None` — Link a processed file to a collection. File must have `status=COMPLETED`.
- `remove_document(user_id: UUID, collection_id: UUID, file_id: UUID) → None` — Unlink document from collection
- `query_collection(user_id: UUID, collection_id: UUID, query: str) → QueryResponse` — Semantic Q&A against collection contents

**`exceptions.py` contents:**
- `CollectionNotFound(NotFoundError)`
- `DocumentAlreadyInCollection(ConflictError)`
- `DocumentNotReady(ValidationError)` — File must be in COMPLETED status before adding to collection
- `DocumentNotInCollection(NotFoundError)`

**Allowed dependencies:**
- `app.modules.rag` — Collection queries go through RAG
- `app.repositories.knowledge`
- `app.repositories.file` — To verify file exists and is COMPLETED before adding
- `app.schemas.knowledge`
- `app.models.knowledge`

**Forbidden dependencies:**
- `app.gateway` — Knowledge module does not call AI directly
- `app.modules.files` — Knowledge module does not process files
- `app.modules.chat` — Chat sessions are separate from collection queries

---

### 7.7 RAG Module

**Location:** `app/modules/rag/`

**Purpose:** The Retrieval-Augmented Generation engine. Converts raw text into searchable vector embeddings, retrieves relevant chunks for a query, and assembles augmented prompts for the AI Gateway.

**Folder structure:**
```
app/modules/rag/
├── __init__.py
├── service.py
├── chunker.py
├── embedder.py
└── retriever.py
```

**`service.py` responsibilities:**
- `embed_document(file_id: UUID, text: str) → None` — Chunk text, generate embeddings, save to FileChunk table
- `retrieve_chunks(query: str, collection_id: UUID | None, limit: int) → list[RetrievedChunk]` — Vector similarity search, returns ranked chunks with source attribution
- `augment_prompt(query: str, chunks: list[RetrievedChunk]) → str` — Assemble RAG prompt: system context + retrieved chunks + user query
- `query(user_id: UUID, collection_id: UUID | None, query: str) → RAGQueryResponse` — Full pipeline: retrieve → augment → call gateway → return response with citations

**`chunker.py` responsibilities:**
Stateless text chunking. Implements multiple strategies selectable by configuration:
- `fixed_chunker(text, chunk_size, overlap)` — Split by character count with overlap
- `paragraph_chunker(text)` — Split on paragraph boundaries
- `sentence_chunker(text, max_sentences_per_chunk)` — Split on sentence boundaries

The active strategy is selected in `service.py` based on document type. Phase 3 uses `paragraph_chunker` as the default.

**`embedder.py` responsibilities:**
Generates vector embeddings for text. Calls the AI Gateway's embedding endpoint (not a direct provider call). Returns a `list[float]` — the raw embedding vector. Handles batching for large documents (embedding is called per-chunk, not per-document).

**`retriever.py` responsibilities:**
Executes the pgvector similarity search. Given a query embedding, queries the `file_chunks` table using cosine distance (`<=>` operator). Applies collection filtering via JOIN when a `collection_id` is provided. Returns chunks sorted by similarity score, with their source file and chunk index for citation.

**Allowed dependencies:**
- `app.gateway` — Embedding calls go through AI Gateway
- `app.repositories.file` — Saves and retrieves FileChunk records
- `app.schemas.knowledge` — RetrievedChunk, RAGQueryResponse types
- `app.models.file` — FileChunk model

**Forbidden dependencies:**
- Direct AI provider calls
- `app.modules.chat` — RAG does not know about chat sessions
- `app.modules.knowledge` — RAG does not know about collections (receives `collection_id` as a parameter only)
- `app.storage` — RAG does not access R2 directly

---

### 7.8 Memory Module

**Location:** `app/modules/memory/`

**Purpose:** Long-term user memory — facts, preferences, and context that persist across conversations. Unlike chat history (which is per-session), memories are global to the user and survive session deletion.

**Folder structure:**
```
app/modules/memory/
├── __init__.py
├── service.py
├── extractor.py
└── exceptions.py
```

**`service.py` responsibilities:**
- `save_memory(user_id: UUID, content: str, memory_type: MemoryType, source: str | None) → Memory` — Manually save a memory record
- `recall_memory(user_id: UUID, query: str, limit: int) → list[Memory]` — Semantic search over user memories (uses vector similarity on memory content embeddings)
- `list_memories(user_id: UUID, memory_type: MemoryType | None) → PaginatedResponse[Memory]` — All memories for a user, optionally filtered by type
- `delete_memory(user_id: UUID, memory_id: UUID) → None` — Remove a specific memory
- `clear_all_memories(user_id: UUID) → None` — Delete all memories for a user (must be confirmed)
- `extract_and_save(user_id: UUID, conversation: list[ChatMessage]) → list[Memory]` — Delegating to `extractor.py`, then saving extracted memories

**Memory types (MemoryType enum):**
- `PREFERENCE` — User stated preferences ("I prefer formal responses")
- `FACT` — Facts the user shared ("My project is named PrimeX AI")
- `CONTEXT` — Ongoing context ("User is a software architect")
- `INSTRUCTION` — Persistent instructions ("Always include type annotations in Python")

**`extractor.py` responsibilities:**
Uses the AI Gateway to analyze a conversation and extract memory-worthy information. Returns structured facts in a schema that maps to the Memory model. Called asynchronously after a chat session ends (via background job `jobs/tasks/extract_memory.py`). The extraction prompt is carefully crafted to avoid hallucination and to extract only explicitly stated user information.

**`exceptions.py` contents:**
- `MemoryNotFound(NotFoundError)`
- `MemoryLimitExceeded(ConflictError)` — User has exceeded their memory quota (configurable per plan)

**Allowed dependencies:**
- `app.gateway` — Memory extraction and recall similarity calls go through gateway
- `app.repositories.memory`
- `app.schemas.memory`
- `app.models.memory`

**Forbidden dependencies:**
- `app.modules.chat` — Memory module does not read chat sessions directly
- `app.modules.rag` — Memory uses its own embedding-based recall, not RAG pipeline
- `app.storage` — Memories are stored in PostgreSQL, not R2

---

### 7.9 Search Module

**Location:** `app/modules/search/`

**Purpose:** Cross-corpus semantic search across the user's entire knowledge base — chat history, uploaded documents, knowledge collections, and memories — in a single query.

**Folder structure:**
```
app/modules/search/
├── __init__.py
├── service.py
└── ranker.py
```

**`service.py` responsibilities:**
- `search(user_id: UUID, query: SearchQuery) → SearchResponse` — Execute search across selected corpora, return ranked results with source labels
- `search_with_citations(user_id: UUID, query: SearchQuery) → SearchResponse` — Same as search but includes specific passage excerpts as citations

Search operates on a `SearchQuery` that specifies:
- `text: str` — The search query text
- `corpora: list[Corpus]` — Which sources to search: `DOCUMENTS`, `CHAT`, `MEMORY`, `KNOWLEDGE`
- `limit: int` — Maximum number of results

**`ranker.py` responsibilities:**
After results are retrieved from multiple corpora (each returns its own similarity scores), the ranker merges, deduplicates, and re-scores across all result types. A document result and a memory result have different inherent relevance signals. The ranker normalizes these and returns a unified sorted list.

**Allowed dependencies:**
- `app.gateway` — Query embedding generation
- `app.repositories.file` — Document chunk search
- `app.repositories.chat` — Chat history search
- `app.repositories.memory` — Memory search
- `app.repositories.knowledge` — Collection document search
- `app.schemas.search`
- `app.models.*` — Read access to all models for search

**Forbidden dependencies:**
- Direct calls to any module's service — search operates at the repository level directly for performance
- `app.modules.rag` — Search does not use the full RAG pipeline; it uses vector retrieval only

---

### 7.10 Analytics Module

**Location:** `app/modules/analytics/`

**Purpose:** Usage tracking, token consumption reporting, and cost estimation. This module is a read-heavy consumer of data written by the AI Gateway's tracker.

**Folder structure:**
```
app/modules/analytics/
├── __init__.py
└── service.py
```

**`service.py` responsibilities:**
- `get_usage_stats(user_id: UUID, period: DateRange) → UsageStats` — Total messages, total tokens, active days
- `get_token_consumption(user_id: UUID, period: DateRange) → TokenConsumption` — Token breakdown by provider and model
- `get_cost_summary(user_id: UUID, period: DateRange) → CostSummary` — Estimated cost based on provider pricing tables
- `get_provider_metrics(period: DateRange) → ProviderMetrics` — Admin-level: provider success rates, average latency, fallback frequency

Analytics is **read-only**. The analytics module never writes to the database. All writes are performed by `app/gateway/tracker.py` at the moment of each AI call.

**Allowed dependencies:**
- `app.repositories.analytics`
- `app.schemas.analytics`
- `app.models.analytics`

**Forbidden dependencies:**
- `app.gateway` — Analytics does not call AI
- Any other module's service or repository — Analytics only reads from its own tables
- `app.storage` — Analytics data lives in PostgreSQL

---

### 7.11 Admin Module

**Location:** `app/modules/admin/`

**Purpose:** System administration operations restricted to users with the `ADMIN` role. Provides visibility into user accounts, system health, and operational metrics.

**Folder structure:**
```
app/modules/admin/
├── __init__.py
├── service.py
└── exceptions.py
```

**`service.py` responsibilities:**
- `list_users(page: int, per_page: int, search: str | None) → PaginatedResponse[AdminUserDetail]` — All users with account status and usage summary
- `get_user(user_id: UUID) → AdminUserDetail` — Full user detail including preferences and usage history
- `suspend_user(admin_id: UUID, target_user_id: UUID, reason: str) → None` — Disable account, revoke all sessions
- `reactivate_user(admin_id: UUID, target_user_id: UUID) → None` — Re-enable suspended account
- `get_system_health() → SystemHealth` — Aggregate health: database connectivity, R2 connectivity, AI provider statuses
- `get_system_stats() → SystemStats` — Platform-wide metrics: total users, total files, total tokens consumed

**`exceptions.py` contents:**
- `AdminActionForbidden(AuthorizationError)` — User lacks admin role
- `CannotSuspendSelf(ValidationError)` — Admin attempted to suspend their own account
- `CannotSuspendAdmin(ValidationError)` — Cannot suspend another admin without super-admin role (Phase 6)

**Allowed dependencies:**
- `app.repositories.user` — User listing and management
- `app.repositories.analytics` — System-wide stats
- `app.gateway.health` — AI provider health status
- `app.storage` — Storage connectivity check
- `app.schemas.admin`
- `app.models.user`
- `app.models.analytics`

**Forbidden dependencies:**
- `app.modules.auth` — Admin module does not issue tokens
- `app.gateway` — Admin does not call AI providers
- `app.modules.chat`, `app.modules.files` — Admin reads data via repositories only, not through domain services

---

## 8. Services Layer

**Location:** `app/storage/` and shared utilities used across modules

**Important clarification on terminology:** In PrimeX AI's architecture, "services" refers to infrastructure services (external system clients), not the business logic services within domain modules. Business logic lives in `app/modules/*/service.py`. Infrastructure services live in `app/storage/`.

### 8.1 Storage Service (`app/storage/`)

**Purpose:** All interaction with Cloudflare R2 (S3-compatible object storage).

**`client.py` responsibilities:**
- Initialize and configure the boto3 S3 client pointed at Cloudflare R2's endpoint
- Handle client-level retries and connection pooling
- Expose a singleton `r2_client` instance

**`operations.py` responsibilities:**
- `upload(key: str, data: bytes, content_type: str) → str` — Upload bytes to R2, return the object URL
- `download(key: str) → bytes` — Download object from R2
- `delete(key: str) → None` — Delete object from R2
- `generate_presigned_url(key: str, expires_in: int) → str` — Create a time-limited download URL
- `key_exists(key: str) → bool` — Check if an object exists

**R2 key naming convention:**
```
files/{user_id}/{file_id}/original.{ext}   — Raw uploaded file
files/{user_id}/{file_id}/content.txt      — Extracted text
files/{user_id}/{file_id}/metadata.json   — Parsed metadata
archives/{date}/{batch_id}.tar.gz          — Batch archive exports
```

**Consumers:** `app/modules/files/`, `app/jobs/tasks/`, `app/modules/admin/` (health check only). No other module may import from `app/storage/`.

---

## 9. Repository Layer

**Location:** `app/repositories/`

The repository layer is the **only** layer that writes SQL. Services never write SQL. API routes never write SQL.

### 9.1 `base.py` — GenericRepository

`GenericRepository[T]` provides reusable CRUD operations using SQLAlchemy. All domain repositories extend this class.

Provided methods:
- `create(data: dict) → T`
- `get_by_id(id: UUID) → T | None`
- `update(id: UUID, data: dict) → T | None`
- `soft_delete(id: UUID) → None` — Sets `deleted_at`, does not remove row
- `hard_delete(id: UUID) → None` — Physically removes row (use sparingly)
- `list(filters: dict, page: int, per_page: int) → tuple[list[T], int]`

All repositories receive the database session via FastAPI's `Depends(get_db)`. Repositories do not own sessions; they receive them as parameters.

### 9.2 Repository Naming and Method Conventions

Each repository is named `{Domain}Repository`. Methods are named to express intent in business language, not database language:

```python
# Correct — business language
user_repository.find_by_email(email)
chat_repository.get_session_with_messages(session_id)
memory_repository.search_by_similarity(embedding, limit)

# Wrong — database language
user_repository.select_where_email(email)
chat_repository.join_session_messages(session_id)
memory_repository.vector_query(embedding, limit)
```

### 9.3 Vector Search Repositories

The `memory` and `file` repositories implement vector similarity search using pgvector's `<=>` (cosine distance) operator. These are the only repositories that generate embedding-aware SQL:

```sql
-- Memory recall query pattern
SELECT * FROM memories
WHERE user_id = :user_id
ORDER BY embedding <=> :query_embedding
LIMIT :limit;
```

The embedding vector is passed in as a parameter. Repositories do not generate embeddings — that happens in `app/modules/rag/embedder.py` or `app/modules/memory/service.py` before the repository is called.

---

## 10. Models Layer

**Location:** `app/models/`

SQLAlchemy ORM models are centralized in `app/models/`. This is a pragmatic decision driven by two technical constraints:

**Constraint 1: Alembic autogenerate.** Alembic's `--autogenerate` feature works by importing all models and comparing them to the database schema. For this to work, `migrations/env.py` must import every model. Centralizing models in `app/models/__init__.py` makes this a single import statement.

**Constraint 2: SQLAlchemy relationships.** `relationship()` definitions can cause circular import errors if models are spread across modules. Centralizing models eliminates this problem entirely.

### 10.1 `base.py` — Shared Mixins

```
DeclarativeBase           — SQLAlchemy's base class
TimestampMixin            — created_at, updated_at (auto-set by SQLAlchemy events)
UUIDMixin                 — id field (UUID, server-default: gen_random_uuid())
SoftDeleteMixin           — deleted_at field (NULL = active, timestamp = deleted)
```

All application models inherit from `DeclarativeBase` and `TimestampMixin`. Most inherit `UUIDMixin`. Models that support soft delete inherit `SoftDeleteMixin`.

### 10.2 Model Inventory

| Model | Table | Key Fields | Notes |
|---|---|---|---|
| `User` | `users` | id, email, password_hash, role, is_active, preferences (JSONB), deleted_at | Soft-deleteable |
| `UserSession` | `user_sessions` | id, user_id, refresh_token_hash, expires_at, revoked_at | Tracks active refresh tokens |
| `ChatSession` | `chat_sessions` | id, user_id, title, model_used, deleted_at | Soft-deleteable |
| `ChatMessage` | `chat_messages` | id, session_id, role, content, token_count, provider_used, metadata (JSONB) | Append-only |
| `UploadedFile` | `uploaded_files` | id, user_id, filename, content_type, size_bytes, status, r2_key, error_detail, deleted_at | status is enum |
| `FileChunk` | `file_chunks` | id, file_id, chunk_index, content, embedding (vector(1536)) | pgvector enabled |
| `Collection` | `collections` | id, user_id, name, description, deleted_at | |
| `CollectionDocument` | `collection_documents` | id, collection_id, file_id, added_at | Junction table |
| `Memory` | `memories` | id, user_id, content, memory_type, embedding (vector(1536)), source, metadata (JSONB) | pgvector enabled |
| `SearchHistory` | `search_history` | id, user_id, query, corpora, result_count | Analytics |
| `UsageRecord` | `usage_records` | id, user_id, provider, model, input_tokens, output_tokens, cost_usd, endpoint, created_at | Written by gateway tracker |

### 10.3 Schema Design Principles

**UUID primary keys everywhere.** No integer primary keys. UUIDs are generated by PostgreSQL server-side (`gen_random_uuid()`), not by the application.

**JSONB for extensibility.** Fields that may need to evolve without a migration (`preferences`, `metadata`) use PostgreSQL JSONB. Application code reads these as Python dicts.

**Soft deletes for user data.** User-owned records (sessions, files, collections, memories) are soft-deleted. PostgreSQL rows are never physically removed during normal operation. A background cleanup job can archive truly old soft-deleted records.

**Embeddings as `vector(1536)`.** All embeddings are dimensioned for 1536 dimensions (compatible with OpenAI `text-embedding-3-small` and Gemini's equivalent). If a different dimension model is adopted, a migration adjusts the column.

---

## 11. Schemas Layer

**Location:** `app/schemas/`

Pydantic schemas are centralized in `app/schemas/`. Unlike models (which map to database tables), schemas map to API contracts — what the frontend sends and what it receives.

### 11.1 Schema Naming Conventions

| Schema type | Naming | Example |
|---|---|---|
| Request body | `{Action}{Resource}Request` | `CreateMessageRequest`, `UpdateProfileRequest` |
| Response body | `{Resource}Response` or `{Resource}Detail` | `MessageResponse`, `FileDetail` |
| Paginated | `{Resource}ListResponse` | `FileListResponse` |
| Internal | `{Resource}Data` | `TokenPayload` |

### 11.2 `common.py` — Shared Schemas

All schemas that appear in multiple domains:
- `PaginatedResponse[T]` — Generic wrapper: `items: list[T]`, `total: int`, `page: int`, `per_page: int`, `has_next: bool`
- `ApiError` — Standard error response: `code: str`, `message: str`, `details: dict | None`
- `UUIDStr` — Annotated type for UUID strings with validation
- `OrderBy` — Enum for sort direction: `ASC`, `DESC`

### 11.3 Schema Layer Responsibilities

Schemas do:
- Validate incoming request data (Pydantic's built-in validation)
- Define the exact shape of API responses (`response_model=`)
- Serialize ORM models to JSON (via `model_validate()` on ORM objects)
- Apply field-level validation (length limits, regex patterns, value ranges)

Schemas do not:
- Query the database
- Call services
- Contain business logic
- Know about SQLAlchemy sessions

### 11.4 ORM Mode

All response schemas are configured with `model_config = ConfigDict(from_attributes=True)`. This allows `Schema.model_validate(orm_model_instance)` to work without manually constructing dictionaries. The API layer uses this pattern exclusively when returning responses.

---

## 12. AI Gateway Layer

**Location:** `app/gateway/`

The AI Gateway is the most architecturally significant component of PrimeX AI. No domain module bypasses it.

### 12.1 `gateway.py` — Public Interface

`AIGateway` is a class with a clean, stable interface. Domain modules import only `AIGateway` — never specific provider classes.

**Public methods:**
- `async complete(messages: list[Message], config: GatewayConfig) → CompletionResponse` — Standard (non-streaming) completion
- `async stream(messages: list[Message], config: GatewayConfig) → AsyncGenerator[StreamChunk, None]` — Streaming completion
- `async embed(texts: list[str], config: GatewayConfig) → list[list[float]]` — Generate embeddings

`GatewayConfig` specifies:
- `preferred_provider: Provider | None` — Override default routing
- `model: str | None` — Specific model override
- `max_tokens: int` — Token limit for this call
- `temperature: float` — Creativity setting
- `system_prompt: str | None` — System context

### 12.2 `router.py` — Provider Selection

The router implements the provider selection algorithm:

```
1. Check health.py — which providers are currently healthy?
2. If preferred_provider is set and healthy → use it
3. Otherwise → use priority order: Gemini → Groq → OpenRouter
4. On provider error (timeout, rate limit, API error) → try next provider
5. If all providers fail → raise AllProvidersUnavailable
6. Log provider selection decision and reason
```

The circuit breaker pattern is implemented here: if a provider fails more than N times in M minutes, it is marked as DEGRADED and skipped until a health probe succeeds.

### 12.3 `providers/base.py` — Abstract Provider

`AIProvider` is an abstract base class (ABC) that all provider implementations must satisfy:

- `async complete(messages, config) → CompletionResponse`
- `async stream(messages, config) → AsyncGenerator[StreamChunk, None]`
- `async embed(texts, config) → list[list[float]]`
- `async health_check() → bool`
- `provider_name: str` — Class attribute

### 12.4 Provider Implementations

**`gemini.py`:** Uses Google's Generative AI SDK. Primary provider. Handles Gemini's message format differences (it uses `parts` instead of `content`). Maps PrimeX AI's internal message format to Gemini's format before each call and maps the response back.

**`groq.py`:** Uses Groq's OpenAI-compatible API. Fallback provider. Groq's API is OpenAI-compatible, making integration simpler. Primary use: speed (Groq is optimized for low-latency inference).

**`openrouter.py`:** Implemented in Phase 5. OpenRouter is an aggregator that provides access to many models under one API. Used when both Gemini and Groq are unavailable, or when a specific model (e.g., Claude, GPT-4) is explicitly requested.

### 12.5 `tracker.py` — Usage Recording

After every successful AI call, the tracker records:
- User ID
- Provider used
- Model used
- Input token count
- Output token count
- Estimated cost (based on provider's published pricing)
- Endpoint (which module made the call)
- Timestamp

This data is written to the `usage_records` table and consumed by the analytics module.

### 12.6 `health.py` — Provider Health Monitoring

Maintains an in-memory state machine for each provider: `HEALTHY`, `DEGRADED`, `UNAVAILABLE`. 

- Health probes run on a background schedule (every 60 seconds)
- A provider moves to `DEGRADED` after 3 consecutive failures
- A provider returns to `HEALTHY` after a successful health probe
- The `/health` endpoint and admin module expose this state

---

## 13. File Processing Layer

**Location:** `app/processing/`

The processing layer contains stateless, side-effect-free parsers. They take bytes in, return structured data out. They never write to the database, never call the AI gateway, and never touch R2.

### 13.1 `pipeline.py` — Orchestrator

`FileProcessingPipeline` orchestrates the full processing workflow. It is called by `app/modules/files/pipeline.py`. It knows the order of steps but delegates each step to the appropriate component.

### 13.2 Parser Implementations

Each parser implements `FileParser.parse(file_bytes: bytes) → ParsedDocument`.

`ParsedDocument` contains:
- `title: str | None` — Extracted document title
- `raw_text: str` — Full extracted text
- `pages: list[str] | None` — Per-page text (PDFs and slide decks)
- `word_count: int`
- `metadata: dict` — Author, creation date, language, etc.

**Parser selection** is based on the file's `content_type` (validated on upload):

| MIME type | Parser |
|---|---|
| `application/pdf` | `PdfParser` (pdfplumber) |
| `application/vnd.openxmlformats-officedocument.wordprocessingml.document` | `DocxParser` (python-docx) |
| `text/plain` | `TxtParser` |
| `text/csv` | `CsvParser` (Phase 7) |
| `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` | `XlsxParser` (Phase 7) |
| `application/vnd.openxmlformats-officedocument.presentationml.presentation` | `PptxParser` (Phase 7) |

### 13.3 Phase 1 Implementation Scope

In Phase 1, only `TxtParser` and a minimal `PdfParser` are fully implemented. `DocxParser` is stubbed. Parsers for CSV, XLSX, and PPTX have stub implementations that raise `NotImplementedError` — they do not silently return empty data.

---

## 14. Background Jobs

**Location:** `app/jobs/`

Background jobs handle workloads that should not block the HTTP request lifecycle. In Phase 1, PrimeX AI uses FastAPI's built-in `BackgroundTasks` — not Celery or Redis queues. This is intentional: avoid external queue infrastructure until usage patterns justify the operational complexity.

### 14.1 `worker.py` — Task Coordinator

`TaskWorker` wraps FastAPI's `BackgroundTasks` and provides:
- Task registration with error handling
- Task logging (task name, user context, start time)
- Failure capture to Sentry

### 14.2 Task Definitions

**`tasks/process_file.py` — `process_file_task(file_id: UUID)`**
Called immediately after a file is uploaded and confirmed in the database. Triggers the full file processing pipeline: download from R2, parse, chunk, embed, save chunks, update status. This task can take 5–60 seconds depending on file size.

**`tasks/generate_summary.py` — `generate_summary_task(file_id: UUID)`**
Called after file processing completes. Sends the extracted text to the AI Gateway for a structured summary. Saves the summary to the `UploadedFile.metadata` JSONB field. Phase 2 feature.

**`tasks/extract_memory.py` — `extract_memory_task(session_id: UUID, user_id: UUID)`**
Called when a chat session is explicitly ended or when a configurable session length threshold is reached. Sends the conversation to the memory extractor, saves any extracted memories. Phase 4 feature.

### 14.3 Future Queue Migration

When background jobs require:
- Retries with exponential backoff
- Dead-letter queues for failed tasks
- Priority queues for time-sensitive vs. batch work
- Distributed execution across multiple workers

...the task functions in `app/jobs/tasks/` will be migrated to Celery or ARQ (async task queue for Python). The function signatures remain identical; only the execution mechanism changes. This is why task functions receive simple scalar arguments (UUIDs, strings) rather than complex objects.

---

## 15. Middleware

**Location:** `app/middleware/`

Middleware applies globally to every request. No middleware contains business logic.

### 15.1 `cors.py` — CORS Configuration

Reads `ALLOWED_ORIGINS` from config and configures FastAPI's `CORSMiddleware`. In production, allows only `https://primex.ai`. In development, allows `http://localhost:3000`.

### 15.2 `auth.py` — Authentication Middleware

Extracts the `Authorization: Bearer <token>` header on every request. Validates the JWT. Attaches the decoded token payload to `request.state.token`. Does not raise exceptions on missing tokens — that is the job of the `get_current_user` dependency, which is applied only to routes that require authentication. Public routes (health check, login, register) function normally without an Authorization header.

### 15.3 `logging.py` — Structured Request Logging

Logs every request and response using `structlog`. Captures:
- Request: method, path, query params, user ID (if authenticated), request ID (UUID)
- Response: status code, duration (ms)
- Exception details (if any)

All log entries are JSON-formatted for ingestion by log aggregators. No sensitive data (passwords, tokens, file content) appears in logs.

### 15.4 `rate_limit.py` — Rate Limiting

In Phase 1, implements a simple in-memory rate limiter per user ID. Limits:
- Chat messages: 60 per minute per user
- File uploads: 20 per hour per user
- Search queries: 100 per minute per user

Phase 5+ replaces the in-memory limiter with a Redis-backed limiter to support multi-instance deployments.

---

## 16. Observability

**Location:** `app/observability/`

### 16.1 `logger.py` — Structured Logging

Configures `structlog` as the logging backend. All log entries are JSON objects with mandatory fields:
- `timestamp` — ISO 8601
- `level` — DEBUG / INFO / WARNING / ERROR / CRITICAL
- `logger` — Module path (e.g., `app.modules.chat.service`)
- `message` — Human-readable message
- `request_id` — Propagated from middleware
- `user_id` — If available from request context
- `environment` — From `ENVIRONMENT` config

All Python `logging.getLogger()` calls are intercepted by structlog's standard library integration. No `print()` statements. No `logging.basicConfig()`.

### 16.2 `sentry.py` — Error Reporting

Initializes Sentry's Python SDK with:
- `dsn` from `SENTRY_DSN` config
- `environment` from `ENVIRONMENT` config
- `traces_sample_rate: 1.0` in staging, `0.1` in production
- Custom `before_send` hook that scrubs PII (email addresses, file content) from error payloads
- Integration with FastAPI for automatic request context capture

Custom fingerprinting groups related errors together: all `AllProvidersUnavailable` exceptions are grouped regardless of which route triggered them.

### 16.3 `metrics.py`

Defines custom application metrics for future Prometheus/Grafana integration. Phase 1: metrics are tracked but not exported. Phase 6+: metrics are exposed via `/metrics` endpoint.

Tracked metrics:
- `ai_requests_total` — Counter by provider and status
- `ai_response_latency` — Histogram by provider
- `file_processing_duration` — Histogram by file type
- `active_users_total` — Gauge

---

## 17. Security Architecture

### 17.1 Authentication Flow

```
1. User POSTs /auth/login with email + password
2. auth.service verifies password hash (bcrypt, cost factor 12)
3. auth.service creates JWT access token (15-minute expiry)
4. auth.service creates refresh token (hashed), saves to user_sessions
5. Response: {access_token, refresh_token, expires_in}

6. Client stores access_token in memory (NOT localStorage)
7. Client sends Authorization: Bearer {access_token} header with every request
8. auth middleware decodes token, attaches to request.state

9. Access token expires → client POSTs /auth/refresh with refresh_token
10. auth.service validates refresh_token hash against user_sessions
11. auth.service issues new access_token
```

**Why JWT in memory, not cookies:** PrimeX AI's API is consumed by a Next.js frontend deployed on a different domain. Cookie-based auth requires careful SameSite and Secure configuration that adds complexity. Access tokens in memory (JS heap) expire quickly (15 minutes) and cannot be accessed by scripts if the frontend practices Content Security Policy. Refresh tokens have longer life but are stored in the database and can be revoked.

### 17.2 Authorization Model

PrimeX AI Phase 1 uses a two-role model:
- `USER` — Standard access; can only access their own data
- `ADMIN` — Full access; can access all user data and admin endpoints

Every repository method that accesses user-owned data takes `user_id: UUID` as a parameter and includes it in the WHERE clause. This is the primary access control enforcement: it is not possible for a user to retrieve another user's file even if they guess the UUID.

### 17.3 Input Validation

All incoming data passes through Pydantic validation at the API layer. Pydantic enforces:
- Type correctness
- String length limits (all text fields have `max_length`)
- Allowed values (enums)
- Non-empty required fields

Content validation (checking that file content is not malicious) is handled in `app/modules/files/service.py` before processing begins.

### 17.4 Secret Management

- No secrets in code
- No secrets in `.env.example`
- Production secrets stored in Render's environment groups (backend) and Vercel's environment variables (frontend)
- Development secrets in gitignored `.env` files
- Database passwords, API keys, and JWT secrets are rotated on a quarterly schedule

---

## 18. Dependency Rules

The following rules are absolute. Any violation is a bug that must be fixed before merging.

### 18.1 Layer Dependency Direction

```
Allowed (→ means "may import from"):
  app/api/*         → app/modules/*/service.py
  app/api/*         → app/schemas/*
  app/api/*         → app/modules/auth/dependencies.py
  app/api/*         → app/dependencies.py

  app/modules/*     → app/repositories/*
  app/modules/*     → app/schemas/*
  app/modules/*     → app/models/*
  app/modules/*     → app/core/*

  app/modules/chat  → app/gateway/gateway.py
  app/modules/rag   → app/gateway/gateway.py
  app/modules/memory → app/gateway/gateway.py
  app/modules/search → app/gateway/gateway.py

  app/modules/files → app/storage/*
  app/modules/files → app/processing/*
  app/modules/files → app/modules/rag (embedding only)

  app/repositories/* → app/models/*
  app/repositories/* → app/core/database.py

  app/gateway/*     → app/repositories/analytics.py (tracker writes usage)
  app/gateway/*     → external AI APIs only

  app/jobs/*        → app/modules/*/service.py
  app/jobs/*        → app/gateway/* (never; jobs use module services)
```

### 18.2 Forbidden Dependencies (Complete List)

```
FORBIDDEN:
  app/api/*         → app/repositories/*       (bypass service layer)
  app/api/*         → app/models/*             (bypass schema layer)
  app/api/*         → app/gateway/*            (AI calls are business logic)

  app/modules/*     → app/api/*                (domain depends on HTTP)
  app/modules/*     → external AI APIs          (bypass gateway)

  app/repositories/* → app/modules/*           (circular; repos have no business logic)
  app/repositories/* → app/schemas/*           (repos return ORM models, not schemas)

  app/models/*      → anything else            (models are leaves in the dependency tree)

  app/gateway/*     → app/modules/* (except analytics.repository for usage recording)
  app/gateway/*     → app/api/*

  app/processing/*  → app/modules/*            (parsers are stateless utilities)
  app/processing/*  → app/repositories/*
  app/processing/*  → app/gateway/*
```

### 18.3 Inter-Module Communication Rules

Modules do not call each other's services directly unless it is an explicit, documented cross-module dependency. Cross-module dependencies are:

| Caller | Called | Reason |
|---|---|---|
| `files` | `rag.embedder` | File processing generates embeddings |
| `knowledge` | `rag.service` | Collection queries use RAG |
| `chat` | `memory.service` | Chat can inject memory context (Phase 4) |
| `search` | `repositories.*` | Search reads across all domains via repositories |
| `admin` | `gateway.health` | Admin displays provider health |

Any new cross-module dependency requires an ADR entry documenting the reason.

---

## 19. Scaling Strategy

### 19.1 Phase 1–3: Single Instance

The backend runs as a single FastAPI process on Render. Vertical scaling (more RAM, more CPU) is sufficient for Phase 1–3. The AI Gateway handles load by routing to different providers. The database connection pool (SQLAlchemy + Neon's PgBouncer) manages connection pressure.

### 19.2 Phase 4–5: Horizontal Scaling

Render supports horizontal scaling with multiple instances. FastAPI is stateless by design — no in-process state except the in-memory rate limiter and provider health state. When scaling to multiple instances:
- Rate limiter migrates from in-memory to Redis (update `app/middleware/rate_limit.py`)
- Provider health state migrates from in-memory to Redis (update `app/gateway/health.py`)
- Background tasks migrate from `BackgroundTasks` to Celery with Redis broker (update `app/jobs/worker.py`)

These migrations require changes to exactly one file each. The module interfaces remain unchanged.

### 19.3 Phase 6–8: Service Extraction

If any module becomes the bottleneck (likely: file processing, RAG, or memory extraction), it can be extracted to a standalone service. The module's `service.py` becomes the service's entry point. The remaining monolith communicates with it via HTTP or message queue. Other modules continue calling the same service interface; only the transport layer changes.

---

## 20. Anti-Patterns

The following patterns are explicitly forbidden. Each represents a decision that creates long-term technical debt.

### 20.1 ❌ SQL in Service or API Layers

**Forbidden:** `db.execute(text("SELECT * FROM users WHERE email = :email"), ...)` appearing in `service.py` or `api/*.py`.

**Why:** The repository layer exists precisely to isolate SQL. When SQL appears in service code, testing becomes dependent on a real database connection, business logic becomes entangled with query structure, and query optimization requires changes to business logic files.

### 20.2 ❌ Direct AI Provider Calls Outside Gateway

**Forbidden:** `import google.generativeai as genai` appearing anywhere outside `app/gateway/providers/gemini.py`.

**Why:** This is the highest-risk anti-pattern in the codebase. AI providers update APIs, change pricing, and have outages. Calls scattered across the codebase make provider migration a full-codebase refactor instead of a single-file change.

### 20.3 ❌ Business Logic in Route Handlers

**Forbidden:** Route handlers that contain `if/else` logic, database queries, or multi-step workflows.

**Why:** Route handlers that contain business logic cannot be unit-tested without HTTP. The service layer exists so that business logic is testable with simple function calls.

### 20.4 ❌ Returning ORM Objects from Services

**Forbidden:** Service methods that return `User` (SQLAlchemy model) instead of `UserProfile` (Pydantic schema).

**Why:** SQLAlchemy models with lazy-loading relationships can trigger database queries when serialized. Services must convert to Pydantic schemas before returning. This also prevents the accidental exposure of database internals (like `password_hash`) in API responses.

### 20.5 ❌ Shared Mutable State Between Requests

**Forbidden:** Module-level variables that are mutated during request handling (e.g., `request_counter = 0; request_counter += 1`).

**Why:** FastAPI handles requests concurrently. Module-level mutable state causes race conditions. State that must be shared across requests belongs in Redis or PostgreSQL.

### 20.6 ❌ Catching and Swallowing Exceptions

**Forbidden:**
```python
try:
    result = await gateway.complete(...)
except Exception:
    return None
```

**Why:** Swallowed exceptions create silent failures that are impossible to debug. All exceptions must either be re-raised, converted to a domain exception, or explicitly logged and reported to Sentry before returning a default value. Never `except Exception: pass`.

### 20.7 ❌ Module Self-Registration

**Forbidden:** Domain modules that register themselves with a global registry by importing at module level.

**Why:** This creates implicit dependencies and makes import order significant. All module wiring is explicit in `main.py` and `app/api/v1/router.py`.

### 20.8 ❌ Alembic `autogenerate` as the Only Migration Check

**Forbidden:** Relying solely on Alembic's autogenerate diff to confirm a migration is complete.

**Why:** Autogenerate misses certain schema changes (custom column types, check constraints, stored procedures). Every migration is reviewed by a human before merging. The ADR for `ADR-003-vector-database.md` documents specific pgvector migration patterns that autogenerate handles incorrectly.

---

## 21. Conclusion

The PrimeX AI backend is organized around four principles that directly address the project's 3–5 year time horizon:

**1. Layers enforce correctness.** The strict API → Service → Repository → Model dependency chain means that changes to one layer do not cascade unexpectedly into other layers. Adding a new feature means adding a route, a service method, and a repository method — in that order, in those locations. There is no debate about where code belongs.

**2. The AI Gateway is a single point of control.** PrimeX AI's competitive advantage is intelligent AI routing, fallback, and usage tracking. Centralizing all AI calls in `app/gateway/` means this logic is always applied, always consistent, and always maintainable. A provider API change touches one file. A new provider requires one new file.

**3. Domain modules are independently comprehensible.** An engineer assigned to work on the memory system can open `app/modules/memory/` and understand the complete feature from its service, through its repository, to its model. They will not need to read through a monolithic `services.py` file of 5,000 lines.

**4. The structure supports extraction.** Every design decision — stateless parsers, thin repositories, message-based background tasks, isolated gateway — is made with service extraction in mind. Phase 8 will look very different from Phase 1. The architecture is designed to evolve without requiring a rewrite.

A new engineer following this document can start implementing PrimeX AI from Phase 1 today. The structure is stable through Phase 8.

---

*Document ends. This document should be read alongside `05_Database_Design.md` (schema definitions) and `10_AI_Gateway_Design.md` (gateway provider configuration).*
