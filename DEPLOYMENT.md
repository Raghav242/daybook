# Deploying Daybook to Render (Free) with Neon PostgreSQL

One Render web service runs the combined image built from the root [Dockerfile](Dockerfile).
FastAPI serves both the API (`/api/*`) and the built frontend (`/`, `/assets/*`) from the
same HTTPS origin. Neon provides PostgreSQL. Deploys happen only when you run the
**Deploy to Render** GitHub Actions workflow by hand.

Local development is unchanged: `compose.yaml`, `backend/Dockerfile` and
`frontend/Dockerfile` are not used by this deployment.

## How a deploy works

1. You start **Actions → Deploy to Render → Run workflow** on `main`.
2. CI tests that exact commit:
   - backend: ruff, pytest on SQLite, and pytest on a disposable PostgreSQL 17 service
     container (including concurrent and failing migrations);
   - frontend: lint, typecheck, tests, production build;
   - image: builds the root Dockerfile, runs it against a disposable PostgreSQL, and runs
     [scripts/smoke_production.py](scripts/smoke_production.py) (static frontend, cache
     headers, API 404s, CSRF/Origin checks, cookie flags, register/logout/login, a write).
3. Only if every job passes, the `deploy` job (GitHub environment `production`) runs
   [.github/scripts/render_deploy.py](.github/scripts/render_deploy.py). It:
   - refuses to deploy if Render auto-deploy is on;
   - calls Render's API with `commitId` set to the tested SHA (`github.sha`);
   - polls the deploy until it is `live`, and fails the workflow on `build_failed`,
     `update_failed`, `pre_deploy_failed`, `canceled`, `deactivated`, or after 25 minutes.

## Migrations

Render Free has no pre-deploy command or one-off jobs, so the container runs
`alembic upgrade head` before starting the server. Startup migrations:

- use `MIGRATION_DATABASE_URL` (Neon's **direct** connection) when set, else `DATABASE_URL`;
- refuse to run through a Neon pooled (`-pooler`) host, because a session advisory lock
  does not work through transaction pooling;
- take a PostgreSQL advisory lock on a dedicated autocommit connection and hold it until
  every migration has finished, so overlapping starts run them once, one at a time. A
  waiting start gives up after `MIGRATION_LOCK_TIMEOUT_SECONDS` (default 600);
- stop startup on any error. The new deploy then fails its health check and Render keeps
  the previous release serving traffic. The workflow reports the failure.

### Rollback does not undo schema changes

Rolling back in Render (or deploying an older commit) changes the **application code only**.
Schema changes already applied to Neon stay applied, and the older code then runs against
the newer schema. Before deploying a migration:

- create a Neon branch or point-in-time restore point as a backup;
- prefer additive, backward-compatible migrations (add columns/tables first, remove later);
- if you must reverse a migration, run `alembic downgrade <revision>` deliberately against the
  direct connection from a trusted machine. Some downgrades delete data (see the README).

## Client IP, proxies and rate limits

Render's load balancer terminates TLS and forwards requests to the service, which is not
directly reachable from the internet. Render's documentation does not describe how it sets
or sanitizes `X-Forwarded-For` or similar headers, so the app does not trust them: uvicorn
runs with `--no-proxy-headers`, and the client address is always the TCP peer (the proxy).

Because every request shares that address, the image sets `AUTH_IP_RATE_LIMITS=false`:

- login attempts are limited **per username** (`AUTH_RATE_LIMIT` per
  `AUTH_RATE_WINDOW_SECONDS`), exactly as before;
- registrations share one global bucket (`AUTH_RATE_LIMIT` per window);
- anonymous sign-in sessions share one global bucket (`AUTH_GLOBAL_SESSION_LIMIT` per
  5 minutes, default 300).

No limit uses a client-supplied header, so none can be bypassed by spoofing one. A flood of
traffic can temporarily block new sign-ins or registrations for everyone; existing sessions
are unaffected. Local development keeps the per-IP limits (`AUTH_IP_RATE_LIMITS` defaults to
true).

## Caching

- `/` and `/index.html`: `Cache-Control: no-cache` with ETag/Last-Modified (always revalidated).
- `/assets/<name>-<8-char hash>.<ext>` (Vite's fingerprinted output):
  `public, max-age=31536000, immutable`.
- Everything else, including all API responses and 404s: `no-store`.
- Unknown `/api/*` paths and other unknown paths return the API's JSON 404; there is no
  catch-all rewrite to the frontend (the app uses hash routes).

## Free-tier behavior

- The service spins down after 15 minutes without traffic; the next request takes about a
  minute (plus Neon's own resume time). Startup migrations add only a version check when the
  schema is current.
- One instance, 512 MB memory, no shell or SSH. Use `python -m app.manage …` from a trusted
  machine with the direct Neon URL if you need the account tools.

## Running the image locally

Never point this at your real database. Use a disposable PostgreSQL:

```bash
docker build -t daybook:local .
docker run --rm -p 127.0.0.1:10000:10000 \
  -e DATABASE_URL='postgresql://USER:PASSWORD@host.docker.internal:PORT/DB' \
  -e CORS_ORIGINS=https://daybook.local.example \
  daybook:local
python scripts/smoke_production.py http://127.0.0.1:10000 https://daybook.local.example
```

See [.env.render.example](.env.render.example) for every variable.
