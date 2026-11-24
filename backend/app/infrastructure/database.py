import sqlite3

from sqlalchemy import create_engine, event, make_url
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session

from app.core.config import DATABASE_URL


class Base(DeclarativeBase):
    pass


@event.listens_for(Engine, "connect")
def enforce_sqlite_foreign_keys(connection, record):
    if isinstance(connection, sqlite3.Connection):
        connection.execute("PRAGMA foreign_keys=ON")


def is_pooled_host(url):
    """Neon's PgBouncer endpoints carry ``-pooler`` in the host name."""
    return "-pooler" in (make_url(url).host or "")


def engine_options(url):
    options = {"pool_pre_ping": True}
    if make_url(url).get_backend_name() == "postgresql":
        # Hosted Postgres closes idle connections and may suspend the compute.
        options["pool_recycle"] = 300
        if is_pooled_host(url):
            # Transaction pooling may route statements to different server sessions.
            options["connect_args"] = {"prepare_threshold": None}
    return options


engine = create_engine(DATABASE_URL, **engine_options(DATABASE_URL))


def get_session():
    with Session(engine) as session:
        yield session
