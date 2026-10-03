# Verification

Checks completed October 2, 2026 (America/New_York).

## Automated checks

- Backend: **14 pytest tests passed**, applying the real Alembic migration to isolated SQLite databases. Coverage includes task completion/dashboard counts, date-only vs aware timed deadlines, timezone and daylight-saving day boundaries, exact currency-separated unpaid bill totals, CRUD, validation/error shapes, pagination, settings persistence, all-day date fidelity, calendar upcoming/past filters, and idempotent seed/clear preserving personal records.
- Backend lint: Ruff passed. Formatting check passed for all 50 Python files.
- Frontend: **7 Vitest/React Testing Library tests passed**. Coverage includes failed saves preserving input and retry, keyboard bill entry, duplicate-submission prevention, date-only timezone stability, daylight-saving input rejection, all-day event rendering, and recovery from an emptied later page after deletion.
- TypeScript type checking, ESLint, and production frontend build passed.
- Docker Compose configuration validated using `docker compose config --quiet`.
- Alembic PostgreSQL offline migration SQL generated successfully; includes UUIDs, timezone-aware timestamps, numeric amounts/quantities, indexes, and constraints.
- Dependency install audit reported zero vulnerabilities after updating Vitest to 4.1.11. This is a point-in-time registry audit, not a complete security assessment.

## Browser inspection

Used the Codex in-app browser at `http://127.0.0.1:5173`.

- Desktop dashboard inspected, including sidebar, composed columns, lower summaries, and full-page alignment.
- Mobile viewport 390 × 844 inspected. Dashboard has a single-column reading order; navigation and agenda editors fit. A small navigation overflow was corrected; document width did not exceed viewport width.
- Task created with notes, high priority and a date-only deadline; dashboard count increased. Title edited, completion persisted and count decreased, dedicated list showed its checked state, and confirmation/deletion returned the list to its prior count.
- All-day calendar entry created at mobile size, appeared in its date group, and was deleted through confirmation.
- Keyboard Enter activated Quick capture; record-type selector received initial focus; Tab reached Title; Escape closed the modal and focus returned to Quick capture.
- Disposable verification task/event records were removed. Other records were preserved.
- Final desktop/mobile screenshots are in `verification/desktop.jpg` and `verification/mobile.jpg`.

## Environment limits

Docker Desktop's Linux engine was stopped (its named pipe was absent), so the full Compose stack and live PostgreSQL tests **were not run**. Compose configuration and PostgreSQL migration SQL were checked, but this does not verify live PostgreSQL behavior. README includes commands for a dedicated PostgreSQL test database.

The running preview uses an explicitly migrated, persisted SQLite file at `backend/daybook.db`, with opt-in sample data. PostgreSQL remains the default configured application database and the only Compose database.

The backend test tooling emitted a Starlette/httpx deprecation warning; tests passed. No later-phase services were installed or started.

Local first currently requires the local API to be running; disconnected browser writes/sync, authenticated multi-user access, public production hosting, and later-phase modules remain outside scope.

## October 3 configuration update

Deployment addresses, published/listening ports, CORS origins, proxy targets, database credentials, and the public browser API base are now supplied through environment variables. The private .env was extended without overwriting existing values, and Git ignore was verified.

- Backend: 19 tests passed, including password-special-character handling, database URL override, CORS parsing, and real Docker Compose model validation with isolated fake environment files. Compose checks covered a required password and non-default addresses/ports/URLs; they do not require the Docker daemon.
- Frontend: 9 tests passed, including configured and same-origin browser API bases. Type checking, ESLint, and production build passed.
- Backend Ruff lint and formatting passed.
- Existing database volumes and running containers were not changed or restarted. The earlier SQLite preview and stopped-daemon notes describe the original October 2 verification; the user subsequently started Docker independently.
- Live cloud deployment and production access controls remain unverified and outside the local development setup.

## October 3 development/production Docker workflows

- Backend: 21 tests passed; Ruff lint and formatting passed. Compose model tests cover missing production database credentials, private API ports, migration ordering, no source mounts in production, and separation of frontend build arguments from database secrets.
- Frontend: 9 tests passed; ESLint and production build passed.
- Both production Docker images built successfully through Docker Desktop.
- An isolated production Compose smoke test used a separate temporary PostgreSQL 17 database on tmpfs and frontend loopback port 18080. Migrations completed, API and frontend health checks passed, static frontend and SPA fallback returned 200, and dashboard/API health requests passed through Nginx. A task was created, listed, and deleted through the production proxy and PostgreSQL.
- Temporary smoke-test containers, network, and configuration files were removed. The user's running local containers, credentials, and database volume were not changed. Private .env.production was created only if missing; both private environment files are ignored by Git.
- Actual cloud ingress/TLS, split-domain provider networking, authentication, and development live reload were not runtime-tested. No cloud deployment or Git commit/push was performed.
