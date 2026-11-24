"""Connection choice and cross-process serialization for Alembic migrations."""

import time
from contextlib import contextmanager

from sqlalchemy import make_url, text

from app.core import config
from app.infrastructure.database import is_pooled_host

# Fixed application-wide key for pg_advisory_lock ("daybook" as a signed bigint).
MIGRATION_LOCK_KEY = 0x6461_7962_6F6F_6B


class MigrationLockTimeout(RuntimeError):
    pass


def migration_url():
    url = config.MIGRATION_DATABASE_URL or config.DATABASE_URL
    if make_url(url).get_backend_name() == "postgresql" and is_pooled_host(url):
        # A session-level advisory lock is meaningless through transaction pooling.
        raise RuntimeError(
            "Migrations need a direct (non-pooled) PostgreSQL connection. "
            "Set MIGRATION_DATABASE_URL to the database's direct connection string."
        )
    return url


@contextmanager
def migration_lock(engine, timeout_seconds=None):
    """Hold a session-level advisory lock on a dedicated connection.

    The lock connection runs in autocommit mode, so it never sits idle in a
    transaction, and stays open until every migration has finished. Closing
    the connection (including when the process dies) releases the lock.
    SQLite and other backends need no lock: they are single-process here.
    """
    if engine.dialect.name != "postgresql":
        yield
        return
    timeout = config.MIGRATION_LOCK_TIMEOUT_SECONDS if timeout_seconds is None else timeout_seconds
    deadline = time.monotonic() + timeout
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as lock_connection:
        acquire = text("SELECT pg_try_advisory_lock(:key)")
        while not lock_connection.scalar(acquire, {"key": MIGRATION_LOCK_KEY}):
            if time.monotonic() >= deadline:
                raise MigrationLockTimeout(
                    f"Another migration still holds the lock after {timeout} seconds."
                )
            time.sleep(1)
        try:
            yield
        finally:
            lock_connection.execute(
                text("SELECT pg_advisory_unlock(:key)"), {"key": MIGRATION_LOCK_KEY}
            )
