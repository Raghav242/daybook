# Architecture

## Phase 0 / Phase 1 boundaries

Daybook is a modular monolith. React/TypeScript/Vite renders a local dashboard; FastAPI/Pydantic serves a versioned-by-release HTTP contract; SQLAlchemy 2.x persists to PostgreSQL, with Alembic as the only normal schema-creation path. Docker Compose runs three services: frontend, backend, and database.

`backend/app/modules/{auth,tasks,calendar,groceries,bills,settings}` contains each feature's SQLAlchemy domain/persistence model, input/output schemas, repository, application service, and routes. Dashboard has a read-only repository/service/router that composes feature records. Its aggregate counts and per-currency numeric totals are SQL queries rather than browser estimates.

Dependency direction:

```text
HTTP routes → application services → feature repositories → SQLAlchemy session
                                      ↓
                              feature domain models
React feature views → shared typed API client → HTTP routes
```

HTTP routes validate transport inputs, choose status codes, and construct dependencies. Feature services own use cases and not-found behavior; Calendar service computes timezone-aware boundaries for upcoming/past filters. Repositories alone query and commit database writes. FastAPI's session dependency closes and rolls back failed transactions. Service constructors accept repositories explicitly, enabling narrow test replacements without generic inheritance.

Domain models deliberately double as SQLAlchemy entities in this small monolith; separate duplicate entity classes would add mapping without a current need. Business input invariants live with Pydantic feature schemas and are reinforced by database constraints.

## Authentication and ownership

The auth feature follows the same routes → services → repositories boundaries. Routes handle cookies and typed transport contracts; AuthService owns password verification, token rotation, CSRF validation, session lifetime, and throttling; AuthRepository performs database operations. A reusable `current_user` dependency validates the HttpOnly cookie, loads its user, and verifies CSRF on writes. No personal route accepts an ownership identifier from the browser. Record services assign the authenticated repository's user_id on create and reject mismatched records. List/get queries, dashboard aggregates, feature filters, and settings reads include ownership explicitly. Another user's UUID receives 404; frontend visibility is never the authorization boundary.

Users retain a display username and an explicit casefold-normalized username with a database uniqueness constraint. The accepted ASCII username alphabet makes normalization predictable. Argon2id password hashes use argon2-cffi, with rehashing after successful verification when parameters change. Unknown accounts perform dummy-hash verification; wrong credentials share one error message. Password inputs use SecretStr and are not returned or logged.

AuthSession stores a SHA-256 token hash, nullable user_id, and expiry. Anonymous 30-minute sessions protect login/registration against CSRF. Cryptographic random tokens only travel in host-only HttpOnly, SameSite=Lax cookies. A separate domain-separated CSRF value derived from the random token is returned to the client; writes must return it as a header. Authentication replaces the prior token and revokes it. Logout deletes the session; expiry is checked on every lookup. Secure cookies default on, with explicit local HTTP configuration. Exact credentialed CORS and supplied-Origin checks complement CSRF; same-site domains or same-origin proxies are needed for Lax cookies.

Rate-limit counters use atomic PostgreSQL upserts shared by all replicas, keyed by hashes of client IP and normalized username, with expiring windows. Proxy trust must be limited to real ingress addresses. Operational pruning removes expired sessions and counters. Sessions and counters are authentication infrastructure; they contain no personal dashboard records.

Frontend App owns session bootstrap and the auth gate. It renders no private component before `/auth/me` succeeds. Login/registration preserve usernames, use password-manager attributes, and display consistent errors. The private React tree is keyed by account/generation and is unmounted on logout, expiry, or cross-tab account changes; aborted resource requests cannot publish old data. CSRF remains in memory, cookies are sent with credentials, and authentication tokens never enter localStorage. Private responses are not cached by HTTP intermediaries.

Migrations `0002`/`0003` separate nullable ownership expansion from mandatory ownership. Existing counts are inspected; `0003` refuses unowned records. The administrative command explicitly selects an existing owner and previews counts before `--apply`. It does not overwrite conflicting settings. Seeds require a designated existing account, use owner-specific deterministic IDs, and run only on request.

Future documents, embeddings/vector chunks, background jobs, calendar credentials, and MCP access must carry and enforce user ownership in their services, storage queries and worker execution. Relationship creation must fetch every referenced record under the current user and enforce same-owner foreign keys/constraints where practical. Never run global vector search and rely on UI filtering; never accept a job, calendar or MCP user_id as authorization. Email verification, social login and password recovery remain out of scope.

## Persistence

Feature record IDs and user IDs are UUIDs. Lists are bounded, paginated, and stably sorted by a final UUID key. Deadlines, completion flags, paid flags, purchased flags, and event start times have indexes. Text limits are enforced at the API boundary; SQL column lengths reinforce them on PostgreSQL.

