import os

from sqlalchemy import URL

# Hosted providers such as Neon hand out libpq-style URLs. SQLAlchemy would read
# them as psycopg2, which is not installed, so pin the installed psycopg 3 driver.
_LIBPQ_SCHEMES = ("postgresql://", "postgres://")


def normalize_database_url(url):
    for scheme in _LIBPQ_SCHEMES:
        if url.startswith(scheme):
            return "postgresql+psycopg://" + url[len(scheme) :]
    return url


def get_database_url():
    override = os.getenv("DATABASE_URL")
    if override:
        return normalize_database_url(override)
    return URL.create(
        "postgresql+psycopg",
        username=os.getenv("POSTGRES_USER", "daybook"),
        password=os.getenv("POSTGRES_PASSWORD") or None,
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        database=os.getenv("POSTGRES_DB", "daybook"),
    )


def get_migration_database_url():
    """Optional direct (non-pooled) connection for schema migrations."""
    url = os.getenv("MIGRATION_DATABASE_URL")
    return normalize_database_url(url) if url else None


DATABASE_URL = get_database_url()
MIGRATION_DATABASE_URL = get_migration_database_url()
MIGRATION_LOCK_TIMEOUT_SECONDS = int(os.getenv("MIGRATION_LOCK_TIMEOUT_SECONDS", "600"))


def get_cors_origins():
    return [origin.strip() for origin in os.getenv("CORS_ORIGINS", "").split(",") if origin.strip()]


CORS_ORIGINS = get_cors_origins()

# Built frontend served by the API in the combined production image. Unset locally.
FRONTEND_DIST = os.getenv("FRONTEND_DIST") or None

# Secure by default. Explicitly disable only for local HTTP development.
SESSION_COOKIE_NAME = "daybook_session"
SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "true").lower() == "true"
SESSION_TTL_SECONDS = int(os.getenv("SESSION_TTL_SECONDS", "604800"))
AUTH_RATE_LIMIT = int(os.getenv("AUTH_RATE_LIMIT", "10"))
AUTH_RATE_WINDOW_SECONDS = int(os.getenv("AUTH_RATE_WINDOW_SECONDS", "300"))
# Per-IP limits key on the TCP peer address. Behind a shared proxy that address is
# the proxy's, so they are switched off there instead of trusting forwarded headers.
AUTH_IP_RATE_LIMITS = os.getenv("AUTH_IP_RATE_LIMITS", "true").lower() == "true"
# With per-IP limits off: a ceiling on anonymous sign-in sessions across all clients.
AUTH_GLOBAL_SESSION_LIMIT = int(os.getenv("AUTH_GLOBAL_SESSION_LIMIT", "300"))
