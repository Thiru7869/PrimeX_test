# PrimeX AI — Product Requirements Document

> Document 2 of 3 — Product Requirements
> Status: Draft for approval
> Source of truth: PrimeX AI Architecture Review, 01_Project_Vision.md

---

# Executive Summary

PrimeX AI is a personal AI operating system that unifies conversational AI, document intelligence, knowledge management, and persistent memory into a single, self-owned platform. It exists because no single inspiration product — Claude, ChatGPT, Gemini, Perplexity, or Notion AI — combines all four of these capabilities under one architecture and one data model that its user actually owns.

This Product Requirements Document (PRD) translates the goals and scope defined in `01_Project_Vision.md` into concrete, testable functional and non-functional requirements. It is the primary reference for feature development, implementation planning, QA, and roadmap management across the project's 3–5 year lifecycle.

**Relationship to the Project Vision:** Where the Vision document answers *why PrimeX AI exists* and *what it must become*, this PRD answers *what must be built, in what order, and how its correctness is verified*. Every requirement in this document traces back to a capability, objective, or success metric already established in the Vision.

**Relationship to the Architecture:** This PRD does not redesign, reinterpret, or extend the approved architecture (Next.js 15, FastAPI, Neon PostgreSQL with pgvector, Cloudflare R2, Vercel/Render, the Gemini → Groq → OpenRouter AI Gateway, JWT/refresh-token authentication, Sentry monitoring). It treats that architecture as fixed and specifies requirements that are implementable within it as written. Where a requirement implies a technical decision, that decision is drawn directly from the architecture review — no new technology is introduced.

---

# Product Goals

## Primary Goals

1. Deliver a working, end-to-end personal AI platform — authentication, chat, and multi-provider AI access — as the foundation all later capability is built on (Phase 1).
2. Make the user's own documents (PDF, DOCX, TXT, and later ZIP/CSV/XLSX/PPTX) first-class, queryable citizens of the platform rather than inert uploads.
3. Give the platform durable memory of its user — preferences and facts that persist and inform behavior across sessions, not just within a single conversation.
4. Ensure no single AI vendor can take the platform down or make it unaffordable: Gemini, Groq, and OpenRouter must be interchangeable behind one Gateway.

## Secondary Goals

1. Provide research-grade search with source citations, so answers about external information are verifiable, not just plausible.
2. Give the platform operator (the same person as the primary user) visibility into system health, storage, and provider usage through an admin dashboard.
3. Extend document intelligence to spreadsheet, archive, and presentation formats once the core document pipeline (PDF/DOCX/TXT) is proven.

## Long-Term Goals

1. Evolve from a system the user *queries* to a system that can *act* — voice interaction and agentic automation (Phase 8).
2. Maintain architectural continuity across all eight phases: no phase should require reworking the data model or services delivered by an earlier phase.
3. Sustain free-tier or near-zero marginal operating cost at personal-scale usage indefinitely, not just during initial development.

## Success Criteria

| Goal | Success Criteria |
|---|---|
| Foundation (Phase 1) | User can authenticate, hold a multi-turn chat, and the AI Gateway transparently serves that chat from Gemini with Groq as a working fallback |
| Document Intelligence | A PDF/DOCX/TXT upload can be summarized and queried with answers grounded in the document's actual content |
| Memory | A preference or fact stated in one session is recalled, unprompted, in a later session |
| Vendor Independence | Adding, removing, or reordering a provider in the AI Gateway requires no changes outside the Gateway layer |
| Research Quality | Search answers include citations that resolve to real, retrievable sources |
| Cost Discipline | Personal-scale usage (single user, moderate daily volume) stays within Neon, R2, Vercel, and Render free tiers through at least Phase 4 |

---

# User Personas

## Primary User

**"The Owner-Operator"**

This is the sole intended user of PrimeX AI in its current scope: a technically capable individual who is simultaneously the product's only customer and its maintainer.

| Attribute | Description |
|---|---|
| Role | Owner, primary user, and operator/developer of the system |
| Technical Skill | Comfortable with web applications, willing to read logs/dashboards, capable of triaging provider or infrastructure issues |
| Relationship to System | Long-term, multi-year; expects the system to accumulate knowledge about them over time |

**Goals**
- Have one place to chat with AI, ask questions about their own documents, and get research answers with citations.
- Avoid juggling separate subscriptions/tools for chat, document Q&A, and notes.
- Build a system that gets more useful — not just more cluttered — the longer they use it.
- Keep monthly operating cost near zero at personal usage volumes.

