# Daybook

A personal, multi-user organizer for your day, plans and money: tasks, an agenda calendar, meals and groceries, bills, expenses, income and budgets. Phases 0, 1 and 2 are implemented, plus the "Everyday" redesign: a Today screen, four sections (Today, Plan, Money, Library), one Add action, shared category lists and manual income tracking. The interface uses locally bundled Newsreader (titles and date headings) and Inter (everything else), a warm near-white light theme and one ink-blue accent.

## Run with Docker Compose (recommended)

### Accounts and upgrading an existing database

New installations start empty. Open Daybook and choose **Create an account**. Usernames use 3–40 ASCII letters, numbers, dots, underscores or hyphens and are unique ignoring case. Passwords use 5–128 characters and are stored only as Argon2id hashes. Registration signs you in; no sample records are added. Login, registration, logout and session lookup are available under `/api/auth` (and root `/auth`).

Before upgrading a populated installation, back up PostgreSQL. Migration `0002` inspects record counts, adds users/sessions and nullable ownership, and removes the settings singleton constraint. Migration `0003` refuses to proceed if any personal row has no owner. Nothing is silently assigned or deleted. For legacy records, stop the app's frontend/backend during the maintenance window, then run:

```powershell
docker compose stop frontend backend
docker compose build backend
docker compose run --rm backend alembic upgrade 0002
docker compose run --rm backend python -m app.manage create-user --username YOUR_USERNAME
# Enter a password at the hidden prompts; never pass it as a command argument.
docker compose run --rm backend python -m app.manage claim-legacy --owner YOUR_USERNAME
# Review the counts and selected owner. Then explicitly assign:
docker compose run --rm backend python -m app.manage claim-legacy --owner YOUR_USERNAME --apply
docker compose run --rm backend alembic upgrade head
docker compose up -d --build
```

The assignment command affects only unowned rows, preserves record IDs/values, and refuses to overwrite an owner's existing settings. An already-existing account can be selected instead of creating one. The command requires an explicit existing username; registering a new account never claims legacy data. Migration `0002` is not automatically reversible after accounts/ownership exist: restore a pre-upgrade backup to return to the old schema. Empty databases can migrate directly to head.

### Cookies, CSRF and production domains

Sessions use opaque random tokens in an HttpOnly, host-only, `SameSite=Lax` cookie; only the SHA-256 token hash is stored in PostgreSQL. Login rotates the token and revokes the prior browser session. Logout revokes it server-side. Sessions expire after `SESSION_TTL_SECONDS` (default seven days); pre-login CSRF sessions expire after 30 minutes. The frontend keeps only its CSRF value in memory and never stores authentication tokens in localStorage. Private HTTP responses use `Cache-Control: no-store`; logout/account changes unmount private views and cancel their resource requests.

`SESSION_COOKIE_SECURE=true` is the backend default and required for HTTPS production. Local Compose explicitly defaults it to false for HTTP localhost. For host development set `SESSION_COOKIE_SECURE=false` in the backend process environment; host commands do not automatically load `.env`. Production Compose defaults it to true. Use the same hostname throughout local browsing (`localhost` or `127.0.0.1`).

Before a login/registration POST, call `GET /api/auth/csrf`, retain its cookie, and send its returned `csrf_token` in the `X-CSRF-Token` header. Authenticated `/auth/me` responses also return the current CSRF token. Every state-changing request requires the valid session-bound header; supplied `Origin` headers must match `CORS_ORIGINS`. Browser requests include credentials and CORS allows only configured exact origins. Do not use wildcard origins with cookies.

Because cookies are `SameSite=Lax`, unrelated provider domains such as `your-app.vercel.app` and `your-api.onrender.com` cannot use cross-site fetch authentication directly. Use a same-origin `/api` proxy (Vercel rewrites or Nginx), or same-site HTTPS custom domains such as `app.example.com` and `api.example.com`. For same-site separate origins, configure the public API build URL, credentialed CORS, and the exact frontend origin. CORS alone cannot override SameSite restrictions. Keep credentials out of frontend build variables.

Login is limited by both normalized username and client IP, using atomic database counters shared across API processes. Registration also has an IP limit. Defaults are `AUTH_RATE_LIMIT=10` attempts per `AUTH_RATE_WINDOW_SECONDS=300`; CSRF session creation allows 60 per IP per five minutes. Invalid logins return the same message for unknown accounts and wrong passwords. Behind a proxy, configure trusted forwarding only for your actual ingress; do not trust arbitrary client-supplied forwarding headers. With no trusted forwarding the IP bucket may be shared by all users behind the proxy. Schedule `python -m app.manage prune-auth` to remove expired sessions/counters. Email verification, social login and password recovery are outside this phase.

