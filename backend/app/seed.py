"""Explicit, repeatable sample data; --clear removes only known sample UUIDs."""

import argparse
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal
from uuid import NAMESPACE_URL, uuid5
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.infrastructure.database import engine
from app.modules.auth.models import User
from app.modules.auth.service import normalize_username
from app.modules.bills.models import Bill
from app.modules.calendar.models import CalendarEntry
from app.modules.groceries.models import Grocery
from app.modules.settings.repository import SettingsRepository
from app.modules.settings.service import SettingsService
from app.modules.tasks.models import Task


def seed(owner, clear=False):
    with Session(engine) as session, session.begin():
        user = session.scalar(
            select(User).where(User.normalized_username == normalize_username(owner))
        )
        if not user:
            raise ValueError("Designated demo account does not exist. Create it explicitly first.")
        settings = SettingsService(SettingsRepository(session, user.id)).get()
        zone = ZoneInfo(settings.timezone)
        today = datetime.now(zone).date()

        def instant(days, hour):
            return datetime.combine(today + timedelta(days=days), time(hour), zone).astimezone(
                timezone.utc
            )

        records = [
            (
                Task,
                "essay",
                dict(
                    title="Finish the first draft",
                    notes="A little progress is enough.",
                    due_date=today,
                    priority="high",
                    category="School",
                    completed=False,
                ),
            ),
            (
                Task,
                "library",
                dict(
                    title="Return library books",
                    due_date=today - timedelta(days=1),
                    priority="normal",
                    category="Errands",
                    completed=False,
                ),
            ),
            (
                Task,
                "walk",
                dict(
                    title="Make time for a walk",
                    priority="low",
                    category="Personal",
                    completed=False,
                ),
            ),
            (
                CalendarEntry,
                "study",
                dict(
                    title="Study group",
                    description="Bring notes for the next chapter.",
                    start=instant(0, 10),
                    end=instant(0, 11),
                    all_day=False,
                ),
            ),
            (
                CalendarEntry,
                "lunch",
                dict(
                    title="Lunch with Alex",
                    description="A catch-up at the café.",
                    start=instant(0, 13),
                    end=instant(0, 14),
                    all_day=False,
                ),
            ),
            (
                CalendarEntry,
                "dentist",
                dict(
                    title="Dentist appointment",
                    description="Remember your insurance card.",
                    start=instant(2, 9),
                    end=instant(2, 10),
                    all_day=False,
                ),
            ),
            (
                Grocery,
                "apples",
                dict(
                    name="Apples",
                    quantity=Decimal("6"),
                    unit="pieces",
                    category="Produce",
                    purchased=False,
                ),
            ),
            (
                Grocery,
                "oats",
                dict(
                    name="Rolled oats",
                    quantity=Decimal("1"),
                    unit="bag",
                    category="Pantry",
                    purchased=False,
                ),
            ),
            (
                Grocery,
                "milk",
                dict(
                    name="Oat milk",
                    quantity=Decimal("2"),
                    unit="cartons",
                    category="Fridge",
                    purchased=False,
                ),
            ),
            (
                Bill,
                "internet",
                dict(
                    name="Internet",
                    amount=Decimal("54.99"),
                    currency=settings.default_currency,
                    due_date=today + timedelta(days=3),
                    paid=False,
                ),
            ),
            (
                Bill,
                "electricity",
                dict(
                    name="Electricity",
                    amount=Decimal("42.80"),
                    currency=settings.default_currency,
                    due_date=today - timedelta(days=2),
                    paid=False,
                ),
            ),
        ]
        changed = 0
        for model, key, values in records:
            record_id = uuid5(
                NAMESPACE_URL,
                "daybook:sample:" + str(user.id) + ":" + model.__tablename__ + ":" + key,
            )
            if clear:
                result = session.execute(
                    delete(model).where(model.id == record_id, model.user_id == user.id)
                )
                changed += result.rowcount
            elif session.get(model, record_id) is None:
                session.add(model(id=record_id, user_id=user.id, **values))
                changed += 1
    print(f"{'Removed' if clear else 'Added'} {changed} sample records.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--clear", action="store_true", help="Remove only the deterministic sample records."
    )
    parser.add_argument("--owner", required=True, help="Existing designated demo username.")
    args = parser.parse_args()
    seed(args.owner, args.clear)
