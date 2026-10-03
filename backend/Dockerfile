FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN useradd --create-home --uid 10001 daybook
USER daybook

FROM base AS development

FROM base AS production
# Cloud providers may supply PORT; Compose supplies BACKEND_PORT.
CMD ["sh", "-c", "exec uvicorn app.main:app --host \"$BACKEND_BIND_ADDRESS\" --port \"${PORT:-$BACKEND_PORT}\""]