**Needs**
- Reliable chat that doesn't break when one AI provider has an outage or rate-limits them.
- Trustworthy file Q&A — answers grounded in the actual uploaded document, not hallucinated.
- A memory system that recalls stated preferences without having to repeat them every session.
- Enough visibility (via the admin dashboard) to know *why* something is slow, expensive, or failing.

**Pain Points (the problems PrimeX AI is built to remove)**
- AI chat tools forget everything between sessions.
- Document Q&A tools are usually separate products from the chat tool itself.
- Single-vendor AI dependency means a provider outage, price change, or capability regression has nowhere to fail over to.
- Knowledge accumulated in one tool (e.g., a notes app) doesn't talk to the AI in another tool (e.g., a chat app).

**Daily Usage Patterns**
- Opens PrimeX AI as the default entry point for AI-assisted thinking, not a tool reached for occasionally.
- Uploads working documents (reports, references, notes) as they are produced or received, expecting them to become queryable almost immediately.
- Asks follow-up questions across sessions that depend on memory of earlier conversations or previously uploaded files.
- Periodically checks the admin dashboard (from Phase 6 onward) to review provider usage, storage consumption, and system health.

## Future Users

PrimeX AI's current architecture and this PRD are scoped to a **single owner-operator**. The following are documented as plausible future directions, **not commitments**, and require a future architecture review before implementation:

| Potential Future User | Implication if Pursued |
|---|---|
| A small circle of trusted collaborators (e.g., family, close colleagues) | Would require multi-account isolation guarantees beyond current single-user assumptions, without necessarily requiring full multi-tenant SaaS infrastructure |
| Read-only "viewer" access for a third party to specific knowledge bases | Would require a sharing/permissions model not currently in scope |
| Multi-tenant productized version | Explicitly out of scope per `01_Project_Vision.md`; would require a new architecture review before any implementation |

No functional requirement in this document assumes multi-user support unless explicitly stated otherwise.

---

# Functional Requirements

## Authentication

**Requirements**
- Users authenticate via email/password (or equivalent credential mechanism) issued and verified by the FastAPI backend.
- The system issues a short-lived JWT access token and a longer-lived refresh token on successful login.
- Refresh tokens can be exchanged for new access tokens without requiring re-authentication, until the refresh token itself expires or is revoked.
- Passwords are never stored or logged in plaintext.
- Sessions can be explicitly terminated (logout), invalidating the associated refresh token.

**User Flows**
1. **Register:** user submits credentials → backend validates and stores a hashed credential → account created.
2. **Login:** user submits credentials → backend verifies → access token + refresh token issued.
3. **Token Refresh:** expired/expiring access token → client presents refresh token → backend issues new access token.
4. **Logout:** client requests logout → backend invalidates the active refresh token.

**Security Expectations**
- Access tokens are short-lived; refresh tokens are the only long-lived credential and must be stored and transmitted securely.
- All authentication endpoints are served over HTTPS only (enforced by Vercel/Render deployment configuration).
- Credential hashing uses an industry-standard, salted algorithm (implementation detail owned by the backend, not redefined here).
- Sentry monitoring captures authentication errors without logging sensitive credential data.

**Acceptance Criteria**
- A user can register, log in, remain authenticated across a token refresh cycle, and log out, with no manual intervention required at any step.
- An expired access token without a valid refresh token results in a clean re-authentication prompt, not an unhandled error.
- No credential or token value appears in plaintext in logs or Sentry error reports.

---

## Chat System

**Requirements**
- Users can create new conversations and continue existing ones.
- Every message and its response are persisted (Neon PostgreSQL `Messages`/`Chats` tables) and associated with the originating conversation.
- Conversation history is retrievable in order and used as context for subsequent turns within the same conversation.
- Responses stream to the client incrementally rather than waiting for full generation to complete.

**Conversations**
- A conversation has a persistent identity (id, owner, created_at, and a title — generated or user-assigned).
- Conversations can be listed, renamed, and deleted by their owner.

**Message History**
- Each message stores: role (user/assistant), content, timestamp, and the provider/model that generated it (for assistant messages).
- History is paginated for long conversations to avoid loading entire histories into memory at once.