Dates and UTC instants are distinct. A UTC SQLAlchemy type preserves awareness on the SQLite test adapter; PostgreSQL uses timestamp with timezone. All-day events keep dates independently of UTC instants so their calendar dates survive timezone preference changes. Date-range queries use the profile timezone and honor variable-length daylight-saving days.

Bill amounts use `Numeric(14, 2)` / Decimal and grocery quantities use `Numeric(12, 3)` / Decimal. JSON serializes decimals as strings. Frontend numeric conversion is used only for display formatting; persisted values are submitted as strings. Currency totals are grouped in SQL.

Each create/update/delete is one transaction. The seed command uses one transaction for all records, uses deterministic UUIDs, skips existing samples, and can remove exactly those IDs. No personal samples run on startup. Tables have no foreign keys to one another, so deletion has no cascade or orphan behavior. Settings has one unique user_id per account; missing preferences read as defaults until explicitly saved. Personal tables reference users with non-null indexed ownership. No existing personal record relationships cross feature tables.

Migration `0001` contains explicit table/index/constraint definitions. Normal startup does not call `create_all`. SQLite tests run those same Alembic definitions, and an optional dedicated PostgreSQL test URL exercises the same behavior on the target engine.

## Frontend

`src/app/App.tsx` owns navigation, selected editor/deletion dialog, shared settings/dashboard refresh, and mutation notifications. Each feature has an entry view. Calendar has its own date-grouped agenda. Tasks, Groceries, and Bills share a record list renderer because paging, filters, and row controls have the same responsibility.

`shared/api/contracts.ts` is the maintained API contract: feature fields, decimal strings, nullable deadlines, page metadata, preferences, and dashboard response. `client.ts` centralizes every HTTP request, typed response, and consistent error decoding. Components never call fetch directly. API inputs/output schemas and contract changes must be reviewed together.

`useResource` cancels outdated requests and exposes loading/error/data states. Initial lists load with a status message; background refreshes preserve rows. Mutations refresh summaries, including counts that may fall outside visible pages. Minute/visibility refreshes keep dates and summaries current. Draft form state stays in the open form after failed requests.

The shared native dialog provides modal semantics, focus confinement, initial form focus, Escape handling, pending-save protection, and trigger focus restoration. Destructive actions require explicit confirmation. CSS tokens use warm ivory/green, minimal shadows, locally bundled Inter, visible focus, and reduced-motion support. Desktop columns become one reading column on mobile, with compact navigation.

## Errors and contracts

Create returns 201, delete returns 204, missing records return 404, validation returns 422, and SQLAlchemy failures return 503. Error bodies use `{error: {code, message, details?}}`. Validation includes field paths; database details are logged server-side and never returned to the browser. Pydantic rejects unexpected write fields. Full PUT updates include the current status so editing preserves completion/purchase/payment state.

Health is process liveness, not a database readiness claim. OpenAPI is available at `/docs`. List endpoints accept offset/limit plus feature status filters; calendar accepts all/upcoming/past. Settings is an account-scoped GET/PUT. Dashboard is a read-only composite resource.

## Deferred provider seams

Later integrations will introduce `LLMProvider`, `EmbeddingProvider`, `VectorStore`, and `CalendarProvider` as service-injected contracts in their corresponding feature modules. They will sit behind application services; HTTP controllers and React views will not depend on adapter SDKs. No empty interfaces, speculative adapters, or later-phase services are implemented now.

## Operational scope

Compose gets all connection addresses, ports, CORS origins, proxy targets, and browser API base from environment variables. The example environment publishes loopback ports, uses a named PostgreSQL volume and database health dependency, and migrates before API startup. Listening ports and Docker port mappings use the same supplied values. Host development retains loopback defaults. There is no cloud hosting deployment in this repository. Session authentication and explicit per-user authorization protect personal API resources.

Secrets belong in ignored environment files/process variables. `.env.example` contains non-secret development defaults and a blank password. Compose requires POSTGRES_PASSWORD and supplies separate credentials to the backend; SQLAlchemy URL.create handles special characters without manual URL interpolation. An explicit DATABASE_URL overrides those variables for host development or SQLite tests. Node dependencies are locked in package-lock.json; backend requirements constrain major versions. SQLite fallback is explicitly for local verification/preview, not a PostgreSQL replacement or cloud replica.

The browser API client reads public VITE_API_BASE_URL and defaults to the same-origin /api path. Production bundles capture this value at build time; local Docker's Vite server receives it at startup. Database credentials are never supplied to frontend containers.

Dockerfiles have development and production targets. Default Compose mounts application source for Vite/Uvicorn reload and retains the local PostgreSQL volume. The standalone compose.production.yaml uses external PostgreSQL, a one-shot migration service, a non-root API without reload, and a built frontend served by Nginx. Only the frontend port is published. Nginx proxies /api to an environment-supplied upstream, with configurable DNS resolution. Separate public domains are supported through the frontend build argument and backend CORS origin. Cloud platforms deploying individual images must supply their own migration job, networking, health checks, persistence/backups, HTTPS, and ingress security configuration.

