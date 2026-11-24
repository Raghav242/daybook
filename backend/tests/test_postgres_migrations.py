"""Migration behavior on a real, disposable PostgreSQL database.

Runs only when TEST_DATABASE_URL points at PostgreSQL. That database must be
empty and disposable: these tests create and drop every Daybook table in it.
"""

import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, make_url, text

from app.infrastructure.database import Base
from app.infrastructure.migrations import (
    MIGRATION_LOCK_KEY,
    MigrationLockTimeout,
    migration_lock,
)

URL = os.getenv("TEST_DATABASE_URL", "")
BACKEND = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(
    not URL or make_url(URL).get_backend_name() != "postgresql",
    reason="Set TEST_DATABASE_URL to a disposable PostgreSQL database",
)


@pytest.fixture
def engine():
    engine = create_engine(URL)
    yield engine
    Base.metadata.drop_all(engine)
    with engine.begin() as connection:
        connection.execute(text("DROP TABLE IF EXISTS alembic_version"))
    engine.dispose()


def alembic(*args, **env):
    environment = {k: v for k, v in os.environ.items() if k != "MIGRATION_DATABASE_URL"}
    environment.update(DATABASE_URL=URL, **env)
    return subprocess.Popen(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def head_revision(engine):
    with engine.connect() as connection:
        return connection.scalar(text("SELECT version_num FROM alembic_version"))


def test_concurrent_startups_migrate_exactly_once(engine):
    processes = [alembic("upgrade", "head") for _ in range(3)]
    outputs = [p.communicate(timeout=180)[0] for p in processes]
    assert [p.returncode for p in processes] == [0, 0, 0], outputs
    assert head_revision(engine) == "0005"
    assert {"tasks", "users", "recipes", "income"} <= set(inspect(engine).get_table_names())


def test_migration_waits_for_the_lock_and_fails_after_the_timeout(engine):
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as holder:
        assert holder.scalar(text("SELECT pg_try_advisory_lock(:k)"), {"k": MIGRATION_LOCK_KEY})
        blocked = alembic("upgrade", "head", MIGRATION_LOCK_TIMEOUT_SECONDS="2")
        output = blocked.communicate(timeout=60)[0]
        assert blocked.returncode != 0
        assert "holds the lock" in output
        assert not inspect(engine).has_table("alembic_version")
        holder.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": MIGRATION_LOCK_KEY})


def test_lock_is_held_for_the_whole_block_on_its_own_connection(engine):
    acquired = threading.Event()
    release = threading.Event()

    def migrate():
        with migration_lock(engine, timeout_seconds=5):
            acquired.set()
            release.wait(10)

    worker = threading.Thread(target=migrate)
    worker.start()
    assert acquired.wait(10)
    with pytest.raises(MigrationLockTimeout):
        with migration_lock(engine, timeout_seconds=1):
            pass
    release.set()
    worker.join(10)
    started = time.monotonic()
    with migration_lock(engine, timeout_seconds=5):
        pass
    assert time.monotonic() - started < 3


def test_failed_migration_exits_non_zero_and_releases_the_lock(engine):
    # A pre-existing conflicting table makes the first migration fail.
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE tasks (id integer)"))
    failed = alembic("upgrade", "head")
    output = failed.communicate(timeout=120)[0]
    assert failed.returncode != 0, output
    with engine.connect() as connection:
        connection.execute(text("DROP TABLE tasks"))
        connection.commit()
    with migration_lock(engine, timeout_seconds=2):
        pass