**Conversation Management**
- Users can delete a conversation (and its messages) and rename a conversation.
- Deleting a conversation does not delete any files or knowledge base entries referenced within it — those are managed independently (see File Intelligence and Knowledge Bases).

**Streaming Responses**
- Assistant responses stream token-by-token (or chunk-by-chunk) to the frontend via the AI Gateway, using whichever streaming mechanism the active provider (Gemini, Groq, or OpenRouter) supports.
- If streaming fails mid-response, the partially generated content is preserved and marked as incomplete rather than discarded.

**Acceptance Criteria**
- A new conversation can be created, messaged in, and the assistant's reply appears incrementally (not all at once) under normal network conditions.
- Reopening a previous conversation displays its full message history in correct order.
- Deleting a conversation removes it and its messages from subsequent listings.

---

## AI Gateway

**Requirements**
- All AI requests from any feature (chat, summarization, RAG, search) are routed through the AI Gateway — no feature calls a provider SDK directly.
- The Gateway abstracts provider-specific request/response shapes behind one internal interface.

**Provider Routing**
- Requests are routed to the Primary provider (Gemini) by default.
- On failure, timeout, or rate-limit response from the Primary provider, the request is retried against the Secondary provider (Groq).
- OpenRouter (Tertiary) is available as a further fallback and, from Phase 5 onward, as a target for explicit health-based routing decisions.

**Gemini Integration**
- Gemini is the default provider for standard chat and generation requests in Phase 1.

**Groq Fallback**
- Groq is automatically used when Gemini is unavailable or returns an error class that indicates fallback is appropriate (e.g., rate limit, timeout, 5xx).
- The fallback is transparent to the end user — no manual provider switching is required.

**OpenRouter Support**
- OpenRouter is integrated as the Tertiary provider in Phase 1's gateway design, with full health-aware routing logic delivered in Phase 5.

**Usage Tracking**
- Every AI Gateway request logs: provider used, model, token counts (where available), latency, and outcome (success/failure/fallback-triggered).
- Usage data is persisted to the `Usage Tracking` table in Neon PostgreSQL for later analytics (Phase 1 capture, Phase 6 dashboard surfacing).

**Error Handling**
- Provider errors are caught and classified (retryable vs. non-retryable) before deciding whether to fail over or surface an error to the user.
- All Gateway-level errors are reported to Sentry with provider and request context attached (excluding sensitive payload content where appropriate).

**Acceptance Criteria**
- A simulated Gemini failure results in the same request being served by Groq without the end user seeing an error.
- Usage Tracking records exist for 100% of AI Gateway requests, successful or not.
- No application code outside the AI Gateway module references a provider SDK or provider-specific API shape directly.

---

## File Intelligence

**Requirements**
- Users can upload files in supported formats and have them processed into queryable content.
- Original files are stored in Cloudflare R2; extracted text and derived metadata are stored according to the approved storage split (R2 for originals/extracted text/archived vectors/backups, Neon for active/operational data).

**PDF**
- Text content is extracted from PDF uploads, including multi-page documents.

**DOCX**
- Text content is extracted from DOCX uploads, preserving paragraph-level structure sufficient for downstream summarization and Q&A.

**TXT**
- Plain text files are ingested directly with no extraction step beyond encoding normalization.

**Upload**
- Uploaded files are stored in Cloudflare R2 as the original artifact; a corresponding metadata record is created in Neon PostgreSQL referencing the R2 object.
- Upload failures (size limits, unsupported format, corrupted file) are surfaced to the user with a specific, actionable error rather than a generic failure.

**Extraction**
- Extracted text is stored separately from the original file (per the approved R2 storage layering) so that summarization, embedding, and Q&A operate on normalized text without repeatedly re-parsing the original.

**Summarization**
- Users can request a summary of an uploaded file's content via the AI Gateway.
- Summarization requests are routed through the same Primary/Secondary/Tertiary provider logic as chat.

**Question Answering**
- Users can ask natural-language questions about a specific uploaded file.
- Answers are grounded in the file's extracted content; the system does not present ungrounded generation as if it were sourced from the file.

**Acceptance Criteria**
- A PDF, DOCX, or TXT file can be uploaded, summarized on request, and queried with at least one specific factual question whose answer is verifiably present in the source file.
- Extracted text persists independently of the original file object and is reused for subsequent requests rather than re-extracted each time.
- Unsupported file types are rejected with a clear, specific error message at upload time.

---

