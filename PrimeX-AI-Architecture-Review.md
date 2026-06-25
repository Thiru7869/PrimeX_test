# PrimeX AI — Architecture Review
### Senior Staff / Cloud Architecture / AI Infrastructure Assessment
*Reviewed against verified free-tier limits as of June 2026*

---

## TL;DR

The architecture is **sound and worth building**. It is not the architecture of a portfolio project — it's a reasonable architecture for a single-user system designed to run for years on free infrastructure. That said, three of your assumptions don't survive scrutiny as stated, and I'm changing them below:

1. **Don't add Supabase anywhere in this stack.** It looks like a free upgrade and is actually a downgrade for your use case — explained in Section 2.
2. **Your roadmap defers basic provider fallback too late.** Building five phases of features on a single LLM provider before adding a fallback path is a real operational risk, not a nice-to-have you can postpone. Move it up.
3. **"Modular from day one" is correct for data models, wrong for code.** Building abstract plumbing for dormant modules (voice, agents) before you've built the first real version of anything similar is speculative complexity — the exact thing you said you want to avoid. I separate what's cheap to do early from what isn't.

Everything else holds up. Details follow.

---

## 1. Architecture Plan

**Is the 3-layer model (R2 archive / Postgres+pgvector active / LLM intelligence) right?** Yes, with one clarification: this is a storage-tiering model, not a service architecture. Don't let the diagram imply three deployed systems — you have two deployed services (Next.js frontend, FastAPI backend) and three external dependencies (R2, Neon, LLM providers). Keep that distinction clear in your own head as you build, or you'll over-engineer service boundaries that don't need to exist.

**Should the backend be FastAPI/Python at all, or could this be Next.js API routes end-to-end?** This is worth challenging directly, and I'd keep Python — but for a specific reason, not by default. Python's document-processing ecosystem (pdfplumber, python-docx, openpyxl, python-pptx, pytesseract) is more mature than the Node equivalent for the file-intelligence module specifically. That's a real, defensible reason to maintain a separate Python service. If file intelligence weren't in scope, I'd tell you to collapse everything into Next.js and skip Render entirely. Since it is in scope, keep FastAPI — but recognize you're paying for it with a second deployed service, a second cold-start source, and a second place secrets and logging have to be managed.

**Hidden problem #1: compounding cold starts.** Render free services sleep after 15 minutes idle (~30-60s wake), and Neon scales to zero independently (~300-500ms wake). When you haven't used the app in a while, both will be asleep simultaneously. Your first request after idle isn't a 500ms hit, it's Render's wake time *plus* Neon's wake time *plus* your actual query — realistically 1-2 seconds before any real work starts. For a single user this is annoying, not fatal. Decide now that this is acceptable rather than rediscovering it as a "bug" later.

**Hidden problem #2: "keep the full architecture visible from day one" is half right.** Designing your database schema, module boundaries, and folder structure to accommodate future modules (voice, agents) is cheap and worth doing now — schemas are easy to extend and hard to retrofit. But building actual abstraction layers (plugin interfaces, dependency-injection containers, generic "module" base classes) for features you haven't built yet is a different thing, and it's expensive in a specific way: you're guessing at the right abstraction before you have a single real implementation to abstract *from*. You will guess wrong, and then you'll pay twice — once to build the speculative scaffolding, once to tear it out when the real voice/agent feature needs something different. Generous schema, lazy code. That's the actual rule, not "build it all now."

---

## 2. Infrastructure Plan

**Vercel + Render + Neon + R2 remains the right stack in 2026.** Here's what changed since you'd have evaluated this a year ago, and why the alternatives don't beat it:

