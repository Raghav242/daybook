import os

from sqlalchemy import URL


def get_database_url():
    override = os.getenv("DATABASE_URL")
    if override:
        return override
    return URL.create(
        "postgresql+psycopg",
        username=os.getenv("POSTGRES_USER", "daybook"),
        password=os.getenv("POSTGRES_PASSWORD") or None,
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        database=os.getenv("POSTGRES_DB", "daybook"),
    )


DATABASE_URL = get_database_url()


def get_cors_origins():
    return [origin.strip() for origin in os.getenv("CORS_ORIGINS", "").split(",") if origin.strip()]


CORS_ORIGINS = get_cors_origins()

# Secure by default. Explicitly disable only for local HTTP development.
SESSION_COOKIE_NAME = "daybook_session"
SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "true").lower() == "true"
SESSION_TTL_SECONDS = int(os.getenv("SESSION_TTL_SECONDS", "604800"))
AUTH_RATE_LIMIT = int(os.getenv("AUTH_RATE_LIMIT", "10"))
AUTH_RATE_WINDOW_SECONDS = int(os.getenv("AUTH_RATE_WINDOW_SECONDS", "300"))