## Knowledge Bases

**Requirements**
- Users can organize ingested documents into named Collections that persist independently of any single chat conversation.
- Each document within a Knowledge Base is embedded (768-dimensional embeddings, per the approved Embedding Strategy) and stored with its `embedding_model`, `embedding_dimension`, and `created_at` metadata in pgvector.

**Collections**
- A Collection has an owner, a name, and zero or more associated documents.
- Collections can be created, renamed, and deleted.

**Documents**
- A document added to a Collection inherits the same extraction pipeline used by File Intelligence (Phase 2) — Knowledge Bases build on, rather than duplicate, that pipeline.
- Documents can be added to or removed from a Collection without re-uploading the underlying file.

**Vector Search**
- Documents within a Collection are searchable via vector similarity (pgvector) using the platform's standard 768-dimensional embedding model.
- Active vectors are stored in Neon PostgreSQL; archived/inactive vectors may be moved to Cloudflare R2 per the approved storage layering.

**Management Operations**
- Users can list all Collections, view documents within a Collection, remove individual documents, and delete an entire Collection (cascading to its document associations, not necessarily the underlying original files).

**Acceptance Criteria**
- A document added to a Collection is embedded and retrievable via vector similarity search within that Collection.
- Deleting a Collection removes its document associations without deleting documents that also belong to other Collections (if shared membership is supported) or original files stored independently via File Intelligence.

---

## RAG System

**Requirements**
- Retrieval-Augmented Generation combines vector search over Knowledge Bases with generation via the AI Gateway.

**Chunk Retrieval**
- Documents are chunked at ingestion time into retrievable units sized appropriately for the 768-dimensional embedding model in use.
- A query retrieves the top-N most similar chunks via pgvector similarity search.

**Context Assembly**
- Retrieved chunks are assembled into a bounded context window passed to the AI Gateway alongside the user's query, respecting the active provider's context limits.

**Source Attribution**
- Every RAG-generated answer can be traced back to the specific chunk(s)/document(s) that informed it.
- Source attribution data is returned alongside the generated answer, not just logged internally.

**Acceptance Criteria**
- A RAG query against a populated Knowledge Base returns an answer accompanied by a list of the specific source documents/chunks used.
- Removing a document from a Knowledge Base removes it from future retrieval without requiring a full Collection rebuild.

---

## Memory System

**Requirements**
- The platform retains information about the user that persists across conversations, distinct from any single conversation's message history.

**Short-Term Memory**
- Within an active conversation, recent message history (per Chat System requirements) functions as short-term context.

**Long-Term Memory**
- Discrete facts and preferences extracted from conversations (explicitly stated or confirmed, not silently inferred without basis) are persisted to the `Memories` table in Neon PostgreSQL.
- Long-term memories are retrievable independently of any specific conversation.

**User Preferences**
- A distinct class of long-term memory specifically representing user-stated preferences (e.g., tone, formatting, recurring constraints), persisted and applied to future interactions.

**Memory Retrieval**
- Relevant memories are retrieved and incorporated into AI Gateway requests where applicable, without requiring the user to restate them.

**Memory Editing**
- Users can view, edit, and delete individual stored memories — memory is not a black box the user cannot inspect or correct.

**Acceptance Criteria**
- A fact or preference stated in one session is retrievable and demonstrably applied in a separate, later session without being re-stated.
- A user can view a list of currently stored memories and remove an incorrect or outdated one, with that removal reflected in subsequent interactions.

---

## Search System

**Requirements**
- Users can issue research-style queries that retrieve information beyond their own uploaded documents and Knowledge Bases.

**Web Search**
- Search queries are dispatched to retrieve external, current information, routed through the AI Gateway/provider ecosystem as appropriate.

**Source Citations**
- Search-derived answers include citations linking specific claims to specific retrieved sources.

**Search History**
- Past search queries and their results are retained and retrievable, consistent with the platform's broader persistence model.

**Acceptance Criteria**
- A search query returns an answer with at least one resolvable citation per significant claim.
- Previously issued searches appear in a retrievable search history.

---

## Analytics

**Requirements**
- The platform surfaces quantitative usage data captured by Usage Tracking (Phase 1) and other operational tables.

**Usage Statistics**
- Aggregate and per-period (e.g., daily/weekly) request counts, token usage, and conversation volume are queryable.

