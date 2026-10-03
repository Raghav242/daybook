# Daybook

A local-first, single-user dashboard for tasks, an agenda calendar, groceries, and bills. Phase 0 and Phase 1 are implemented. Warm ivory surfaces, locally bundled Inter, a composed dashboard, responsive navigation, and explicit quick capture keep everyday work easy to find.

## Run with Docker Compose (recommended)

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

Cloud ingress must provide HTTPS and route to the published frontend port. Keep loopback binding when a host reverse proxy handles ingress; configure the binding/network appropriately for your provider. Configure database backups and private network access. Daybook still has no application authentication: protect the deployment with an access gateway/VPN covering every public frontend and API entry point, or add authentication before exposing personal records publicly. CORS is not access control.

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

Explicit migration commands:

```powershell
docker compose exec backend alembic upgrade head
docker compose exec backend alembic current
```

Optional realistic samples, relative to the profile's current local date:

```powershell
docker compose exec backend python -m app.seed
docker compose exec backend python -m app.seed --clear
```

Seeding is idempotent, uses deterministic sample UUIDs, and does not change settings. Clearing removes only those known sample UUIDs, including samples you have edited. Other records are preserved. It never runs at startup.

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
Set-Location backend
..\.venv\Scripts\python.exe -m alembic upgrade head
..\.venv\Scripts\python.exe -m app.seed
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
..\.venv\Scripts\python.exe -m app.seed
..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Run the frontend as above. Optional samples can be cleared using `..\.venv\Scripts\python.exe -m app.seed --clear` with the same database URL. The preview database is ignored by Git. SQLite and PostgreSQL stores are separate; no automatic synchronization or transfer is implemented.

## Verification commands

From `backend`:

```powershell
..\.venv\Scripts\python.exe -m pytest -q
..\.venv\Scripts\python.exe -m ruff check app tests migrations
..\.venv\Scripts\python.exe -m ruff format --check app tests migrations
```

Tests apply the real Alembic migration to isolated temporary SQLite databases. To run the same tests against PostgreSQL, create a **dedicated disposable empty database**, then set `TEST_DATABASE_URL`. Tests migrate it and drop all Daybook tables after each test. Never use your personal database.

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

- **Overview:** persisted counts, today's overlapping events, prioritized open tasks, overdue items, upcoming plans, grocery items, and unpaid bill totals due through 30 days from today.
- **Quick capture:** choose Tasks, Calendar, Groceries, or Bills, then enter the corresponding fields. No AI extraction.
- **Tasks:** create/edit, mark complete or reopen, filter completed/open, and delete with confirmation.
- **Calendar:** an agenda grouped by date with Upcoming, Past, and All filters. Upcoming includes ongoing events. Edit or delete each event.
- **Groceries:** quantities with units and categories; mark purchased or unpurchase; filters and CRUD.
- **Bills:** exact decimal amounts and currency codes; mark paid/unpaid; filters and CRUD. No payments are initiated.
- **Settings:** IANA timezone, default currency, and enabled modules. Disabled modules retain their data.

Lists have 25-record pages, with bounded API pagination up to 100. Dashboard lists are intentionally compact; totals count every matching persisted record. Failed form saves keep input. Pending saves disable duplicate submissions; success and error messages are announced. Escape closes idle dialogs, focus stays in modal dialogs and returns to the trigger, and keyboard focus is visible.

## Data assumptions and limitations

- One profile, no login or multi-user isolation. Keep the services on your own computer. This is not a secure multi-user deployment.
- Defaults: `America/New_York`, `USD`, all four modules enabled. Set your timezone in Settings before entering timed events.
- Tasks have either `due_date` (a calendar date), `due_at` (an aware instant), or neither. Today's task count includes open overdue tasks and today's deadlines. Overdue task attention uses deadlines before today's local midnight.
- Timed events are stored as UTC instants and rendered in the profile's timezone. Task timed deadlines follow the same convention.
- All-day events have stable `start_date` and **exclusive** `end_date`; changing timezone never shifts those dates. UTC start/end instants are also retained. For a one-day event on October 2, enter October 2 through October 3.
- The time editor rejects nonexistent daylight-saving times. Ambiguous fall-back times use the timezone library's default occurrence; explicit offset selection is not implemented.
- Amounts and quantities use decimal strings in API contracts and SQL numeric columns. Bills support nonnegative amounts with two decimal places; three-letter uppercase currency codes are accepted. No currency conversion is performed. Totals stay separate by currency.
- Deletions are permanent after confirmation. There are no cross-record foreign keys or cascades in Phase 1. Settings are a singleton preference resource accessed through GET/PUT.
- Each write commits once; sample data is inserted/cleared in one transaction. Concurrent edits use last-write-wins; offline browser edits and conflict resolution are later work.
- “Local-first” means the local API/database owns data and the app requires no cloud services. A service worker or disconnected-browser synchronization is not included.
- Documents, meal planning, budgeting, RAG, assistants, integrations, and MCP are recorded in [ROADMAP.md](ROADMAP.md); their services are not installed or running.

See [ARCHITECTURE.md](ARCHITECTURE.md) for dependency direction and [VERIFICATION.md](VERIFICATION.md) for the checks performed in this workspace.

