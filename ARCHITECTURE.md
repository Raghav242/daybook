# Architecture

## Phase 0 / Phase 1 boundaries

Daybook is a modular monolith. React/TypeScript/Vite renders a local dashboard; FastAPI/Pydantic serves a versioned-by-release HTTP contract; SQLAlchemy 2.x persists to PostgreSQL, with Alembic as the only normal schema-creation path. Docker Compose runs three services: frontend, backend, and database.

`backend/app/modules/{tasks,calendar,groceries,bills,settings}` contains each feature's SQLAlchemy domain/persistence model, input/output schemas, repository, application service, and routes. Dashboard has a read-only repository/service/router that composes feature records. Its aggregate counts and per-currency numeric totals are SQL queries rather than browser estimates.

Dependency direction:

```text
HTTP routes → application services → feature repositories → SQLAlchemy session
                                      ↓
                              feature domain models
React feature views → shared typed API client → HTTP routes
```

HTTP routes validate transport inputs, choose status codes, and construct dependencies. Feature services own use cases and not-found behavior; Calendar service computes timezone-aware boundaries for upcoming/past filters. Repositories alone query and commit database writes. FastAPI's session dependency closes and rolls back failed transactions. Service constructors accept repositories explicitly, enabling narrow test replacements without generic inheritance.

Domain models deliberately double as SQLAlchemy entities in this small monolith; separate duplicate entity classes would add mapping without a current need. Business input invariants live with Pydantic feature schemas and are reinforced by database constraints.

## Persistence

All personal record IDs are UUIDs. Lists are bounded, paginated, and stably sorted by a final UUID key. Deadlines, completion flags, paid flags, purchased flags, and event start times have indexes. Text limits are enforced at the API boundary; SQL column lengths reinforce them on PostgreSQL.

Dates and UTC instants are distinct. A UTC SQLAlchemy type preserves awareness on the SQLite test adapter; PostgreSQL uses timestamp with timezone. All-day events keep dates independently of UTC instants so their calendar dates survive timezone preference changes. Date-range queries use the profile timezone and honor variable-length daylight-saving days.

Bill amounts use `Numeric(14, 2)` / Decimal and grocery quantities use `Numeric(12, 3)` / Decimal. JSON serializes decimals as strings. Frontend numeric conversion is used only for display formatting; persisted values are submitted as strings. Currency totals are grouped in SQL.

Each create/update/delete is one transaction. The seed command uses one transaction for all records, uses deterministic UUIDs, skips existing samples, and can remove exactly those IDs. No personal samples run on startup. Tables have no foreign keys to one another, so deletion has no cascade or orphan behavior. Settings uses an integer singleton key constrained to 1; missing preferences read as documented defaults until explicitly saved.

Migration `0001` contains explicit table/index/constraint definitions. Normal startup does not call `create_all`. SQLite tests run those same Alembic definitions, and an optional dedicated PostgreSQL test URL exercises the same behavior on the target engine.

## Frontend

`src/app/App.tsx` owns navigation, selected editor/deletion dialog, shared settings/dashboard refresh, and mutation notifications. Each feature has an entry view. Calendar has its own date-grouped agenda. Tasks, Groceries, and Bills share a record list renderer because paging, filters, and row controls have the same responsibility.

`shared/api/contracts.ts` is the maintained API contract: feature fields, decimal strings, nullable deadlines, page metadata, preferences, and dashboard response. `client.ts` centralizes every HTTP request, typed response, and consistent error decoding. Components never call fetch directly. API inputs/output schemas and contract changes must be reviewed together.

`useResource` cancels outdated requests and exposes loading/error/data states. Initial lists load with a status message; background refreshes preserve rows. Mutations refresh summaries, including counts that may fall outside visible pages. Minute/visibility refreshes keep dates and summaries current. Draft form state stays in the open form after failed requests.

The shared native dialog provides modal semantics, focus confinement, initial form focus, Escape handling, pending-save protection, and trigger focus restoration. Destructive actions require explicit confirmation. CSS tokens use warm ivory/green, minimal shadows, locally bundled Inter, visible focus, and reduced-motion support. Desktop columns become one reading column on mobile, with compact navigation.

## Errors and contracts

Create returns 201, delete returns 204, missing records return 404, validation returns 422, and SQLAlchemy failures return 503. Error bodies use `{error: {code, message, details?}}`. Validation includes field paths; database details are logged server-side and never returned to the browser. Pydantic rejects unexpected write fields. Full PUT updates include the current status so editing preserves completion/purchase/payment state.

Health is process liveness, not a database readiness claim. OpenAPI is available at `/docs`. List endpoints accept offset/limit plus feature status filters; calendar accepts all/upcoming/past. Settings is a singleton GET/PUT. Dashboard is a read-only composite resource.

## Deferred provider seams

Later integrations will introduce `LLMProvider`, `EmbeddingProvider`, `VectorStore`, and `CalendarProvider` as service-injected contracts in their corresponding feature modules. They will sit behind application services; HTTP controllers and React views will not depend on adapter SDKs. No empty interfaces, speculative adapters, or later-phase services are implemented now.

## Operational scope

Compose publishes only loopback ports, uses a named PostgreSQL volume and database health dependency, and migrates before API startup. The frontend development server listens inside its container while the host publish remains loopback. Host dev servers bind 127.0.0.1. There is no public hosting, authentication, or multi-user security boundary.

Secrets belong in ignored environment files/process variables. `.env.example` contains local-only development defaults. Node dependencies are locked in package-lock.json; backend requirements constrain major versions. SQLite fallback is explicitly for local verification/preview, not a PostgreSQL replacement or cloud replica.

