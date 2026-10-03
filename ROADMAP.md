# Daybook roadmap

## Phase 0 — Foundation (implemented)

React/TypeScript/Vite/Tailwind shell and design tokens, locally bundled font, accessible responsive navigation, feature-based FastAPI architecture, SQLAlchemy models, Alembic migration, environment examples, Compose, docs, and test tooling.

Completion criteria: clean type/lint/build checks, migration-created schema, no automatic personal seeds, no cloud dependency, and localhost-only development access. PostgreSQL execution must be checked where a Docker daemon or PostgreSQL instance is available.

## Phase 1 — Everyday essentials (implemented)

Persisted task, calendar, grocery, bill, and preference workflows; dedicated views; explicit record-type capture; an agenda grouped by date; completion/purchased/paid filters; bounded pagination; query-derived dashboard; failure-preserving forms; deletion confirmation; realistic opt-in seed/clear commands.

Completion criteria: meaningful backend tests for persistence and constraints, timezone/date semantics, completion counts, exact unpaid totals, and CRUD; frontend tests for keyboard entry, failed requests, pending state, and date handling; visual inspection at desktop/mobile sizes and a create/edit/complete/delete browser workflow. See VERIFICATION.md for current evidence and any environment limits.

## Phase 2 — Meals and budgeting

Meal plans, recipes, grocery-list generation, budget categories, and recurring bills. Decide recurrence timezone and end-of-month semantics before implementation.

Completion criteria: a meal-to-grocery workflow with user-confirmed changes, decimal budget calculations with explicit currency boundaries, idempotent recurring bill generation, migrations, and no automatic payment movement.

## Phase 3 — Documents and retrieval

Local document library, text ingestion, document deletion lifecycle, and source-linked retrieval. Introduce EmbeddingProvider and VectorStore contracts; evaluate Ollama and Qdrant only at this phase.

Completion criteria: cited answers link to exact source passages, unsupported claims are identified, ingestion handles unsupported/corrupt files, deletion removes derived embeddings, and local data/storage limits are documented and tested.

## Phase 4 — Assistant

An optional local assistant behind LLMProvider, grounded in explicitly authorized Daybook records. Draft structured proposals and request user confirmation before applying changes.

Completion criteria: provenance for retrieved material, bounded tool access, no writes from untrusted retrieved instructions, inspectable proposed changes, cancellation, failure recovery, and tests covering incorrect or unavailable model output.

## Phase 5 — Calendar adapters and jobs

Introduce CalendarProvider adapters for selected calendar services, conflict-aware synchronization, opt-in credentials, incremental sync, and background jobs. Evaluate Celery/Redis when durable asynchronous work is actually needed.

Completion criteria: timezone and all-day fidelity, idempotent sync, explicit ownership/deletion rules, revocable credentials, retry/backoff without duplicates, and documented conflict behavior.

## Phase 6 — MCP and offline resilience

Expose narrow, validated MCP tools for authorized record access. Add offline browser reads/writes, synchronization, local export/import, backups, and conflict resolution.

Completion criteria: scoped tools with clear read/write permissions, confirmation for destructive operations, deterministic offline reconciliation, restore drills, and a documented boundary between local single-user use and any future multi-user deployment.

Ollama, Qdrant, Celery/Redis, external calendar adapters, and MCP servers are intentionally absent from the current Compose stack.

