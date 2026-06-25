# 06 — Repository Structure

**Document:** PrimeX AI Implementation Documentation
**Version:** 1.0.0
**Status:** Approved — Implementation Ready
**Scope:** Complete repository layout, monorepo strategy, environment configuration, and governance rules

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Repository Design Philosophy](#2-repository-design-philosophy)
3. [Monorepo Strategy](#3-monorepo-strategy)
4. [Complete Repository Tree](#4-complete-repository-tree)
5. [Applications Layer](#5-applications-layer)
6. [Shared Packages](#6-shared-packages)
7. [Infrastructure Layer](#7-infrastructure-layer)
8. [Documentation Layer](#8-documentation-layer)
9. [Scripts Layer](#9-scripts-layer)
10. [GitHub Layer](#10-github-layer)
11. [Environment Strategy](#11-environment-strategy)
12. [Repository Standards](#12-repository-standards)
13. [Dependency Boundaries](#13-dependency-boundaries)
14. [Scaling Strategy](#14-scaling-strategy)
15. [Anti-Patterns](#15-anti-patterns)
16. [Conclusion](#16-conclusion)

---

## 1. Executive Summary

PrimeX AI is organized as a **polyglot monorepo** — a single Git repository that hosts both the Next.js frontend (`apps/web`) and the FastAPI backend (`apps/api`), along with shared TypeScript packages, infrastructure configuration, and documentation.

This structure is not a convention choice. It is an architectural decision that directly serves PrimeX AI's long-term goals: a platform expected to evolve across 8 phases over 3–5 years, maintained by a small team, with zero tolerance for coordination drift between frontend and backend contracts.

The repository is **self-contained by design**: anyone who clones it has everything needed to understand, run, and extend PrimeX AI without hunting across multiple repositories.

**Core structural decisions made in this document:**

| Decision | Choice | Reason |
|---|---|---|
| Repo strategy | Monorepo | Single source of truth, atomic cross-app commits |
| Monorepo tooling | Makefile + pnpm workspaces (no Turborepo) | Python backend cannot participate in JS pipeline graphs |
| Frontend location | `apps/web/` | Isolated from backend, own dependency graph |
| Backend location | `apps/api/` | Isolated from frontend, own Python toolchain |
| Shared types | `packages/types/` | Prevents schema drift between frontend and backend |
| Infrastructure | `infrastructure/` | All deployment and container config in one place |
| Documentation | `docs/` | Version-controlled alongside code |
| CI/CD | `.github/` | GitHub Actions, per-app workflow isolation |

---

## 2. Repository Design Philosophy

### 2.1 One Repository, One Source of Truth

PrimeX AI does not use multiple repositories. All application code, infrastructure, documentation, and scripts live in one repository. This is a non-negotiable constraint for Phase 1 through Phase 8.

**Why this matters for PrimeX AI specifically:**

- The frontend and backend share API contracts. When the backend changes an endpoint, the frontend must change in the same commit. Separate repositories make this a coordination problem. A monorepo makes it a compile-time verification problem — solvable with shared types.
- Documentation is code. A `docs/` change that documents a new API route should be in the same pull request as the route implementation.
- Infrastructure affects both apps. A change to Docker configuration or a new environment variable touches the frontend and backend simultaneously.

### 2.2 Isolation at the App Boundary, Not the Repository Boundary

The two applications (`web` and `api`) are completely isolated within the repository. They do not share runtime code, dependency managers, or build systems. The frontend uses `pnpm`. The backend uses `poetry`. They are connected only at the **interface boundary**: shared TypeScript type definitions that describe API request and response shapes.

This means:
- Adding a Python dependency to the backend does not require any npm action.
- Adding an npm dependency to the frontend does not require any poetry action.
- The two apps can be deployed, tested, and built entirely independently.

### 2.3 Horizontal Scalability of the Repository

The repository structure is designed to absorb new applications and packages without restructuring. If a future phase (Phase 8: Agents) requires a dedicated agent runner service, it is added as `apps/agent-runner/` without touching any existing directory. If a shared utility package is needed, it is added as `packages/utility-name/`. The root structure never changes.

---

## 3. Monorepo Strategy

### 3.1 Why Not Turborepo

Turborepo is the canonical monorepo build tool for Next.js projects. PrimeX AI does **not** use Turborepo as its primary orchestration layer. The decision is architectural, not preferential.

Turborepo operates on the concept of a **pipeline**: tasks defined in `turbo.json` are executed across packages in dependency order, with caching of build outputs. This pipeline model works excellently for a pure TypeScript monorepo where every app and package participates in the same build graph.

PrimeX AI's backend is Python/FastAPI. Python has no `package.json`, no `build` script, no output directory that Turborepo can cache. Forcing a TypeScript build tool to orchestrate a Python application creates artificial complexity: wrapper scripts, fake `package.json` files in the backend directory, or a Turborepo config that ignores half the repository.

**The chosen approach:** Turborepo's pipeline is used exclusively for the JavaScript/TypeScript packages (`packages/*` and `apps/web`). The backend orchestration uses a root-level `Makefile`. Cross-app tasks (start everything, run all tests, lint everything) are Makefile targets that call the appropriate toolchain for each app.

### 3.2 pnpm Workspaces

The frontend app and shared TypeScript packages are managed by `pnpm` workspaces. This provides:
- Shared `node_modules` hoisting (reduced disk usage, faster installs)
- Local package resolution: `@primex/types` resolves to `packages/types/` without publishing to npm
- Consistent lockfile across all JavaScript packages

The workspace configuration is minimal:

```
# pnpm-workspace.yaml (root)
packages:
  - "apps/web"
  - "packages/*"
```

The FastAPI backend (`apps/api`) is **explicitly excluded** from pnpm workspaces. It has no `package.json`. pnpm does not manage it.

### 3.3 Poetry for Python

The backend uses `poetry` for dependency management. All Python dependency and virtual environment concerns are contained within `apps/api/`. The root-level Makefile provides convenience targets (`make api-install`, `make api-test`) but these simply delegate to `cd apps/api && poetry run ...`.

### 3.4 Root-Level Coordination via Makefile

The `Makefile` at the repository root is the developer's single entry point for all tasks:

| Target | Action |
|---|---|
| `make install` | Install all dependencies (pnpm + poetry) |
| `make dev` | Start both apps in development mode (via docker-compose or parallel processes) |
| `make test` | Run all tests across both apps |
| `make lint` | Run linters across both apps |
| `make migrate` | Run Alembic database migrations |
| `make build` | Build frontend for production |
| `make docker-up` | Start local Docker stack |
| `make docker-down` | Stop local Docker stack |
| `make format` | Auto-format all code |
| `make check` | Pre-commit validation (lint + test + type check) |

This approach requires no learning of a new tool. Any engineer familiar with `make` can immediately operate the repository.

---

## 4. Complete Repository Tree

The following tree represents the complete repository at implementation-ready depth. Every directory and key file is named. Directories marked `[generated]` are produced by build tools and must not be committed.

```
primex-ai/
│
├── .github/
│   ├── workflows/
│   │   ├── ci-web.yml                  # Frontend CI: lint, type-check, test, build
│   │   ├── ci-api.yml                  # Backend CI: lint, type-check, test
│   │   ├── deploy-web.yml              # Deploy frontend to Vercel (main branch)
│   │   ├── deploy-api.yml              # Deploy backend to Render (main branch)
│   │   └── codeql.yml                  # Security scanning
│   ├── PULL_REQUEST_TEMPLATE.md
│   ├── ISSUE_TEMPLATE/
│   │   ├── bug_report.md
│   │   └── feature_request.md
│   └── CODEOWNERS                      # Branch protection ownership rules
│
├── apps/
│   │
│   ├── web/                            # Next.js 15 frontend application
│   │   ├── .env.example                # All required env vars documented
│   │   ├── .env.local                  # [gitignored] Local development secrets
│   │   ├── .eslintrc.json              # ESLint config (extends @primex/eslint-config)
│   │   ├── .prettierrc.json
│   │   ├── next.config.ts
│   │   ├── package.json
│   │   ├── postcss.config.mjs
│   │   ├── tailwind.config.ts
│   │   ├── tsconfig.json               # Extends packages/tsconfig/base.json
│   │   ├── components.json             # shadcn/ui configuration
│   │   ├── public/
│   │   │   ├── favicon.ico
│   │   │   ├── logo.svg
│   │   │   └── og-image.png
│   │   └── src/
│   │       ├── app/                    # Next.js App Router pages
│   │       │   ├── layout.tsx
│   │       │   ├── page.tsx
│   │       │   ├── (auth)/
│   │       │   │   ├── login/
│   │       │   │   │   └── page.tsx
│   │       │   │   └── register/
│   │       │   │       └── page.tsx
│   │       │   ├── (dashboard)/
│   │       │   │   ├── layout.tsx
│   │       │   │   ├── chat/
│   │       │   │   │   ├── page.tsx
│   │       │   │   │   └── [sessionId]/
│   │       │   │   │       └── page.tsx
│   │       │   │   ├── files/
│   │       │   │   │   └── page.tsx
│   │       │   │   ├── knowledge/
│   │       │   │   │   ├── page.tsx
│   │       │   │   │   └── [collectionId]/
│   │       │   │   │       └── page.tsx
│   │       │   │   ├── memory/
│   │       │   │   │   └── page.tsx
│   │       │   │   ├── search/
│   │       │   │   │   └── page.tsx
│   │       │   │   └── settings/
│   │       │   │       └── page.tsx
│   │       │   └── (admin)/
│   │       │       ├── layout.tsx
│   │       │       └── admin/
│   │       │           └── page.tsx
│   │       ├── components/
│   │       │   ├── ui/                 # shadcn/ui generated components [gitignored from shadcn]
│   │       │   ├── layout/
│   │       │   │   ├── Sidebar.tsx
│   │       │   │   ├── Header.tsx
│   │       │   │   └── AppShell.tsx
│   │       │   ├── chat/
│   │       │   │   ├── ChatWindow.tsx
│   │       │   │   ├── MessageList.tsx
│   │       │   │   ├── MessageBubble.tsx
│   │       │   │   └── ChatInput.tsx
│   │       │   ├── files/
│   │       │   │   ├── FileUploader.tsx
│   │       │   │   └── FileCard.tsx
│   │       │   ├── knowledge/
│   │       │   │   ├── CollectionCard.tsx
│   │       │   │   └── DocumentCard.tsx
│   │       │   ├── memory/
│   │       │   │   └── MemoryCard.tsx
│   │       │   ├── search/
│   │       │   │   ├── SearchBar.tsx
│   │       │   │   └── SearchResults.tsx
│   │       │   └── shared/
│   │       │       ├── LoadingSpinner.tsx
│   │       │       ├── ErrorBoundary.tsx
│   │       │       └── EmptyState.tsx
│   │       ├── hooks/
│   │       │   ├── useChat.ts
│   │       │   ├── useFileUpload.ts
│   │       │   └── useSearch.ts
│   │       ├── lib/
│   │       │   ├── api/
│   │       │   │   ├── client.ts       # Axios/fetch base client
│   │       │   │   ├── auth.ts
│   │       │   │   ├── chat.ts
│   │       │   │   ├── files.ts
│   │       │   │   ├── knowledge.ts
│   │       │   │   └── search.ts
│   │       │   └── utils/
│   │       │       ├── cn.ts           # Tailwind class merging
│   │       │       ├── format.ts       # Date, number formatting
│   │       │       └── validators.ts
│   │       ├── store/
│   │       │   ├── auth.store.ts       # Zustand auth store
│   │       │   ├── chat.store.ts
│   │       │   └── ui.store.ts
│   │       ├── types/
│   │       │   └── index.ts            # Re-exports from @primex/types
│   │       └── middleware.ts           # Next.js middleware (auth guards)
│   │
│   └── api/                            # FastAPI backend application
│       │                               # (Expanded fully in 07_Backend_Folder_Structure.md)
│       ├── .env.example
│       ├── .env                        # [gitignored]
│       ├── pyproject.toml              # Poetry config + project metadata
│       ├── poetry.lock
│       ├── alembic.ini
│       ├── Dockerfile
│       ├── .dockerignore
│       ├── app/                        # Application source (see doc 07)
│       │   └── ...
│       ├── migrations/
│       │   └── ...
│       └── tests/
│           └── ...
│
├── packages/
│   │
│   ├── types/                          # Shared TypeScript type definitions
│   │   ├── package.json                # name: "@primex/types"
│   │   ├── tsconfig.json
│   │   ├── src/
│   │   │   ├── index.ts                # Barrel export
│   │   │   ├── api/
│   │   │   │   ├── auth.types.ts       # AuthRequest, AuthResponse, TokenPayload
│   │   │   │   ├── chat.types.ts       # Message, Session, StreamChunk
│   │   │   │   ├── files.types.ts      # UploadedFile, FileStatus, ParseResult
│   │   │   │   ├── knowledge.types.ts  # Collection, KnowledgeDocument
│   │   │   │   ├── memory.types.ts     # Memory, MemoryType
│   │   │   │   ├── search.types.ts     # SearchResult, SearchQuery
│   │   │   │   ├── analytics.types.ts  # UsageStats, ProviderMetrics
│   │   │   │   └── common.types.ts     # PaginatedResponse, ApiError, UUID
│   │   │   └── enums/
│   │   │       ├── file-status.enum.ts
│   │   │       ├── memory-type.enum.ts
│   │   │       └── provider.enum.ts
│   │   └── dist/                       # [generated] TypeScript compilation output
│   │
│   ├── eslint-config/                  # Shared ESLint rules
│   │   ├── package.json                # name: "@primex/eslint-config"
│   │   ├── index.js                    # Base config
│   │   ├── next.js                     # Next.js specific rules
│   │   └── react.js                    # React rules
│   │
│   └── tsconfig/                       # Shared TypeScript configurations
│       ├── package.json                # name: "@primex/tsconfig"
│       ├── base.json                   # Strict base config
│       ├── nextjs.json                 # Next.js specific settings
│       └── library.json                # Library package settings
│
├── infrastructure/
│   ├── docker/
│   │   ├── api/
│   │   │   └── Dockerfile.prod         # Production-optimized backend image
│   │   └── postgres/
│   │       └── init.sql                # pgvector extension initialization
│   ├── render/
│   │   └── render.yaml                 # Render deployment configuration
│   └── vercel/
│       └── vercel.json                 # Vercel project configuration
│
├── docs/
│   ├── 01_Project_Overview.md
│   ├── 02_Product_Vision.md
│   ├── 03_Technology_Stack.md
│   ├── 04_Architecture_Overview.md
│   ├── 05_Database_Design.md
│   ├── 06_Repository_Structure.md      # This document
│   ├── 07_Backend_Folder_Structure.md
│   ├── 08_Frontend_Folder_Structure.md
│   ├── 09_API_Contracts.md
│   ├── 10_AI_Gateway_Design.md
│   ├── 11_File_Processing_Pipeline.md
│   ├── 12_RAG_Architecture.md
│   ├── 13_Memory_System.md
│   ├── 14_Security_Model.md
│   ├── 15_Deployment_Guide.md
│   ├── 16_Development_Workflow.md
│   ├── adr/                            # Architecture Decision Records
│   │   ├── ADR-001-monorepo.md
│   │   ├── ADR-002-ai-gateway.md
│   │   ├── ADR-003-vector-database.md
│   │   └── ADR-004-storage-strategy.md
│   └── runbooks/
│       ├── incident-response.md
│       ├── database-migrations.md
│       └── provider-failover.md
│
├── scripts/
│   ├── setup.sh                        # First-time developer environment setup
│   ├── seed.py                         # Database seeding for development
│   ├── check-env.sh                    # Validates all required env vars are set
│   ├── generate-types.sh               # Syncs backend Pydantic schemas → TS types
│   └── backup-db.sh                    # Manual database backup trigger
│
├── .env.example                        # Root-level env vars (shared, non-secret)
├── .gitignore
├── .gitattributes
├── .editorconfig
├── .pre-commit-config.yaml             # Pre-commit hooks (lint, format, type check)
├── docker-compose.yml                  # Local development stack
├── docker-compose.override.yml.example # Local overrides template
├── Makefile                            # Root-level developer commands
├── pnpm-workspace.yaml
├── package.json                        # Root package.json (dev tooling only)
├── turbo.json                          # Turborepo pipeline (JS packages only)
├── README.md
└── CONTRIBUTING.md
```

---

## 5. Applications Layer

### 5.1 `apps/web/` — Next.js Frontend

**Purpose:** The primary user interface for PrimeX AI. Handles all user interactions, real-time streaming, file uploads, and data visualization.

**Key characteristics:**
- **Owned by:** Frontend/Full-Stack engineer
- **Tech:** Next.js 15 (App Router), TypeScript, Tailwind CSS, shadcn/ui, Zustand, TanStack Query
- **Deployed to:** Vercel
- **Communicates with:** `apps/api/` only, via REST API + SSE for streaming

**Dependency source:** `packages/types` for all API shape types. The frontend never defines its own API types; it always imports from `@primex/types`. This guarantees that a backend schema change is immediately visible as a TypeScript error in the frontend.

**Route group structure explanation:**
- `(auth)/` — Routes that require the user to be logged out (login, register). Middleware prevents authenticated users from accessing these.
- `(dashboard)/` — Routes that require authentication. Middleware redirects unauthenticated users to login.
- `(admin)/` — Routes restricted to admin users. Separate layout with admin-specific navigation.

**Environment variables** (all prefixed `NEXT_PUBLIC_` for client-side access or plain for server-side):
```
NEXT_PUBLIC_API_URL=          # Backend API base URL
NEXT_PUBLIC_APP_URL=          # Frontend base URL
NEXT_PUBLIC_SENTRY_DSN=       # Sentry frontend DSN
```

### 5.2 `apps/api/` — FastAPI Backend

**Purpose:** The backend application, AI gateway, data processing engine, and business logic layer for PrimeX AI.

**Key characteristics:**
- **Owned by:** Backend engineer
- **Tech:** Python, FastAPI, SQLAlchemy, Alembic, Pydantic, Poetry
- **Deployed to:** Render
- **Communicates with:** Neon PostgreSQL, Cloudflare R2, AI providers (Gemini, Groq, OpenRouter), Sentry

The backend folder structure is fully documented in `07_Backend_Folder_Structure.md`. This document describes only its position in the repository and its interface contract with the rest of the monorepo.

The backend does **not** import from `packages/`. It defines its data shapes using Pydantic and these are the authoritative source. A code generation script (`scripts/generate-types.sh`) exports the Pydantic schemas to TypeScript types in `packages/types/`, ensuring the frontend always stays synchronized with the backend contract.

**Environment variables:**
```
DATABASE_URL=                 # Neon PostgreSQL connection string
DIRECT_DATABASE_URL=          # Direct connection (for migrations, bypasses PgBouncer)
R2_ACCOUNT_ID=
R2_ACCESS_KEY_ID=
R2_SECRET_ACCESS_KEY=
R2_BUCKET_NAME=
R2_PUBLIC_URL=
GEMINI_API_KEY=
GROQ_API_KEY=
OPENROUTER_API_KEY=
JWT_SECRET_KEY=
JWT_ALGORITHM=HS256
JWT_EXPIRATION_MINUTES=60
SENTRY_DSN=
ENVIRONMENT=development
LOG_LEVEL=INFO
ALLOWED_ORIGINS=
```

---

## 6. Shared Packages

Shared packages live in `packages/`. They are TypeScript-only. Python code is **never** placed in `packages/`. Each package is a private npm package (not published to a registry) resolved via pnpm workspaces.

### 6.1 `packages/types/` — `@primex/types`

**This is the most important shared package.** It defines the complete TypeScript representation of every API request and response shape in PrimeX AI.

**Ownership rule:** Types are generated from the backend's Pydantic schemas using `scripts/generate-types.sh`. Engineers do not hand-write types in this package — they define Pydantic schemas in the backend, then run the generation script. Manual edits to `packages/types/src/api/` are forbidden.

**Why:** Prevents the single most common form of frontend/backend drift — mismatched API shape expectations that cause runtime errors instead of compile-time errors.

**Contents by subdirectory:**

- `src/api/` — Request/response types for every API domain, mirroring the backend schema structure exactly
- `src/enums/` — Shared enumeration values (e.g., `FileStatus.PROCESSING`, `MemoryType.PREFERENCE`) that both apps need to agree on

**Consumers:** `apps/web` only. The backend does not consume this package.

### 6.2 `packages/eslint-config/` — `@primex/eslint-config`

Shared ESLint rule set. All JavaScript/TypeScript files in the repository use the same linting rules, preventing configuration drift between the web app and any future apps.

Contains three configs:
- `index.js` — Base rules for all TypeScript code
- `next.js` — Rules specific to Next.js (no `<img>` without `next/image`, etc.)
- `react.js` — Rules specific to React (hooks rules, component rules)

### 6.3 `packages/tsconfig/` — `@primex/tsconfig`

Shared TypeScript configurations. Enforces strict mode (`strict: true`, `noUncheckedIndexedAccess: true`, `exactOptionalPropertyTypes: true`) across all TypeScript in the repository.

Contains three configs:
- `base.json` — Strictest settings, inherited by all others
- `nextjs.json` — Extends base, adds Next.js specific compiler options
- `library.json` — Extends base, configures for package library compilation (`declaration: true`, `declarationMap: true`)

---

## 7. Infrastructure Layer

`infrastructure/` holds all deployment and container configuration. Source code is never placed here. Infrastructure config is treated as code: it is reviewed in pull requests, versioned, and documented.

### 7.1 `infrastructure/docker/`

Contains Dockerfiles and initialization SQL that are not part of any specific app's directory but are consumed by the Docker Compose local development stack.

**`infrastructure/docker/api/Dockerfile.prod`** — A multi-stage production Docker image for the FastAPI backend. This is separate from `apps/api/Dockerfile` (used for local development, optimized for rebuild speed) because production builds have different requirements: non-root user, no dev dependencies, stripped binary size.

**`infrastructure/docker/postgres/init.sql`** — Executed once when the local PostgreSQL container starts. Installs the `pgvector` extension. Content:
```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
```

### 7.2 `infrastructure/render/`

**`render.yaml`** — Render's Infrastructure-as-Code configuration. Defines the backend web service, health check endpoint, environment variable groups, and auto-deploy branch. This file is committed and reviewed; Render reads it on each deploy.

### 7.3 `infrastructure/vercel/`

**`vercel.json`** — Vercel project configuration. Defines build settings, framework preset, function regions, and security headers. This supplements (not replaces) the Vercel dashboard configuration.

### 7.4 `docker-compose.yml` (Root)

The local development stack. Not in `infrastructure/` because it is a daily-use developer tool, not a deployment artifact. It deserves root-level visibility.

Defines:
- `postgres` — PostgreSQL 16 with pgvector extension, port 5432
- `api` — FastAPI backend, port 8000, hot-reload enabled, mounts `apps/api/`
- `redis` — Redis for background job queue (Phase 1+), port 6379

**`docker-compose.override.yml.example`** — A template for developer-specific overrides. Engineers copy this to `docker-compose.override.yml` (gitignored) to customize ports, mount points, or environment variables for their local setup without affecting the committed configuration.

---

## 8. Documentation Layer

All project documentation lives in `docs/` and is version-controlled alongside the code. Documentation is not optional or aspirational — it is a first-class deliverable.

### 8.1 Documentation Standards

- Every document is a Markdown file.
- Every document has a version number, status, and date in its header.
- Documents are numbered. Numbering is not reorganized; new documents receive the next available number.
- Documents reference each other by filename: "See `07_Backend_Folder_Structure.md`."
- Documents are updated in the same pull request as the code they describe.
- Outdated documentation is updated, not deleted.

### 8.2 Architecture Decision Records (ADRs)

`docs/adr/` contains Architecture Decision Records. An ADR is created every time a significant architectural decision is made. ADRs document:
- **Context:** The situation that required a decision.
- **Decision:** The choice made.
- **Consequences:** What this decision enables and constrains.

ADRs are never deleted or reversed — they are marked as superseded and a new ADR is created with the updated decision. This creates an auditable history of how PrimeX AI evolved.

### 8.3 Runbooks

`docs/runbooks/` contains operational procedures for common situations: how to handle a database migration, what to do when an AI provider goes down, how to restore from a backup. Runbooks are written for humans under stress; they must be step-by-step, specific, and tested.

---

## 9. Scripts Layer

`scripts/` contains executable scripts that automate development tasks. These are not build scripts (those live in `package.json` or the `Makefile`); they are operational utilities.

### Script Inventory

| Script | Language | Purpose |
|---|---|---|
| `setup.sh` | Bash | First-time setup: installs pnpm, poetry, creates `.env` files from examples, checks system dependencies |
| `seed.py` | Python | Creates development database fixtures: test user, sample conversations, example files |
| `check-env.sh` | Bash | Validates that all required environment variables are set before starting any service. Run by CI before deployment. |
| `generate-types.sh` | Bash | Runs the Pydantic-to-TypeScript code generation and writes output to `packages/types/src/api/` |
| `backup-db.sh` | Bash | Triggers a manual Neon snapshot via the Neon API. Used before major migrations. |

### Script Standards

- Scripts must be executable (`chmod +x`)
- Scripts must have a `#!/usr/bin/env bash` or `#!/usr/bin/env python3` shebang
- Scripts must print a usage message if run without required arguments
- Scripts must exit with a non-zero status on failure
- Scripts must not contain secrets; they read from environment variables

---

## 10. GitHub Layer

`.github/` contains all GitHub-specific configuration: workflows, templates, and ownership rules.

### 10.1 CI Workflows

**`ci-web.yml`** — Triggered on pull requests touching `apps/web/**` or `packages/**`:
1. Install pnpm dependencies
2. Type-check (`tsc --noEmit`)
3. Lint (`eslint`)
4. Run tests (`vitest`)
5. Build (`next build`)

**`ci-api.yml`** — Triggered on pull requests touching `apps/api/**`:
1. Set up Python 3.12
2. Install poetry dependencies
3. Type-check (`mypy`)
4. Lint (`ruff check`)
5. Format check (`ruff format --check`)
6. Run tests (`pytest --cov`)

**`deploy-web.yml`** — Triggered on merge to `main` touching `apps/web/**` or `packages/**`. Triggers a Vercel deployment. Vercel handles the actual build; this workflow only initiates the deploy hook and waits for success.

**`deploy-api.yml`** — Triggered on merge to `main` touching `apps/api/**`. Triggers a Render deploy hook. Waits for the health check endpoint (`/health`) to return 200 before marking the workflow as successful.

**`codeql.yml`** — Scheduled weekly + triggered on pull requests. GitHub's CodeQL security analysis for Python and JavaScript.

### 10.2 Pull Request Template

Every pull request follows a structured template:
- Description of changes
- Type of change (feature / bug fix / refactoring / documentation)
- How to test
- Checklist (tests written, documentation updated, env vars documented, migration included if schema changed)

### 10.3 CODEOWNERS

Branch protection is enforced via `.github/CODEOWNERS`. This file ensures:
- Changes to `apps/api/app/gateway/` require review from the Lead Architect
- Changes to `docs/adr/` require review from the Technical Lead
- Changes to `packages/types/` require review (this is the shared contract)
- Changes to `.github/workflows/` require review

### 10.4 Branch Strategy

| Branch | Purpose | Protected |
|---|---|---|
| `main` | Production-ready code. Deploys to Vercel + Render on merge. | Yes — requires PR + CI pass |
| `develop` | Integration branch. Feature branches merge here first. | Yes — requires PR |
| `feature/*` | Individual feature development | No |
| `fix/*` | Bug fixes | No |
| `chore/*` | Maintenance, dependency updates | No |
| `docs/*` | Documentation-only changes | No |

---

## 11. Environment Strategy

### 11.1 Three Environments

| Environment | Frontend | Backend | Database | Purpose |
|---|---|---|---|---|
| `local` | `localhost:3000` | `localhost:8000` | Docker PostgreSQL | Development |
| `staging` | Vercel preview URL | Render staging service | Neon branch | Pre-production validation |
| `production` | `primex.ai` | `api.primex.ai` | Neon main branch | Live |

### 11.2 Environment Variable Hierarchy

```
Repository level:
  .env.example (committed, documents all variables, no values)

App level:
  apps/web/.env.example    (committed, Next.js vars)
  apps/api/.env.example    (committed, Python vars)

Developer level (gitignored):
  apps/web/.env.local      (local values, never committed)
  apps/api/.env            (local values, never committed)

CI/CD level:
  GitHub Secrets           (injected into workflows as env vars)
  Render Environment Groups (production secrets in Render dashboard)
  Vercel Environment Variables (production secrets in Vercel dashboard)
```

### 11.3 Rules for Environment Variables

1. **No secrets in the repository.** API keys, database passwords, JWT secrets — all are stored in the hosting platform's secret management (GitHub Secrets for CI, Render for backend, Vercel for frontend).
2. **Every required variable has a documented example.** `.env.example` files describe every variable, its format, and where to obtain it. New variables must be added to `.env.example` in the same commit that adds the code that uses them.
3. **`check-env.sh` is run in CI before deployment.** If a required variable is missing, the deployment fails before any code executes.
4. **Backend and frontend environments are strictly separated.** The frontend never has access to backend secrets (database URLs, AI provider keys). The backend never uses `NEXT_PUBLIC_` prefixed variables.
5. **`ENVIRONMENT` controls behavior.** The backend reads `ENVIRONMENT=development|staging|production` to adjust logging verbosity, Sentry sampling, and CORS rules. The frontend reads `NODE_ENV` (set by Next.js automatically).

---

## 12. Repository Standards

### 12.1 Naming Conventions

| Entity | Convention | Example |
|---|---|---|
| Directories | `kebab-case` | `ai-gateway/`, `file-processing/` |
| Python files | `snake_case` | `user_service.py`, `ai_router.py` |
| TypeScript files | `PascalCase` for components, `camelCase` for utilities | `ChatWindow.tsx`, `useChat.ts` |
| TypeScript types | `PascalCase` | `AuthResponse`, `ChatMessage` |
| Python classes | `PascalCase` | `UserService`, `AIGateway` |
| Python functions | `snake_case` | `get_current_user()`, `create_session()` |
| Environment variables | `SCREAMING_SNAKE_CASE` | `DATABASE_URL`, `GEMINI_API_KEY` |
| Git branches | `type/short-description` | `feature/chat-streaming`, `fix/file-upload-timeout` |
| Commit messages | `type(scope): description` | `feat(chat): add streaming response support` |

### 12.2 Commit Message Format

PrimeX AI uses [Conventional Commits](https://www.conventionalcommits.org/). This is enforced by a pre-commit hook.

```
type(scope): description

Types: feat, fix, docs, style, refactor, perf, test, build, ci, chore
Scopes: web, api, gateway, auth, chat, files, knowledge, memory, search, analytics, admin, infra, docs
```

### 12.3 Pull Request Standards

- No PR is merged without passing CI.
- No PR introduces a `TODO` that does not have an associated GitHub issue.
- Every PR that changes an API endpoint updates `docs/09_API_Contracts.md`.
- Every PR that changes a database schema includes an Alembic migration.
- Every PR that adds a new environment variable updates `.env.example`.

### 12.4 Testing Standards

| Layer | Framework | Minimum Coverage |
|---|---|---|
| Backend unit | pytest | 80% |
| Backend integration | pytest + TestClient | All API endpoints |
| Frontend unit | Vitest | 70% |
| Frontend E2E | Playwright (Phase 2+) | Critical user flows |

---

## 13. Dependency Boundaries

The following rules govern which parts of the repository may depend on which other parts.

### 13.1 Allowed Dependencies

```
apps/web      → packages/types        ✅ Web imports shared types
apps/web      → packages/eslint-config ✅ Web uses shared lint config
apps/web      → packages/tsconfig     ✅ Web uses shared TS config
packages/*    → packages/*            ✅ Packages may depend on each other
                                         (no circular deps allowed)
```

### 13.2 Forbidden Dependencies

```
apps/api      → packages/*            ❌ Backend is Python; no JS imports
apps/api      → apps/web              ❌ Backend never imports from frontend
apps/web      → apps/api              ❌ Frontend never imports backend source
packages/*    → apps/*                ❌ Packages never import from apps
infrastructure → apps/*               ❌ Infrastructure config is self-contained
scripts/*     → packages/*            ❌ Scripts are standalone utilities
```

### 13.3 Communication Boundary

The **only** legitimate runtime dependency between frontend and backend is the HTTP API. The frontend calls the backend's REST endpoints. The shape of those calls is defined in `packages/types/`. There is no shared database access, no shared process, no shared memory.

---

## 14. Scaling Strategy

The repository structure is designed to absorb PrimeX AI's 8-phase roadmap without structural reorganization.

### Phase 1–3 (Current Design)

The repository as described above. One frontend, one backend, shared types, minimal infrastructure.

### Phase 4–6 (Parallel Services)

If a dedicated memory service, a search indexer, or a background processing worker needs to become an independent deployable unit, it is extracted to `apps/memory-service/`, `apps/search-indexer/`, etc. It follows the same conventions as `apps/api/`:
- Own `pyproject.toml` (if Python) or `package.json` (if Node)
- Own `Dockerfile`
- Own CI workflow in `.github/workflows/`
- Own set of environment variables documented in its `.env.example`

### Phase 7–8 (Voice, Agents)

Voice processing and agent infrastructure are resource-intensive and may require different scaling profiles than the main API. They are added as separate apps, not bolted onto `apps/api/`. The AI Gateway in `apps/api/` remains the central coordination point; these new apps communicate through it.

### Shared Type Growth

As phases expand, `packages/types/` grows. The internal directory structure of `packages/types/src/api/` maps exactly to the backend module structure. New backend modules generate new type files; no existing files are modified if the change is additive.

---

## 15. Anti-Patterns

The following patterns are explicitly forbidden in this repository. Any PR implementing these patterns will be rejected.

### 15.1 ❌ Cross-App Source Imports

**Forbidden:** The frontend importing Python source files. The backend importing TypeScript source files. These are different runtimes with different language semantics. They communicate over HTTP only.

### 15.2 ❌ Secrets in Code or `.env.example`

**Forbidden:** Any actual API key, database password, or secret appearing in any committed file. `.env.example` contains placeholder values (`your-api-key-here`), never real values.

### 15.3 ❌ Environment-Specific Code in Shared Packages

**Forbidden:** `packages/types/` importing from `apps/web/` or `apps/api/`. Packages are environment-agnostic. They contain pure type definitions.

### 15.4 ❌ Infrastructure Configuration Inside App Directories

**Forbidden:** Putting Docker Compose or Render/Vercel configuration files inside `apps/web/` or `apps/api/`. Infrastructure configuration lives in `infrastructure/` or at the repository root (`docker-compose.yml`). App directories contain only application code.

### 15.5 ❌ Ad-Hoc Scripts at Repository Root

**Forbidden:** One-off scripts (`fix-this.sh`, `temp-migrate.py`) committed to the repository root. Scripts belong in `scripts/` with a documented purpose. Temporary scripts are run locally and never committed.

### 15.6 ❌ Documentation in `README.md` Only

**Forbidden:** Writing architectural decisions in a `README.md` and calling it done. `README.md` is a welcome page, not a documentation system. All architectural decisions belong in `docs/` and specifically in `docs/adr/` if they are architectural decisions.

### 15.7 ❌ Bypassing the Makefile for Cross-App Tasks

**Forbidden:** Running `cd apps/api && poetry run pytest && cd ../../apps/web && pnpm test` in CI scripts. All cross-app task orchestration goes through the root `Makefile`. This ensures CI and local development use identical commands.

---

## 16. Conclusion

The PrimeX AI repository structure is designed around three principles:

**1. Clarity of ownership.** Every file in the repository has a clear home. Engineers never debate where code belongs: application code is in `apps/`, shared contracts are in `packages/`, infrastructure config is in `infrastructure/`, documentation is in `docs/`.

**2. Independence of applications.** The frontend and backend are completely isolated. They share a type contract, not source code, not dependencies, not toolchains. This allows them to evolve at different speeds and be deployed independently without coordination overhead.

**3. Absorptive capacity.** Adding a new application, a new shared package, or a new phase of features requires adding a new directory, not restructuring existing ones. The repository can absorb PrimeX AI's entire 8-phase roadmap without a major reorganization.

This structure is implementation-ready for Phase 1 and designed to remain stable through Phase 8.

---

*Document ends. Continue to `07_Backend_Folder_Structure.md` for the complete FastAPI application architecture.*