- **Fly.io is dead as a free option.** It removed its permanent free tier in 2024; new accounts get a 2-hour trial, then a credit card is mandatory. Cross it off entirely — any "use Fly.io for the backend" version of this plan no longer exists.
- **Railway's free tier isn't viable for always-on.** It's a one-time $5 credit, then $1/month — nowhere near enough to keep a service running continuously. Fine for occasional batch jobs, not your backend.
- **Supabase is not a free upgrade over Neon — challenge this one directly.** Supabase bundles Postgres + Auth + Storage + Edge Functions, which sounds like it collapses your stack. But on the free tier: 500 MB database (essentially identical to Neon's 0.5 GB, no win there), only 1 GB of file storage (worse than R2's 10 GB), and — this is the disqualifying one — **free Supabase projects pause after 7 days of inactivity and require a manual restore from the dashboard.** Neon's "scale to zero" is automatic and transparent (300-500ms wake on next request); Supabase's pause is a hard outage until you personally intervene. For a personal app you might not touch every single day, that's a materially worse failure mode. Don't add Supabase to this stack for the database. The one place it's worth a second look is *Supabase Auth specifically*, as a "buy don't build" alternative to rolling your own — but since you're not using Supabase for anything else, that means standing up a second identity system that has to stay in sync with your own Postgres `users` table. That's added complexity, not removed complexity. **Verdict: roll your own auth.** At single-user scale, email + password + bcrypt + JWT access/refresh tokens is a solved, low-risk problem. Don't import a vendor for it.
- **Vercel Hobby is correct for the frontend, with one ToS catch worth knowing.** Hobby is explicitly restricted to personal, non-commercial use, and serverless functions cap at 10-60 seconds depending on configuration. Since PrimeX AI is genuinely personal, the ToS restriction is fine *today*. Just know that if this ever becomes something you share or monetize, Vercel Hobby stops being compliant the moment it does — that's a future migration trigger to keep in mind, not a current problem. The function timeout is the other reason your FastAPI backend should own anything that takes a while (file processing, RAG retrieval + generation) rather than trying to do it in a Next.js API route.

**What I'd choose today, unchanged from your plan:** Vercel (frontend) + Render (backend) + Neon (database) + Cloudflare R2 (storage) + Gemini/Groq/OpenRouter (LLM layer). Your instincts here were right; the alternatives that look free are not.

---

## 3. Deployment Plan

- **Repo structure:** monorepo (`frontend/`, `backend/`, `docs/`). You're a solo developer; a monorepo means atomic commits across frontend/backend changes and one CI config to maintain, with no real downside at this scale.
- **CI/CD:** you don't need a custom deployment pipeline. Both Vercel and Render deploy automatically on push to `main` via their native Git integration — that's your CD, free, with zero extra config. Use GitHub Actions for what Git-triggered deploys *don't* cover: running lint/tests before merge, and a scheduled job for the weekly `pg_dump` → R2 backup (see Section 4). Public repos get unlimited GitHub Actions minutes; private repos get a free monthly allowance that's more than enough for a backup cron and a test suite at your scale.
- **Environments:** skip building a full staging environment for v1 — Render's free tier doesn't give you a second free backend instance, and standing up a paid staging service defeats the free-tier goal. Use Vercel's automatic preview deployments (free, per-PR) as your de facto frontend staging, and a local Docker Compose setup (or a Neon database *branch* — instant, copy-on-write, costs nothing extra against your compute allowance) for backend testing before you push to `main`.
- **Secrets:** platform-native environment variables (Vercel and Render dashboards) for production secrets. `.env.local`, gitignored, for local dev. No third-party secrets manager — that's an extra moving part with no real benefit at single-user scale.
- **Local development:** the cleanest version of this uses a Neon branch as your local/dev database instead of running Postgres+pgvector in Docker. Branching is instant and copy-on-write, so you get a real database that matches production schema exactly, with no version drift between your local Postgres and Neon's managed version. For R2, use a second free bucket as your dev bucket — 10 GB is enough to split between dev and prod without going near the limit.

---

## 4. Database Strategy

**PostgreSQL + pgvector, not a dedicated vector database.** Your relational data (users, chats, messages, foreign keys) belongs in Postgres regardless. The question is whether vectors should live there too, versus a dedicated vector store (Pinecone, Qdrant Cloud, Weaviate Cloud — all of which have free tiers). At single-user scale, a separate vector DB buys you nothing and costs you a second system to keep in sync with your Postgres metadata, a second auth boundary, and a second failure mode. pgvector's performance ceiling is in the hundreds of thousands to low millions of vectors before you need to think about it seriously — you are not going to get there as one person within years. Keep vectors in Postgres.