**Provider Usage**
- Usage is broken down by provider (Gemini/Groq/OpenRouter), including fallback frequency, to support the Vendor Independence and Cost Optimization principles.

**Storage Usage**
- Storage consumption across Cloudflare R2 (originals, extracted text, archived vectors, backups) and Neon PostgreSQL (active data) is queryable.

**System Metrics**
- Error rates, latency, and provider health signals (captured via Sentry and Gateway-level logging) are surfaced as system-level metrics.

**Acceptance Criteria**
- Usage, provider, and storage statistics can be retrieved for a given time range without manual database querying.
- Provider fallback frequency is visible as a distinct metric, not buried inside aggregate request counts.

---

## Admin Dashboard

**Requirements**
- A dedicated administrative surface (owner-only, consistent with the single-user scope) presents the Analytics data above in a usable form.

**Monitoring**
- Sentry-reported errors and Gateway-level operational issues are visible from the dashboard.

**Storage**
- R2 and Neon storage consumption (per Analytics: Storage Usage) is visible, including approach to free-tier limits.

**Provider Health**
- Current and historical health status of Gemini, Groq, and OpenRouter (latency, error rate, fallback frequency) is visible, supporting the health-aware routing introduced in Phase 5.

**User Data**
- The owner can view their own account-level data footprint (conversations, files, Knowledge Bases, memories) from one place, supporting transparency and the Memory Editing requirement above.

**Acceptance Criteria**
- The dashboard surfaces, on a single screen or a small set of linked screens, current provider health, storage consumption relative to free-tier limits, and recent error activity.
- No dashboard view requires direct database access to answer "is the system healthy right now?"

---

# Non-Functional Requirements

## Performance

| Requirement | Measurable Target |
|---|---|
| Chat response start (time to first streamed token) | Sub-second to low-single-digit seconds under normal provider conditions, excluding provider-side cold starts |
| File extraction (PDF/DOCX/TXT, typical document size) | Completes without blocking the user from continuing other activity in the platform |
| Vector similarity search (per Knowledge Base query) | Returns top-N results without noticeable UI-blocking delay at personal-scale document volumes |

## Reliability

| Requirement | Measurable Target |
|---|---|
| AI Gateway failover | A Primary provider failure results in a Secondary provider response without a user-visible error in the majority of cases |
| Data durability | No conversation, file metadata, or memory record is lost due to a transient provider or infrastructure failure |
| Monitoring coverage | All unhandled exceptions in backend services are captured by Sentry |

## Scalability

| Requirement | Measurable Target |
|---|---|
| Conversation volume | The schema and storage design support growth in conversation/message volume over a multi-year horizon without redesign |
| Knowledge Base size | pgvector-based search remains the retrieval mechanism as Knowledge Base size grows, with archival of inactive vectors to R2 as the documented overflow strategy |
| Provider addition | A new AI provider can be added to the Gateway without modifying any consuming feature |

## Security

| Requirement | Measurable Target |
|---|---|
| Authentication | JWT access tokens are short-lived; refresh tokens are the sole long-lived credential |
| Transport | All client-server and Gateway-provider traffic occurs over HTTPS |
| Secrets handling | Provider API keys and credentials are never present in client-side code or logs |
| Data isolation | A single user's conversations, files, memories, and Knowledge Bases are not accessible to any other account context (even in a future multi-user scenario) |

## Maintainability

| Requirement | Measurable Target |
|---|---|
| Modularity | Authentication, Chat, AI Gateway, File Intelligence, Knowledge Bases, RAG, Memory, Search, Analytics, and Admin are separable modules, each independently testable |
| Schema evolution | Alembic migrations are used for all schema changes; no manual/untracked schema modification |
| Phase additivity | A new phase's implementation does not require modifying the data model or services delivered by a prior phase, beyond additive migrations |

## Cost Optimization

| Requirement | Measurable Target |
|---|---|
| Provider cost awareness | Usage Tracking data is sufficient to identify which provider/feature combination is driving cost at any time |
| Storage tiering | Infrequently accessed data (archived vectors, backups) is stored in Cloudflare R2 rather than retained indefinitely in Neon PostgreSQL active tables |

## Free-Tier Compatibility

| Requirement | Measurable Target |
|---|---|
| Personal-scale operation | Single-user, moderate daily usage operates within Neon, Cloudflare R2, Vercel, and Render free-tier limits through at least Phase 4 |
| Graceful degradation | If a free-tier limit is approached, the Admin Dashboard (Phase 6) surfaces this before a hard service interruption occurs |

