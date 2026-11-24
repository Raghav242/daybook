# Combined production image for single-service hosting (e.g. Render):
# FastAPI serves the API and the built frontend from one origin.
# Local development keeps using compose.yaml with backend/ and frontend/ Dockerfiles.

FROM node:22-alpine AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
# Public configuration only: the browser calls the API on the same origin.
RUN VITE_API_BASE_URL=/api npm run build

FROM python:3.12-slim AS production
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FRONTEND_DIST=/app/static \
    SESSION_COOKIE_SECURE=true \
    AUTH_IP_RATE_LIMITS=false \
    PORT=10000
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/alembic.ini ./
COPY backend/migrations ./migrations
COPY backend/app ./app
COPY --from=frontend /frontend/dist ./static
RUN useradd --create-home --uid 10001 daybook
USER daybook
EXPOSE 10000
# 1. Apply migrations under a PostgreSQL advisory lock; any error stops startup,
#    so the platform keeps the previous release live.
# 2. Serve on the platform's PORT. Proxy headers are ignored on purpose: the
#    client address is never taken from spoofable X-Forwarded-* headers.
CMD ["sh", "-c", "set -e; alembic upgrade head; exec uvicorn app.main:app --host 0.0.0.0 --port \"$PORT\" --no-proxy-headers"]