**Storage math, restated precisely:** a 768-dimension float32 embedding is ~3 KB raw; with pgvector's HNSW index overhead, budget roughly 6-8 KB per stored chunk in practice. Against a realistic 300 MB working budget (leaving room for chat history, users, audit logs), that's tens of thousands of chunks — genuinely enough for a real personal knowledge base. At 3072 dimensions (Gemini's default, un-truncated) you'd fit roughly a quarter of that. **Truncate to 768 dimensions explicitly via `output_dimensionality` — don't take the model default.**

**The risk nobody mentions: relational table growth, not just vectors.** Chat messages, usage-tracking rows, and audit logs all consume the same 0.5 GB budget as your vectors. A retention/archival policy needs to cover *all* tables that grow unboundedly, not just the knowledge base. Decide your chat-history retention window now (e.g., keep 90 days active in Postgres, archive older transcripts to R2 as JSON) rather than discovering the database is full of three-year-old chat logs you never look at.

**Embedding model lock-in is real and underdiscussed.** Embedding spaces between model versions are not compatible — switching embedding models (even a version upgrade from the same provider) requires re-embedding your entire knowledge base from scratch; there's no migration path that preserves existing vectors. Treat the embedding model choice as a slow-moving decision, and store the model name + dimension alongside every vector row. That single column is the difference between "we know exactly which vectors need re-embedding if we ever switch" and "we have to guess."

**Backup strategy:** weekly `pg_dump` via a scheduled GitHub Action, written to R2. This is cheap, decouples your backup from Neon's own retention policy, and is your real disaster-recovery story for a system you intend to run for years. **Test the restore process at least once.** A backup that has never been restored is a hypothesis, not a backup.

---

## 5. Storage Strategy

**R2 over every alternative, and it's not close.** S3's free tier is a 12-month trial, not permanent. Backblaze B2 also offers free egress, but only through a Cloudflare-specific bandwidth partnership that adds a layer of configuration you don't need when R2 gives you the same zero-egress guarantee natively. Supabase Storage's 1 GB free tier is a tenth of R2's 10 GB. R2 is the correct, uncontested choice for file storage.

**File lifecycle, concretely:**
1. Upload → original file stored in R2.
2. Extract text → store the extracted text in R2 alongside the original (cheap, and saves re-running OCR/extraction if you ever want to re-chunk with different parameters).
3. Chunk + embed → vectors land in Postgres/pgvector; raw text stays in R2.
4. Archive → when a collection is archived, export its vectors + metadata to R2 and hard-delete the Postgres rows. Reactivation reads the export back from R2 — no re-embedding API call needed, since you exported the vectors themselves, not just the source text.
5. Backup → the weekly `pg_dump` lands in R2 too.

One storage primitive (R2) ends up serving four distinct jobs: file archive, extracted-text cache, vector cold storage, and database backup target. That's good design — don't introduce a second storage service to split these across.

**Hot vs. cold, restated:** Postgres is your hot/working layer (active queries need to be fast). R2 is cold storage for everything that doesn't need millisecond access — originals, archived vectors, backups. This division is correct as designed; keep it.

---

## 6. AI Strategy

**Provider order: Gemini Flash primary, Groq secondary, OpenRouter tertiary.** This was already the right call, for the reasons established earlier in this conversation — Gemini's free tier is by far the most generous in daily request volume and token throughput, Groq is faster but tighter on daily caps per model, and OpenRouter's free tier is the thinnest of the three (its daily floor only improves once you've funded the account with a one-time $10, which permanently raises it). Use OpenRouter as the last resort, not a coequal fallback.

**Embeddings:** `gemini-embedding-001`, truncated to 768 dimensions via `output_dimensionality`. Free tier access is available through Google AI Studio for testing and development volumes consistent with single-user use.

**Routing strategy:** build a provider-usage table (`provider`, `date`, `request_count`, `token_count`) and check it before routing, not after a 429 forces your hand. On failure, mark a provider "cooling down" for a fixed window rather than retrying it every request — this is the difference between a graceful fallback and a system that hammers a dead provider on every single user action.

**Cost optimization, beyond what's been said:** cache stable system prompts where the provider supports cached-token discounts; never re-embed content you've already embedded (the R2 vector-archive pattern in Section 5 exists partly for this reason); batch embedding calls where the workflow allows it instead of one chunk at a time.

**The lock-in risk that matters here isn't the LLM provider — it's the embedding model**, covered in Section 4. Switching chat providers costs you nothing structural. Switching embedding models costs you your entire knowledge base's vector store.

---

## 7. Monitoring Strategy

- **Logging:** at single-user traffic volume, don't onboard a third-party log aggregator (Better Stack, Axiom, etc.) just to avoid grepping. A structured `request_logs` table in Postgres (pruned on a schedule) covers this, with old entries exported to R2 instead of a separate vendor relationship to manage.
- **Error tracking:** this is a different job than general logging — it needs stack-trace grouping and alerting, which a Postgres table doesn't give you cleanly. Sentry's free tier is realistically sized for single-user traffic and is worth the one integration. Use it for errors specifically; keep general request logs in your own table.
- **Alerting:** if you want an uptime check, a free monitor (e.g., UptimeRobot, which offers up to 50 free monitors) hitting a health endpoint works — but don't use it as a keep-warm trick to dodge Render's cold start. That just burns your 750 free instance-hours faster for a UX improvement you don't need as a single user. Accept the cold start; use the monitor purely for "tell me if this is actually down," at a low ping frequency.
- **Analytics:** you don't need a separate analytics pipeline. The provider-usage table from Section 6 *is* your usage analytics. Phase 6's "usage analytics" feature should be a dashboard reading that existing table, not a new data-collection system.

---

## 8. Security Strategy

- **Authentication:** roll your own — email/password, bcrypt hashing, JWT access + refresh tokens. Solved problem at this scale; don't add a vendor identity provider for one user.
- **Authorization:** trivial today, but put `user_id` foreign keys on every table now, even though there's only one user. This is the one piece of "design for multi-user before you have multiple users" that's genuinely cheap — it's a column, not an abstraction. Don't mistake this for "adding a second user later will be painless," though — auth, quota-sharing, and billing-readiness all still need real work whenever that day comes. The FK just means you won't have to do a destructive schema migration to get there.
- **Secrets:** platform-native env vars only, rotated periodically, distinct keys per environment. Never logged — make sure your structured request logging in Section 7 explicitly scrubs auth headers and API keys before anything is written.
- **File security:** never make the R2 bucket public. Serve files via short-lived signed URLs. Validate file type and size server-side — don't trust client-side checks — both to prevent storage abuse and because malformed files are also your most likely crash vector in the file-intelligence module.
- **API security:** rate-limit your own backend endpoints, even at single-user scale. This isn't about attackers — it's about a frontend bug or a runaway retry loop silently burning through your entire daily Gemini/Groq quota in minutes and locking you out of your own app for the rest of the day. A simple per-user request counter in Postgres covers this.
- **RAG security — the one most projects skip entirely:** retrieved document chunks can contain text that looks like instructions ("ignore previous instructions and...") if a malicious or even just adversarially-formatted document ends up in your knowledge base — importing a scraped webpage or an untrusted PDF is the realistic path in. Treat retrieved content as data, never as instructions: wrap it in clearly delimited blocks in your prompt template, and don't give RAG-retrieved text the same authority as your system prompt. Low probability for a personal KB you curate yourself, but it costs nothing to design the prompt template correctly from the start.

---

## 9. Feature Roadmap — Order Review

Your eight-phase roadmap is fundamentally right. One concrete change:

**Move basic provider fallback into Phase 1, not Phase 5.** As written, you build five phases of features — chat, files, RAG, memory — all running on Gemini alone, with no fallback path, before you add Groq/OpenRouter routing in Phase 5. That means for the majority of the build, a Gemini outage or an unexpected quota change blocks your entire development and testing workflow, not just a feature. Your "AI Gateway Foundation" in Phase 1 should ship with *at least* one working fallback path (Gemini → Groq) from day one, even if it's the simplest possible implementation. Full provider monitoring, OpenRouter integration, and a polished routing dashboard can absolutely stay in Phase 5 — but "if the primary provider fails, try a second one" is infrastructure every later phase depends on, not a feature to add later.

Everything else in your ordering — auth/chat first, files before knowledge bases, knowledge bases before memory, search and admin last, voice/agents deferred to the end — is the right sequence and I wouldn't change it.

---

## 10. Top 20 Risks

1. **Neon's 0.5 GB storage** is the one hard ceiling in this entire architecture — and it's consumed by chat history and logs just as much as by vectors.
2. **Embedding model lock-in** — switching models means re-embedding the entire knowledge base from scratch, with no migration path.
3. **Free-tier policy drift** — Render's spin-down window already tightened once (30 min → 15 min); Neon's compute allowance already doubled once. These tiers move, in both directions, without warning.
4. **Compounding cold starts** (Render + Neon both asleep) creating multi-second delays on first use after idle that can feel like the app is broken.
5. **An untested backup** — a `pg_dump` you've written but never restored is a hope, not a recovery plan.
6. **RAG prompt injection** via an adversarial or malicious document entering the knowledge base.
7. **Zip bombs / decompression bombs** once ZIP support (Phase 7) lands — a classic attack surface even in a single-user context if you ever import files from external sources.
8. **Speculative abstraction** — building plugin/module plumbing for voice or agents before you've built a single real implementation to generalize from.
9. **No second pair of eyes** — as a solo maintainer, silent failures stay silent until you personally notice; your own alerting is the only safety net you have.
10. **Vercel Hobby's commercial-use restriction** — fine today, but it means sharing or monetizing this later isn't a feature flag, it's a tier migration across your whole frontend hosting.
11. **Secrets leakage** via a committed `.env` or an unscrubbed log line containing an API key.
12. **Quota self-DoS** — a retry loop or frontend bug burning your entire daily Gemini/Groq allowance in minutes, locking you out of your own app.
13. **Migration footguns** — Alembic migrations run directly against a tiny production database with no real staging environment to test against first.
14. **Dependency rot** — Next.js, FastAPI, LangChain, and assorted Python file-processing libraries will all ship breaking changes over a multi-year timeline; infrequent maintenance windows mean bigger, riskier upgrade jumps.
15. **Connection pool exhaustion** — Neon's free tier caps pooled connections; careless connection handling (especially if you ever add edge functions) can exhaust this faster than expected.
16. **Fragile document parsing** — scanned PDFs, password-protected files, and corrupted uploads need graceful degradation in the file-intelligence module, not crashes.
17. **Silent token-budget blowups** — stuffing too many retrieved chunks into a RAG prompt inflates Gemini token usage in ways that don't show up until you're unexpectedly near your daily cap.
18. **The multi-user FK isn't a free pass** — `user_id` columns make a future second user *possible*, not *easy*; auth, quotas, and billing-readiness are still real work whenever that day comes.
19. **External search API dependency** (Phase 6) — whatever free search API you pick will have its own quota and policy-drift risk, identical in kind to the LLM-provider risk; apply the same fallback thinking there.
20. **Loss of momentum** — for a solo, years-long project, the biggest realistic threat isn't a technical one. A "modular but mostly dormant" architecture can produce long stretches with little visible progress, which is exactly the condition that kills personal infrastructure projects. Keep every phase shippable and demoable to yourself.

---

## 11. Free-Tier Sustainability

**Yes — this can realistically run for years on free tiers as a single-user platform.** The reframing in your previous message was correct: nearly every quota here (Gemini's 1,500 requests/day, Render's 750 instance-hours/month, R2's 10 GB) has enormous headroom against one person's actual usage pattern. You were never going to hit most of these ceilings.

**The first bottleneck you'll hit, with high confidence, is Neon's 0.5 GB storage** — and it'll arrive from accumulated chat history and unpruned logs as much as from the knowledge base itself, likely within months of real daily use if archiving isn't active from the start.

**The second bottleneck, much further out, is R2's 10 GB** — only a concern if you're uploading large media files heavily; for documents and PDFs, you're realistically years away from this.

**The bottleneck that isn't a tier limit at all is your own maintenance time** — dependency upgrades, provider API changes, and the operational policies in Sections 4-8 all need periodic attention. For a system meant to run for 3-5 years, this is the actual long-term constraint, not anything Render or Neon will ever bill you for.

---

## 12. Final Recommendation

If I were responsible for this codebase for the next 3-5 years, I'd keep your architecture almost exactly as proposed, with these concrete amendments:

- **Don't add Supabase.** Roll your own auth; keep Neon for the database.
- **Truncate embeddings to 768 dimensions** via `output_dimensionality`, and store the model name + dimension on every vector row from day one.
- **Pull basic Gemini→Groq fallback into Phase 1's gateway**, not Phase 5 — full routing/monitoring can stay later, but the fallback path itself can't.
- **Let R2 do four jobs**: file archive, extracted-text cache, vector cold storage, and database backup target. Don't add a second storage service for any of these.
- **Add Sentry for error tracking from Phase 1.** Skip building custom analytics — your provider-usage table already is your analytics.
- **Treat Neon's 0.5 GB as the one binding constraint** in the entire system, and write down — even informally — what happens at 90% full before you're at 90% full.
- **Design data models generously for dormant modules (voice, agents); write zero abstraction code for them until you build the first real version.** Generous schema, lazy code.

The foundation is genuinely stable. What's left is operational discipline — storage lifecycle, provider routing, and backup verification — executed consistently as you build, not a redesign.