---

# User Stories

**Authentication**
- As the owner, I want to log in once and stay authenticated across a normal session so I don't have to re-enter credentials every time my access token expires.
- As the owner, I want to log out and know my session is fully invalidated, so a stale refresh token can't be reused.

**Chat**
- As the owner, I want to start a new conversation and see the assistant's response stream in as it's generated, so the experience feels responsive rather than like waiting for a batch job.
- As the owner, I want to return to a conversation from days ago and see its full history, so I can pick up exactly where I left off.

**Files**
- As the owner, I want to upload a PDF report and ask a specific question about its contents, so I don't have to re-read the entire document myself.
- As the owner, I want a quick summary of a long DOCX file before deciding whether to read it in full.

**Knowledge Bases**
- As the owner, I want to group related documents into a named Collection, so I can query "everything I know about X" rather than one file at a time.
- As the owner, I want a RAG answer to tell me which document it came from, so I can verify it myself if needed.

**Memory**
- As the owner, I want to tell PrimeX AI a preference once (e.g., "always answer concisely") and have it remembered in every future session, not just the current one.
- As the owner, I want to see and delete a memory that's no longer accurate, so outdated information doesn't keep influencing responses.

**Search**
- As the owner, I want to ask a research question and get an answer with sources I can actually click through to, so I can trust and verify the result.

**Administration**
- As the owner/operator, I want to see at a glance which AI provider is currently serving requests and whether any fallback is happening, so I know if something upstream is degraded.
- As the owner/operator, I want to see my storage usage relative to free-tier limits before I get a surprise bill or a hard cutoff.

---

# Acceptance Criteria Matrix

| Feature | Requirement | Acceptance Criteria | Priority |
|---|---|---|---|
| Authentication | JWT + refresh token issuance | Login issues both tokens; refresh exchanges old token for new access token without re-login | Critical |
| Chat | Streaming responses | Assistant output appears incrementally, not as a single blocking response | Critical |
| Chat | Persisted history | Reopening a conversation shows full, correctly ordered message history | Critical |
| AI Gateway | Primary → Secondary failover | Simulated Gemini failure results in a Groq-served response with no user-visible error | Critical |
| AI Gateway | Usage Tracking | Every Gateway request produces a Usage Tracking record | High |
| File Intelligence | PDF/DOCX/TXT extraction | Uploaded file's text is extracted and stored separately from the original | Critical |
| File Intelligence | Grounded Q&A | Answer to a question about a file is verifiably grounded in that file's content | Critical |
| Knowledge Bases | Vector search | Document search within a Collection returns results via pgvector similarity | High |
| RAG | Source attribution | Every RAG answer includes traceable source document/chunk references | Critical |
| Memory | Cross-session recall | A fact stated in one session is recalled, unprompted, in a later session | Critical |
| Memory | User-editable | Stored memories can be viewed and deleted by the user | High |
| Search | Citations | Search answers include resolvable citations for significant claims | High |
| Analytics | Provider breakdown | Usage statistics can be filtered/viewed by provider | Medium |
| Admin Dashboard | Provider health visibility | Current provider health status is visible without querying the database directly | High |
| Non-Functional | Free-tier operation | Personal-scale usage stays within Neon/R2/Vercel/Render free tiers through Phase 4 | Critical |

---

# Product Constraints

**Technology Constraints**
- Frontend must use Next.js 15, TypeScript, Tailwind CSS, shadcn/ui, Zustand, and TanStack Query — no alternative frontend framework.
- Backend must use FastAPI, Python, SQLAlchemy, and Alembic — no alternative backend framework or ORM.
- Database must be Neon PostgreSQL with pgvector — no alternative vector database or relational database.
- Object storage must be Cloudflare R2 — no alternative object storage provider.
- Deployment must target Vercel (frontend) and Render (backend) — no alternative hosting platform without a new architecture review.

**Free-Tier Constraints**
- All Phase 1–4 functionality must be operable within the free tiers of Neon, Cloudflare R2, Vercel, and Render at personal-scale usage.
- Any feature whose normal operation would require paid-tier infrastructure must be flagged and reviewed before implementation, not silently built.

