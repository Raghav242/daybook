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
