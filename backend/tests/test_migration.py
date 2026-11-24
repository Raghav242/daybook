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
    command.upgrade(migration, "0004")
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


def test_category_migration_merges_equivalent_text_and_downgrades(tmp_path, monkeypatch):
    url = os.getenv(
        "TEST_DATABASE_URL", "sqlite:///" + str(tmp_path / "categories.db").replace("\\", "/")
    )
    monkeypatch.setattr(config, "DATABASE_URL", url)
    migration = Config("alembic.ini")
    command.upgrade(migration, "0004")
    engine = create_engine(url)
    alice, bob = "a" * 32, "b" * 32
    rows = {
        "users": [
            f"('{alice}','Alice','alice','x','2026-01-01 00:00:00')",
            f"('{bob}','Bob','bob','x','2026-01-01 00:00:00')",
        ],
        "tasks": [
            f"('{'1' * 32}','{alice}','Essay','','normal','School',false)",
            f"('{'2' * 32}','{alice}','Notes','','normal',' school ',false)",
            f"('{'3' * 32}','{alice}','Walk','','normal','',false)",
            f"('{'4' * 32}','{bob}','Report','','normal','school',false)",
            f"('{'5' * 32}','{alice}','Tidy','','normal','home',false)",
        ],
        "groceries": [f"('{'6' * 32}','{alice}','Milk',1,'l','Fridge',false)"],
        "expenses": [
            f"('{'7' * 32}','{alice}',12.50,'USD','Coffee','coffee','2026-11-02','')",
            f"('{'8' * 32}','{alice}',3.00,'USD','COFFEE','coffee','2026-11-03','')",
            f"('{'9' * 32}','{alice}',40.00,'USD','groceries','groceries','2026-11-04','')",
        ],
        "budgets": [f"('{'c' * 32}','{alice}','coffee','coffee',20.00,'USD')"],
    }
    columns = {
        "users": "id,username,normalized_username,password_hash,created_at",
        "tasks": "id,user_id,title,notes,priority,category,completed",
        "groceries": "id,user_id,name,quantity,unit,category,purchased",
        "expenses": "id,user_id,amount,currency,category,category_key,spent_on,note",
        "budgets": "id,user_id,category,category_key,amount,currency",
    }
    with engine.begin() as connection:
        for table, values in rows.items():
            connection.execute(
                text(f"INSERT INTO {table} ({columns[table]}) VALUES {','.join(values)}")
            )
    command.upgrade(migration, "0005")

    def names(connection, table, owner=alice):
        return dict(
            connection.execute(
                text(
                    f"SELECT t.id, c.name FROM {table} t LEFT JOIN categories c "
                    f"ON c.id = t.category_id WHERE t.user_id = '{owner}'"
                )
            ).all()
        )

    def ids(value):
        return value.replace("-", "")

    with engine.connect() as connection:
        tasks = {ids(str(k)): v for k, v in names(connection, "tasks").items()}
        # Case/spacing variants merge into one category, named by the commonest spelling.
        assert tasks["1" * 32] == tasks["2" * 32] == "School"
        assert tasks["3" * 32] is None  # an empty category stays empty
        assert (
            tasks["5" * 32] == "Home"
        )  # equivalent to a starting category: joined, not duplicated
        expenses = set(names(connection, "expenses").values())
        assert expenses == {"Coffee", "Groceries"}
        assert set(names(connection, "budgets").values()) == {"Coffee"}
        # Budgets and expenses reference the very same expense category.
        assert (
            connection.scalar(
                text(
                    "SELECT count(DISTINCT e.category_id) FROM expenses e JOIN budgets b "
                    "ON b.category_id = e.category_id"
                )
            )
            == 1
        )
        assert set(names(connection, "groceries").values()) == {"Fridge"}
        # Every account gets its own starting lists; Bob's "school" is his own category.
        assert set(names(connection, "tasks", bob).values()) == {"school"}
        per_user = connection.execute(
            text("SELECT user_id, count(*) FROM categories WHERE scope = 'income' GROUP BY user_id")
        ).all()
        assert sorted(count for _, count in per_user) == [6, 6]
        assert connection.scalar(text("SELECT count(*) FROM tasks")) == 5
    command.downgrade(migration, "0004")
    with engine.connect() as connection:
        restored = dict(connection.execute(text("SELECT title, category FROM tasks")).all())
        assert restored == {
            "Essay": "School",
            "Notes": "School",
            "Walk": "",
            "Report": "school",
            "Tidy": "Home",
        }
        assert sorted(
            connection.execute(text("SELECT category, category_key FROM expenses")).all()
        ) == [("Coffee", "coffee"), ("Coffee", "coffee"), ("Groceries", "groceries")]
        assert connection.execute(text("SELECT category, amount FROM budgets")).all()[0][0] == (
            "Coffee"
        )
    command.upgrade(migration, "head")
    if os.getenv("TEST_DATABASE_URL"):
        Base.metadata.drop_all(engine)
        with engine.begin() as connection:
            connection.execute(text("DROP TABLE alembic_version"))
    engine.dispose()