**Storage Constraints**
- Original files, extracted text, archived vectors, and database backups belong in Cloudflare R2.
- Users, Chats, Messages, Memories, Metadata, Active Vectors, and Usage Tracking belong in Neon PostgreSQL.
- No feature may bypass this storage split (e.g., storing original file binaries in Neon, or treating R2 as a queryable database).

**Provider Constraints**
- All AI provider calls must pass through the AI Gateway. No feature may call Gemini, Groq, or OpenRouter SDKs directly.
- Provider order (Primary: Gemini, Secondary: Groq, Tertiary: OpenRouter) is fixed per the architecture review unless a future review changes it.

**Operational Constraints**
- The platform is operated by a single owner who is also its developer/maintainer; no requirement assumes a dedicated ops or support team.
- Monitoring (Sentry) must be active from Phase 1 onward — no phase ships without error visibility.

---

# Assumptions

1. The platform will be used by a single primary user for the foreseeable future; multi-user support is not assumed unless a future architecture review introduces it.
2. Gemini, Groq, and OpenRouter will each continue to offer usable free or low-cost tiers sufficient for personal-scale usage; if any provider's terms change materially, the Gateway's vendor-independence design is expected to absorb the impact without application-level rework.
3. Document volumes and Knowledge Base sizes will remain at personal scale (a working individual's accumulated documents, not enterprise-scale corpora) for the planning horizon of this PRD.
4. 768-dimensional embeddings are assumed sufficient for the platform's RAG and semantic search needs across the current roadmap; a change in embedding model/dimension would be a deliberate, tracked decision (the schema already stores `embedding_model` and `embedding_dimension` to support this).
5. The phase order defined in the architecture review (Phase 1 through Phase 8) reflects actual build priority; this PRD assumes phases are implemented sequentially rather than in parallel.
6. "Generous schema, lazy code" means some database fields/tables relevant to later phases (e.g., Memory-related fields) may exist structurally before Phase 4 code consumes them — this is intentional, not scope creep.

---

# Risks

| Risk | Impact | Mitigation |
|---|---|---|
| A primary AI provider (Gemini) changes pricing or deprecates a needed capability | Chat/RAG/Search degrade or become costly | AI Gateway's provider-agnostic design allows Secondary/Tertiary promotion without application-level changes |
| Free-tier limits (Neon, R2, Vercel, Render) are exceeded as usage grows | Service interruption or unexpected cost | Admin Dashboard (Phase 6) surfaces approach-to-limit before hard cutoffs; storage tiering moves cold data to R2 |
| Document extraction quality varies across PDF/DOCX sources (e.g., scanned PDFs, complex DOCX formatting) | Poor summarization/Q&A grounding, user distrust | Acceptance criteria require verifiable grounding; low-confidence extraction should be surfaced rather than silently presented as reliable |
| Memory system incorrectly retains or misapplies a stated preference/fact | Reduced trust in long-term memory | Memory Editing requirement ensures all memories are user-visible and deletable |
| Knowledge Base growth degrades vector search performance over time | Slower RAG/semantic search at scale | Archival of inactive vectors to R2 (per approved storage layering) keeps the active pgvector index lean |
| Single-developer/operator bandwidth limits how many phases can be actively maintained at once | Slipped roadmap, partially implemented phases | Sequential phase assumption (see Assumptions) keeps scope bounded per phase; "generous schema, lazy code" avoids rework when phases are picked up later |
| Provider API shape changes (Gemini/Groq/OpenRouter) break Gateway integration | Chat/RAG/Search outages | Gateway's internal abstraction isolates provider-specific changes to one module |

---

# Phase Mapping

| Requirement Area | Phase 1 | Phase 2 | Phase 3 | Phase 4 | Phase 5 | Phase 6 | Phase 7 | Phase 8 |
|---|---|---|---|---|---|---|---|---|
| Authentication | ✅ | | | | | | | |
| Chat System | ✅ | | | | | | | |
| AI Gateway (Gemini/Groq) | ✅ | | | | | | | |
| Usage Tracking | ✅ | | | | | | | |
| Monitoring (Sentry) | ✅ | | | | | | | |
| File Upload (PDF/DOCX/TXT) | | ✅ | | | | | | |
| Summarization & File Q&A | | ✅ | | | | | | |
| Knowledge Bases | | | ✅ | | | | | |
| RAG | | | ✅ | | | | | |
| Semantic Search | | | ✅ | | | | | |
| Memory System | | | | ✅ | | | | |
| User Preferences | | | | ✅ | | | | |
| Provider Routing (full health-aware) | | | | | ✅ | | | |
| OpenRouter (full integration) | | | | | ✅ | | | |
| Health Monitoring (providers) | | | | | ✅ | | | |
| Search Engine + Citations | | | | | | ✅ | | |
| Admin Dashboard | | | | | | ✅ | | |
| ZIP/CSV/XLSX/PPTX Analysis | | | | | | | ✅ | |
| Voice | | | | | | | | ✅ |
| Agents & Automation | | | | | | | | ✅ |

---

# Future Requirements

The following are anticipated but intentionally undefined in implementation detail, consistent with "generous schema, lazy code":

- **Multi-user account isolation** — if future scope expands beyond a single owner, requiring schema-level tenant boundaries beyond current single-user assumptions.
- **Sharing/permissions model** — read-only or collaborative access to specific Knowledge Bases by a third party.
- **Additional AI providers** beyond Gemini/Groq/OpenRouter — the Gateway's abstraction is designed to absorb this without requiring this PRD to enumerate specific future vendors.
- **Expanded file format support** beyond Phase 7's ZIP/CSV/XLSX/PPTX (e.g., audio transcripts, images-as-documents) — plausible but not committed.
- **Agent task types** (Phase 8) — the specific automations PrimeX AI can perform autonomously are not yet enumerated and will require their own requirements pass closer to Phase 8.
- **Voice provider selection** (Phase 8) — whether voice is handled via a new Gateway-style abstraction or a dedicated integration is undecided and out of scope for this PRD.

---

# Requirements Traceability Matrix

| Goal | Feature | Key Requirement | Phase |
|---|---|---|---|
| Foundation / Primary Goal 1 | Authentication | JWT + refresh token flow | Phase 1 |
| Foundation / Primary Goal 1 | Chat System | Streaming, persisted history | Phase 1 |
| Foundation / Primary Goal 1 | AI Gateway | Gemini primary, Groq fallback | Phase 1 |
| Vendor Independence / Primary Goal 4 | AI Gateway | Provider abstraction, Usage Tracking | Phase 1, hardened Phase 5 |
| Document Intelligence / Primary Goal 2 | File Intelligence | PDF/DOCX/TXT extraction, summarization, Q&A | Phase 2 |
| Document Intelligence / Primary Goal 2 | Knowledge Bases | Collections, vector search | Phase 3 |
| Document Intelligence / Primary Goal 2 | RAG System | Chunk retrieval, source attribution | Phase 3 |
| Memory / Primary Goal 3 | Memory System | Long-term memory, preferences, editing | Phase 4 |
| Vendor Independence / Primary Goal 4 | AI Gateway | Health-aware routing, OpenRouter maturity | Phase 5 |
| Research Quality / Secondary Goal 1 | Search System | Citations, search history | Phase 6 |
| Operational Visibility / Secondary Goal 2 | Admin Dashboard | Monitoring, storage, provider health | Phase 6 |
| Document Breadth / Secondary Goal 3 | File Intelligence (extended) | ZIP/CSV/XLSX/PPTX | Phase 7 |
| Long-Term Vision / Long-Term Goal 1 | Voice, Agents | Voice interaction, automation | Phase 8 |
| Architectural Continuity / Long-Term Goal 2 | All features | No cross-phase schema rework | All phases |
| Cost Discipline / Long-Term Goal 3 | Analytics, Admin Dashboard | Usage/storage visibility within free-tier limits | Phase 1 capture, Phase 6 surfacing |

---

# Conclusion

This PRD operationalizes the vision established in `01_Project_Vision.md` into requirements that are specific, testable, and traceable to the approved architecture and eight-phase roadmap. Every functional area — Authentication, Chat, AI Gateway, File Intelligence, Knowledge Bases, RAG, Memory, Search, Analytics, and Admin Dashboard — is defined with concrete requirements and acceptance criteria rather than aspirational language, and every requirement is mapped to the phase that delivers it.

No new technology, vendor, or architectural pattern has been introduced beyond what the architecture review already approved. The next document, `03_Final_Architecture.md`, will take these requirements and show precisely how the approved architecture satisfies each of them — system diagrams, data flow, and the technical structures that implement everything specified here.

---

*End of Document 2 — 02_Product_Requirements.md*
*Awaiting approval before proceeding to Document 3: 03_Final_Architecture.md*
