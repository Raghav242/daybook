import json
import os

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.core import config
from app.infrastructure.database import Base
from app.manage import claim_legacy
from app.modules.auth.models import User
from app.modules.auth.service import hasher, now_utc
from app.modules.settings.models import Settings


def test_legacy_records_require_explicit_owner_and_are_preserved(tmp_path, monkeypatch):
    url = os.getenv(
        "TEST_DATABASE_URL", "sqlite:///" + str(tmp_path / "legacy.db").replace("\\", "/")
    )
    monkeypatch.setattr(config, "DATABASE_URL", url)
    migration = Config("alembic.ini")
    command.upgrade(migration, "0001")
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO tasks (id,title,notes,priority,category,completed) VALUES ('11111111111111111111111111111111','Keep legacy','','normal','',false)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO settings (id,timezone,default_currency,enabled_modules) VALUES (1,'UTC','EUR','[]')"
            )
        )
    command.upgrade(migration, "0002")
    with pytest.raises(RuntimeError, match="Unowned legacy records"):
        command.upgrade(migration, "head")
    with Session(engine) as session:
        session.add(
            User(
                username="Chosen",
                normalized_username="chosen",
                password_hash=hasher.hash("test-passphrase-123"),
                created_at=now_utc(),
            )
        )
        session.commit()
        counts = claim_legacy(session, "CHOSEN")
        assert counts["tasks"] == counts["settings"] == 1
        assert session.scalar(text("SELECT count(*) FROM tasks WHERE user_id IS NULL")) == 1
        with pytest.raises(ValueError, match="does not exist"):
            claim_legacy(session, "missing-owner", True)
        claim_legacy(session, "Chosen", True)
    command.upgrade(migration, "head")
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT title FROM tasks")) == "Keep legacy"
        assert connection.scalar(text("SELECT default_currency FROM settings")) == "EUR"
        assert connection.scalar(text("SELECT count(*) FROM tasks WHERE user_id IS NULL")) == 0
    with Session(engine) as session:
        second = User(
            username="Second",
            normalized_username="second",
            password_hash=hasher.hash("test-passphrase-123"),
            created_at=now_utc(),
        )
        session.add(second)
        session.flush()
        session.add(Settings(user_id=second.id))
        session.commit()
        assert session.scalar(text("SELECT count(*) FROM settings")) == 2
    if os.getenv("TEST_DATABASE_URL"):
        Base.metadata.drop_all(engine)
        with engine.begin() as connection:
            connection.execute(text("DROP TABLE alembic_version"))
    engine.dispose()


def test_planning_migration_preserves_records_and_downgrades(tmp_path, monkeypatch):
    url = os.getenv(
        "TEST_DATABASE_URL", "sqlite:///" + str(tmp_path / "planning.db").replace("\\", "/")
    )
    monkeypatch.setattr(config, "DATABASE_URL", url)
    migration = Config("alembic.ini")
    command.upgrade(migration, "0003")
    engine = create_engine(url)
    user = "22222222222222222222222222222222"
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO users (id,username,normalized_username,password_hash,created_at) "
                f"VALUES ('{user}','Keeper','keeper','x','2026-01-01 00:00:00')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO tasks (id,user_id,title,notes,priority,category,completed) VALUES "
                f"('33333333333333333333333333333333','{user}','Kept task','','normal','',false)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO bills (id,user_id,name,amount,currency,due_date,paid) VALUES "
                f"('44444444444444444444444444444444','{user}','Kept bill',12.34,'USD','2026-11-30',false)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO settings (user_id,timezone,default_currency,enabled_modules) "
                f"VALUES ('{user}','UTC','EUR','[\"bills\"]')"
            )
        )
    command.upgrade(migration, "head")
    with engine.begin() as connection:
        assert connection.scalar(text("SELECT title FROM tasks")) == "Kept task"
        assert connection.scalar(text("SELECT series_id FROM tasks")) is None
        assert str(connection.scalar(text("SELECT amount FROM bills"))) == "12.34"
        modules = connection.scalar(text("SELECT enabled_modules FROM settings"))
        assert "meals" in modules and "budget" in modules and "bills" in modules
        connection.execute(
            text(
                "INSERT INTO task_series (id,user_id,title,notes,priority,category,frequency,"
                "repeat_interval,start_date,generated_through) VALUES ('55555555555555555555555555555555',"
                f"'{user}','Weekly','','normal','','weekly',1,'2026-11-02','2026-11-09')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO tasks (id,user_id,title,notes,priority,category,completed,series_id,"
                "occurrence_date,due_date) VALUES ('66666666666666666666666666666666',"
                f"'{user}','Weekly','','normal','',false,'55555555555555555555555555555555',"
                "'2026-11-02','2026-11-02')"
            )
        )
    command.downgrade(migration, "0003")
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM tasks")) == 2
        modules = connection.scalar(text("SELECT enabled_modules FROM settings"))
        # PostgreSQL returns parsed JSON; SQLite returns its text.
        assert (json.loads(modules) if isinstance(modules, str) else modules) == ["bills"]
    command.upgrade(migration, "head")
    if os.getenv("TEST_DATABASE_URL"):
        Base.metadata.drop_all(engine)
        with engine.begin() as connection:
            connection.execute(text("DROP TABLE alembic_version"))
    engine.dispose()
