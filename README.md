# Daybook

A local-first, single-user dashboard for tasks, an agenda calendar, groceries, and bills. Phase 0 and Phase 1 are implemented. Warm ivory surfaces, locally bundled Inter, a composed dashboard, responsive navigation, and explicit quick capture keep everyday work easy to find.

## Run with Docker Compose (recommended)

Prerequisites: Docker Desktop with its Linux engine running, or Docker Engine with Compose v2. Ports 5173, 8000, and 5432 must be available. All published ports bind to loopback.

From the repository root, in PowerShell:

```powershell
Copy-Item .env.example .env
docker compose up --build -d
docker compose logs -f backend
```

Open [Daybook](http://localhost:5173). API documentation: [OpenAPI](http://localhost:8000/docs). The backend applies `alembic upgrade head` before starting. A named PostgreSQL volume preserves data across restarts. Startup creates no personal records.

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
$env:DATABASE_URL = 'postgresql+psycopg://daybook:daybook_local@localhost:5432/daybook'
$env:CORS_ORIGINS = 'http://localhost:5173,http://127.0.0.1:5173'
Set-Location backend
..\.venv\Scripts\python.exe -m alembic upgrade head
..\.venv\Scripts\python.exe -m app.seed
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Match the database URL to your `.env` credentials. Host commands read process environment variables; copying `.env` alone does not set them. In another terminal:

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
$env:TEST_DATABASE_URL = 'postgresql+psycopg://daybook:daybook_local@localhost:5432/daybook_test'
..\.venv\Scripts\python.exe -m pytest -q
Remove-Item Env:TEST_DATABASE_URL
```

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

The production frontend bundle is created in `frontend/dist`. Compose intentionally serves the development app; this is a local development setup, not a public production deployment.

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