Prerequisites: Docker Desktop with its Linux engine running, or Docker Engine with Compose v2. The example environment publishes frontend/API/database ports 5173, 8001, and 5432 on loopback. Addresses and ports are configurable in .env.

From the repository root, in PowerShell:

```powershell
if (!(Test-Path .env)) { Copy-Item .env.example .env }
notepad .env
# Set POSTGRES_PASSWORD, save the file, then continue.
docker compose up --build -d
docker compose logs -f backend
```

With the example environment values, open [Daybook](http://localhost:5173). Docker API documentation: [OpenAPI](http://localhost:8001/docs). The backend applies `alembic upgrade head` before starting. A named PostgreSQL volume preserves data across restarts. Startup creates no personal records.

Compose requires a nonempty password from your ignored local `.env`. The committed `.env.example` has a blank password and there is no shared password fallback. Use single quotes around passwords containing `$` or `#`. Compose supplies separate credential variables to the backend, which constructs the SQLAlchemy connection URL safely for special characters.

### Environment-specific configuration

Compose defines the services, images, build paths, and persistent volume. Deployment connection settings reference variables. Local values live in `.env.example` and your private `.env`.

| Variables | Purpose |
|---|---|
| POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD | Database identity and secret |
| POSTGRES_HOST, POSTGRES_PORT | Backend's database address; POSTGRES_PORT also sets the bundled database's listening port |
| HOST_BIND_ADDRESS | Host interface for published ports; the template uses loopback |
| POSTGRES_PUBLISHED_PORT, BACKEND_PUBLISHED_PORT, FRONTEND_PUBLISHED_PORT | Ports you connect to on your computer |
| BACKEND_BIND_ADDRESS, BACKEND_PORT | Backend's listening address and port inside its container |
| FRONTEND_BIND_ADDRESS, FRONTEND_PORT | Frontend development server's listening address and port |
| CORS_ORIGINS | Allowed browser origins, comma separated |
| VITE_API_PROXY | Server-side development proxy target, using the Docker backend hostname and internal port |
| VITE_API_BASE_URL | Public browser API base: /api with the local proxy, or https://your-api.example/api |
| DATABASE_URL | Optional backend connection override, including managed PostgreSQL URLs and driver options |

Host-side and container-network addresses are distinct. With the template, your browser connects to localhost:5173, the frontend container proxies to backend:8000, and the backend connects to db:5432. Changing BACKEND_PUBLISHED_PORT does not change the internal proxy target. When changing BACKEND_PORT, update VITE_API_PROXY to match. When changing FRONTEND_PUBLISHED_PORT or the public domain, update CORS_ORIGINS.

Compose loads .env for variable substitution and passes selected values to each container. A different environment file can be selected explicitly:

```powershell
docker compose --env-file .env.staging config --quiet
docker compose --env-file .env.staging up -d --build
```

Environment-specific files are ignored by Git. Shell variables take precedence over file values. Use config --quiet to validate without printing resolved secrets.

### Cloud deployment scope

For cloud deployment, provide backend credentials through the platform's environment/secret settings and set CORS_ORIGINS to the actual frontend origin. Set VITE_API_BASE_URL to the browser-reachable API base, including /api, or keep /api behind a same-origin reverse proxy. VITE_* values are public frontend configuration and must contain no secrets.

For a production frontend, Vite captures VITE_API_BASE_URL during npm run build; set it in the cloud build environment and rebuild when it changes. The local Compose frontend reads it when the development server starts.

The default `compose.yaml` is for development. `compose.production.yaml` is a separate production stack with Nginx serving the built frontend, a non-root API process without reload, and a one-shot migration job. It uses an external PostgreSQL database; it does not start or publish a database container. No cloud deployment was performed.

### Development and production Docker workflows

Development keeps the existing `.env` and PostgreSQL volume:

```powershell
docker compose up -d --build
```

Frontend `src` and backend `app`/`migrations` directories are mounted for live reload. Vite uses polling for Docker Desktop. Rebuild for dependency, Dockerfile, or other configuration changes. Database migrations are applied at backend startup; after adding a migration, run `docker compose exec backend alembic upgrade head` or recreate the backend.

For production, edit the ignored `.env.production` (created from `.env.production.example` if missing). Set `DATABASE_URL` to a separate production PostgreSQL database, using `postgresql+psycopg://` and your provider's TLS options. URL-encode the username/password when putting them in a URL. Set `CORS_ORIGINS` to the public frontend origin. A local example origin is included only for testing; change it for deployment.

```powershell
if (!(Test-Path .env.production)) { Copy-Item .env.production.example .env.production }
notepad .env.production
docker compose --env-file .env.production -p daybook-production -f compose.production.yaml config --quiet
docker compose --env-file .env.production -p daybook-production -f compose.production.yaml up -d --build
docker compose --env-file .env.production -p daybook-production -f compose.production.yaml ps --all
```

Use the production file **by itself**, not merged with the development file. The distinct project name prevents local development containers from being replaced. The example publishes the frontend on localhost:8080 and leaves the backend private to the Docker network. Changing environments does not copy your local records into the production database.

The migration service must succeed before the backend starts, and the backend must pass its health check before the frontend starts. On subsequent releases, set a new `IMAGE_TAG` so Compose recreates the migration job for the new code. Back up the production database before schema changes. Do not run migrations concurrently from multiple replicas.

Same-origin mode uses `VITE_API_BASE_URL=/api`: Nginx forwards `/api` to `BACKEND_UPSTREAM` (an HTTP(S) base address with no trailing slash or `/api` suffix). Changing this internal upstream is a runtime change; recreate the frontend container. `NGINX_RESOLVER` is Docker's internal DNS in Compose; on another container platform use its DNS resolver.

For separate public frontend/API domains, set `VITE_API_BASE_URL=https://your-api.example/api` **before building** and `CORS_ORIGINS=https://your-app.example` on the backend. Rebuild the frontend when its API base changes. `BACKEND_UPSTREAM` still configures Nginx's optional same-origin API route. `VITE_API_PROXY` and the Vite development host/port variables are not used in production.

When the cloud provider deploys individual images rather than Compose, build the `production` targets from each Dockerfile. Supply the frontend build argument `VITE_API_BASE_URL`, and runtime variables `FRONTEND_PORT`, `BACKEND_UPSTREAM`, and `NGINX_RESOLVER`. Supply backend runtime variables `DATABASE_URL`, `CORS_ORIGINS`, `BACKEND_BIND_ADDRESS`, and `BACKEND_PORT`; its start command also accepts the provider's `PORT`. Run `alembic upgrade head` as a release job using the backend image before starting API replicas. The provider's service definitions replace Compose dependencies, port publication, and health checks.

Cloud ingress must provide HTTPS and route to the published frontend port. Keep loopback binding when a host reverse proxy handles ingress; configure the binding/network appropriately for your provider. Configure database backups and private network access. Daybook uses username/password authentication and per-user authorization. Keep all production traffic on HTTPS. CORS allows browser requests but does not replace authentication.

Commit `.env.example`, `.env.production.example`, Dockerfiles, Nginx templates, and Compose files. Keep `.env` and `.env.production` private; cloud secrets belong in the platform's secret manager, not in build arguments.

### Changing the password of an existing database

For a fresh database volume, PostgreSQL initializes its password from `.env`. For an existing volume, editing `.env` alone does not change PostgreSQL's stored password.

After entering the new password in `.env`, connect to the already-running database:

```powershell
docker compose exec db psql -U daybook -d daybook
```

Inside psql, run:

```text
\password daybook
```

Enter the same password as in `.env` twice at the hidden prompts, then exit with `\q`. The password prompt avoids putting the password in command history. Adapt the user/database names if you changed them.

Recreate the containers with the updated configuration, retaining the database volume:

```powershell
docker compose up -d --build
docker compose ps
docker compose logs --tail=30 backend
```

An ordinary `docker compose restart` does not apply changed container environment variables. The password update/recreation preserves existing records. Do not remove the database volume as part of a password change.

Explicit migration commands (Phase 2 adds migration `0004`; the redesign adds `0005` for categories and income). Back up first, as with any schema change:

```powershell
docker compose exec db pg_dump -U daybook daybook > daybook-backup.sql
docker compose exec backend alembic upgrade head
docker compose exec backend alembic current
# Roll back categories and income only if needed (deletes income, see below):
docker compose exec backend alembic downgrade 0004
# Roll back Phase 2 only if needed (deletes Phase 2 records, see below):
docker compose exec backend alembic downgrade 0003
```

Migration `0005` keeps every record and its category. Each existing free-text category becomes a category in the matching list (tasks, groceries and recipe aisles, or expenses and budgets, which share one list). Only values that differ by case or spacing are merged ("Coffee" and " coffee "), named after the most common spelling; a value equal to a starting category ("groceries") joins it. Every account also receives the starting lists. Downgrading to `0004` writes category names back into the text columns, and **permanently deletes** income records, unused categories and archive flags; merged spellings come back as the single merged name. `0005` must run against a live database; offline `--sql` generation is refused because it rewrites rows.

Migration `0004` preserves all existing records: existing tasks and bills become standalone (non-repeating) records, and accounts with saved preferences get the new Meals and Budget modules switched on (turn them off in Settings). Downgrading to `0003` **permanently deletes** recipes, meal plans, grocery-addition receipts, expenses, budgets and repeat definitions; already generated task and bill occurrences remain as ordinary tasks and bills, and Meals/Budget are removed from preferences. Offline `alembic upgrade --sql` scripts cannot update stored preferences.

Optional realistic samples, relative to the profile's current local date:

```powershell
docker compose exec backend python -m app.seed --owner demo
docker compose exec backend python -m app.seed --owner demo --clear
```

Create the designated demo account first with `docker compose exec backend python -m app.manage create-user --username demo` (hidden password prompts). Seeding is opt-in and idempotent, uses deterministic sample UUIDs, and does not change settings. Clearing removes only those known sample UUIDs, including samples you have edited. Other records are preserved. It never runs at startup.

Stop while retaining data:

```powershell
docker compose down
```

## Run development tools on the host

Prerequisites: Python 3.12+, Node.js 22.12+ (22 LTS recommended), npm, and PostgreSQL 17. You can use Compose for only PostgreSQL:

```powershell
docker compose up -d db
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
$env:POSTGRES_HOST = 'localhost'
$env:POSTGRES_PORT = '5432'
$env:POSTGRES_DB = 'daybook'
$env:POSTGRES_USER = 'daybook'
$env:POSTGRES_PASSWORD = (Get-Credential -UserName daybook -Message 'Enter the password from .env').GetNetworkCredential().Password
$env:CORS_ORIGINS = 'http://localhost:5173,http://127.0.0.1:5173'
$env:SESSION_COOKIE_SECURE = 'false' # Local HTTP only
Set-Location backend
..\.venv\Scripts\python.exe -m alembic upgrade head
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Match the process variables to your `.env` credentials. Host commands read process environment variables; copying `.env` alone does not set them. An explicit `DATABASE_URL` overrides the separate PostgreSQL variables, including for SQLite previews. In another terminal:

```powershell
Set-Location frontend
npm ci
npm run dev
```

Open [Daybook on loopback](http://127.0.0.1:5173). Vite proxies `/api` to `http://127.0.0.1:8000`; override with `VITE_API_PROXY` if needed. The frontend contains no database credentials. Bundled font files require no external font service.

On POSIX systems, use `.venv/bin/python` and `export NAME=value` instead of PowerShell syntax.

## SQLite verification / fallback preview

PostgreSQL is the application database in Compose. A migrated SQLite file is also supported for tests and a local preview when Docker is unavailable; it does not replace PostgreSQL integration testing.

From `backend`:

```powershell
$env:DATABASE_URL = 'sqlite:///./daybook.db'
..\.venv\Scripts\python.exe -m alembic upgrade head
..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Run the frontend as above. Optional samples can be cleared using `..\.venv\Scripts\python.exe -m app.seed --owner demo --clear` with the same database URL. The preview database is ignored by Git. SQLite and PostgreSQL stores are separate; no automatic synchronization or transfer is implemented.

## Verification commands

From `backend`:

```powershell
..\.venv\Scripts\python.exe -m pytest -q
..\.venv\Scripts\python.exe -m ruff check app tests migrations
..\.venv\Scripts\python.exe -m ruff format --check app tests migrations
```

Tests apply the real Alembic migrations to isolated temporary SQLite databases. Ownership checks use real database sessions and HTTP requests. To run the same tests against PostgreSQL, create a **dedicated disposable empty database**, then set `TEST_DATABASE_URL`. Tests migrate it and drop all Daybook tables after each test. Never use your personal database. Legacy migration tests also run against this disposable database when configured.

```powershell
# Create a separate database first (with a PostgreSQL client or database admin tool).
$env:TEST_DATABASE_URL = 'postgresql+psycopg://daybook:YOUR_URL_ENCODED_PASSWORD@localhost:5432/daybook_test'
..\.venv\Scripts\python.exe -m pytest -q
Remove-Item Env:TEST_DATABASE_URL
```

Replace the placeholder with your password, URL-encoding special characters when using an explicit connection URL.

From `frontend`:

```powershell
npm run typecheck
npm run lint
npm test
npm run build
```

From the root:

```powershell
docker compose config --quiet
```

The production frontend bundle is created in `frontend/dist` and copied into the Nginx production image. The default Compose file serves the development app; select `compose.production.yaml` explicitly for production mode.

## Everyday workflows

- **Navigation:** phones get four labeled bottom tabs (Today, Plan, Money, Library) with section links at the top of Plan (Tasks, Calendar, Meals, Groceries) and Money (Overview, Transactions, Budgets, Bills). Desktop uses the same structure in a compact sidebar. Settings and Log out are in the profile menu. Every page has a link (`#today`, `#tasks`, `#money`, `#transactions`, …); older links such as `#dashboard` and `#budget` still work. Sections whose modules are all turned off are hidden.
- **Today:** a dated heading; *Needs attention* only when something is overdue or over budget; one schedule combining timed events and timed tasks on a timeline, with date-only tasks and bills under *Due today*; *Anytime* for undated tasks; one *Coming up* list (events, dated and repeating tasks, bills for the next 7 days); and a short *At a glance* for meals, groceries and money when there is something to show. Previews are limited and link to the full lists. A new account sees a single starting state instead.
- **Add:** one Add button (sidebar on desktop, floating above the tab bar on phones) opens a dialog, or a bottom sheet on phones, for a Task, Event, Grocery, Expense, Income or Bill. Essential fields come first; notes, priority and repeat rules are under *More details*. No AI extraction.
- **Tasks:** create/edit, mark complete or reopen, filter completed/open, and delete with confirmation.
- **Calendar:** an agenda grouped by date with Upcoming, Past, and All filters. Upcoming includes ongoing events. Edit or delete each event.
- **Groceries:** quantities with units and categories; mark purchased or unpurchase; filters and CRUD.
- **Bills:** exact decimal amounts and currency codes; mark paid/unpaid; filters and CRUD. No payments are initiated.
- **Repeating tasks and bills:** choose *Repeats* (daily, weekly or monthly, every N, optional end date) when adding a task or bill. Each occurrence is a normal record you complete, pay, edit or delete on its own. When editing an occurrence choose *Only this occurrence* or *This and future occurrences*; *Stop repeating…* removes upcoming open occurrences and keeps completed, paid and overdue ones.
- **Paying bills:** ticking a bill opens *Mark bill paid*. Optionally record the payment as one linked expense (category and date). Repeating the request never creates a second expense. To mark such a bill unpaid, delete its expense first, so it is never counted as both spent and owed. Daybook records payments; it never moves money or connects to banks.
- **Meals:** save recipes with servings and ingredient quantities, plan them into a Monday–Sunday week (breakfast, lunch, dinner, snack) with their own servings, then choose *Make grocery list*. The review dialog shows scaled, merged quantities you can edit or leave out before adding. Meals already added are marked and never added twice; existing grocery items are never changed.
- **Money:** for the selected month and currency, *Overview* shows income received, expenses recorded and net cash flow (income minus expenses, explicitly not a balance), unpaid bills separately, and budget progress by expense category. *Transactions* lists expenses and income together with All / Expenses / Income filters. *Budgets* manages standing monthly limits. Income is entered manually (amount, currency, received date, source, note); refunds and transfers are not income.
- **Categories:** tasks, groceries (and recipe aisles), expenses and budgets, and income each pick from a dropdown with starting lists (for example Housing … Other for expenses; Salary, Part-time Work, Scholarship, Freelance, Gift, Other for income). *Add category* inside the selector saves a category for your account only. Long lists become searchable. In Settings → Categories you can rename, archive or restore; archived categories stay on existing records but are not offered for new ones.
- **Settings:** IANA timezone, default currency, enabled modules (Tasks, Calendar, Groceries, Bills, Meals, Money) and categories. Disabled modules retain their data and are hidden from navigation and Today.

Lists have 25-record pages, with bounded API pagination up to 100. Dashboard lists are intentionally compact; totals count every matching persisted record. Failed form saves keep input. Pending saves disable duplicate submissions; success and error messages are announced. Escape closes idle dialogs, focus stays in modal dialogs and returns to the trigger, and keyboard focus is visible.

## Data assumptions and limitations

- Accounts use session authentication and isolated personal records. Production requires HTTPS and correctly configured cookie/CORS settings.
- Defaults: `America/New_York`, `USD`, all six modules enabled. Set your timezone in Settings before entering timed events.
- Tasks have either `due_date` (a calendar date), `due_at` (an aware instant), or neither. Today's task count includes open overdue tasks and today's deadlines. Overdue task attention uses deadlines before today's local midnight.
- Timed events are stored as UTC instants and rendered in the profile's timezone. Task timed deadlines follow the same convention.
- All-day events have stable `start_date` and **exclusive** `end_date`; changing timezone never shifts those dates. UTC start/end instants are also retained. For a one-day event on October 2, enter October 2 through October 3.
- The time editor rejects nonexistent daylight-saving times. Ambiguous fall-back times use the timezone library's default occurrence; explicit offset selection is not implemented.
- Amounts and quantities use decimal strings in API contracts and SQL numeric columns. Bills support nonnegative amounts with two decimal places; three-letter uppercase currency codes are accepted. No currency conversion is performed. Totals stay separate by currency.
- Deletions are permanent after confirmation. Phase 2 relationships (occurrence → series, ingredient and meal → recipe, expense → bill) use same-owner composite foreign keys. Deleting a bill keeps its linked expense as spending. Settings are a singleton preference resource accessed through GET/PUT.
- Each write commits once; sample data is inserted/cleared in one transaction. Concurrent edits use last-write-wins; offline browser edits and conflict resolution are later work.
- “Local-first” means the local API/database owns data and the app requires no cloud services. A service worker or disconnected-browser synchronization is not included.
- **Recurrence:** occurrences are calendar dates, never instants; timed repeating tasks are not supported. "Today" is the profile timezone's local date, and changing the timezone never shifts stored occurrence dates. Weekly series repeat on the start date's weekday (one weekday per series). Monthly series always derive from the start date: an anchor on the 29th–31st falls on the last day of shorter months (Jan 31 → Feb 28/29 → Mar 31) without drifting.
- Occurrences are generated on demand when tasks, bills, the budget summary or the overview load, up to 42 days ahead; there are no background jobs. Generation is idempotent (one row per series and date, enforced by a unique key) and safe under concurrent requests. New series never backfill dates before today. A deleted occurrence is not recreated, except that *This and future* rebuilds upcoming open occurrences from the new rule. *This and future* keeps earlier occurrences and every completed or paid one; open overdue occurrences keep their dates and take the new details.
- **Meals:** quantities scale by planned ÷ recipe servings and round half-up to 0.001 (never to zero). Ingredients merge only when the name (ignoring case and spacing) and unit match; a small table recognizes spellings of the *same* unit (g/grams, tbsp/tablespoons, cup/cups). No conversions are made, so cups and grams stay on separate lines. Changing a planned meal after its groceries were added does not adjust the grocery list. Deleting a recipe removes its planned meals but keeps added groceries.
- **Money:** expenses, income, budgets and bills use exact decimals; income and expense dates are calendar dates. Budgets are standing monthly limits per expense category and currency, so past months are shown against current budget amounts. Currencies are never summed or converted; each has its own figures. Income never reduces reported spending or changes a budget. Paid bills without a recorded expense are not counted as spending. Recording a bill payment as an expense requires choosing an expense category (Utilities is preselected when it exists).
- **Categories:** names are unique per account and list, ignoring case and spacing. Categories can be archived but not deleted, so historical records always keep a readable category. The database enforces that a record's category belongs to the same account; the API additionally checks the list (scope).
- **Library** is a placeholder: documents are not implemented yet, and the page says so.
- Documents, RAG, assistants, external calendar integrations, background jobs and MCP are recorded in [ROADMAP.md](ROADMAP.md); their services are not installed or running.

See [ARCHITECTURE.md](ARCHITECTURE.md) for dependency direction and [VERIFICATION.md](VERIFICATION.md) for the checks performed in this workspace.

