from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from uuid import UUID

import pytest
from conftest import authenticate
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from app.infrastructure.database import get_session
from app.main import app
from app.modules.bills.models import Bill
from app.modules.bills.repository import BillSeriesRepository
from app.modules.bills.schemas import BillSeriesInput
from app.modules.recurrence.rules import HORIZON_DAYS
from app.modules.recurrence.service import RecurrenceService
from app.modules.settings.repository import SettingsRepository
from app.modules.settings.service import SettingsService
from app.modules.tasks.models import Task, TaskSeries
from app.modules.tasks.repository import TaskSeriesRepository
from app.modules.tasks.schemas import TaskSeriesInput

DAY = timedelta(days=1)


@contextmanager
def recurrence(client, kind="task"):
    user_id = UUID(client.get("/api/auth/me").json()["user"]["id"])
    dependency = app.dependency_overrides[get_session]()
    session = next(dependency)
    repository = (TaskSeriesRepository if kind == "task" else BillSeriesRepository)(
        session, user_id
    )
    try:
        yield (
            session,
            RecurrenceService(repository, SettingsService(SettingsRepository(session, user_id))),
        )
    finally:
        dependency.close()


def today_of(client):
    return date.fromisoformat(client.get("/api/dashboard").json()["today"])


def all_tasks(client, **params):
    response = client.get("/api/tasks", params={"limit": 100, **params})
    assert response.status_code == 200, response.text
    return response.json()


def test_generation_is_idempotent_and_bounded_by_horizon(client):
    today = today_of(client)
    created = client.post(
        "/api/task-series",
        json={"title": "Water plants", "frequency": "daily", "start_date": today.isoformat()},
    )
    assert created.status_code == 201, created.text
    first = all_tasks(client)
    assert first["total"] == HORIZON_DAYS + 1
    assert all_tasks(client)["total"] == first["total"]
    assert client.get("/api/dashboard").status_code == 200
    # Simulate a lost generated_through marker (or a concurrent generator): the unique
    # (series_id, occurrence_date) key still prevents duplicates.
    with recurrence(client) as (session, service):
        session.execute(update(TaskSeries).values(generated_through=today - DAY))
        session.commit()
        service.ensure(today)
        service.ensure(today)
        dates = session.scalars(
            select(Task.occurrence_date).where(Task.series_id == UUID(created.json()["id"]))
        ).all()
    assert len(dates) == len(set(dates)) == HORIZON_DAYS + 1
    assert min(dates) == today and max(dates) == today + timedelta(days=HORIZON_DAYS)


def test_completing_or_deleting_one_occurrence_leaves_the_others(client):
    today = today_of(client)
    series = client.post(
        "/api/task-series",
        json={"title": "Review", "frequency": "weekly", "start_date": today.isoformat()},
    ).json()
    items = all_tasks(client)["items"]
    assert [item["due_date"] for item in items] == [
        (today + timedelta(weeks=n)).isoformat() for n in range(7)
    ]
    assert {item["series_id"] for item in items} == {series["id"]}
    first, second = items[0], items[1]
    first_id = first.pop("id")
    response = client.put(f"/api/tasks/{first_id}", json={**first, "completed": True})
    assert response.status_code == 200, response.text
    # Echoed read-only fields cannot move a record to another series.
    assert response.json()["series_id"] == series["id"]
    assert all_tasks(client, completed="true")["total"] == 1
    assert all_tasks(client, completed="false")["total"] == 6
    assert client.delete(f"/api/tasks/{second['id']}").status_code == 204
    assert all_tasks(client)["total"] == 6  # Not regenerated after deletion.
    # Editing only this occurrence changes nothing else.
    third = all_tasks(client, completed="false")["items"][0]
    third_id = third.pop("id")
    client.put(f"/api/tasks/{third_id}", json={**third, "title": "Just this once"})
    titles = [item["title"] for item in all_tasks(client)["items"]]
    assert titles.count("Just this once") == 1 and titles.count("Review") == 5


def test_this_and_future_edit_splits_series_without_duplicates(client):
    today = today_of(client)
    start = today - timedelta(weeks=2)
    with recurrence(client) as (session, service):
        # Created two weeks ago: two overdue occurrences exist now.
        old = service.create(
            TaskSeriesInput(title="Old", frequency="weekly", start_date=start), today=start
        )
        service.ensure(today)
        rows = {
            t.occurrence_date: t
            for t in session.scalars(select(Task).where(Task.series_id == old.id)).all()
        }
        rows[start].completed = True  # done on time
        rows[today + timedelta(weeks=1)].completed = True  # done early
        session.commit()
        cut = start + timedelta(weeks=1)  # an overdue, still-open occurrence
        target = service.update_future(
            rows[cut].id,
            TaskSeriesInput(title="New", frequency="weekly", start_date=cut, priority="high"),
            today=today,
        )
        session.expire_all()
        old = session.get(TaskSeries, old.id)
        assert old.until_date == cut - DAY and target.id != old.id
        tasks = session.scalars(select(Task).order_by(Task.occurrence_date)).all()
    by_date = {t.occurrence_date: t for t in tasks}
    assert len(by_date) == len(tasks)  # one row per scheduled date
    assert by_date[start].title == "Old" and by_date[start].series_id == old.id
    assert by_date[cut].title == "New" and by_date[cut].due_date == cut  # overdue kept
    assert by_date[cut].series_id == target.id and by_date[cut].priority == "high"
    early = by_date[today + timedelta(weeks=1)]
    assert early.completed and early.title == "Old" and early.series_id == target.id
    upcoming = [t for d, t in by_date.items() if d >= today and not t.completed]
    assert upcoming and all(t.title == "New" and t.series_id == target.id for t in upcoming)


def test_editing_the_first_occurrence_updates_the_series_in_place(client):
    today = today_of(client)
    series = client.post(
        "/api/bill-series",
        json={
            "name": "Rent",
            "amount": "1200.00",
            "frequency": "monthly",
            "start_date": today.isoformat(),
        },
    ).json()
    first = client.get("/api/bills").json()["items"][0]
    response = client.put(
        f"/api/bills/{first['id']}/future",
        json={
            "name": "Rent",
            "amount": "1250.00",
            "frequency": "monthly",
            "start_date": today.isoformat(),
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["id"] == series["id"]
    bills = client.get("/api/bills").json()["items"]
    assert bills and {b["amount"] for b in bills} == {"1250.00"}
    assert len({b["occurrence_date"] for b in bills}) == len(bills)
    # A non-repeating record has no future to edit.
    single = client.post(
        "/api/bills", json={"name": "Once", "amount": "5.00", "due_date": today.isoformat()}
    ).json()
    future = client.put(
        f"/api/bills/{single['id']}/future",
        json={"name": "x", "amount": "1.00", "frequency": "daily", "start_date": today.isoformat()},
    )
    assert future.status_code == 409


def test_month_end_bills_and_independent_payment(client):
    anchor = date(2026, 10, 31)
    with recurrence(client, "bill") as (session, service):
        series = service.create(
            BillSeriesInput(name="Card", amount="40.00", frequency="monthly", start_date=anchor),
            today=anchor,
        )
        service.ensure(date(2027, 1, 25))
        service.ensure(date(2027, 1, 25))
        dates = session.scalars(
            select(Bill.due_date).where(Bill.series_id == series.id).order_by(Bill.due_date)
        ).all()
    assert dates == [
        date(2026, 10, 31),
        date(2026, 11, 30),
        date(2026, 12, 31),
        date(2027, 1, 31),
        date(2027, 2, 28),
    ]


def test_paying_one_bill_occurrence_does_not_pay_the_next(client):
    today = today_of(client)
    client.post(
        "/api/bill-series",
        json={
            "name": "Phone",
            "amount": "30.00",
            "frequency": "weekly",
            "start_date": today.isoformat(),
        },
    )
    bills = client.get("/api/bills").json()["items"]
    paid = client.post(f"/api/bills/{bills[0]['id']}/pay", json={"paid_on": today.isoformat()})
    assert paid.status_code == 200 and paid.json()["paid"] is True
    assert paid.json()["expense_id"]
    states = [b["paid"] for b in client.get("/api/bills").json()["items"]]
    assert states.count(True) == 1 and len(states) == 7


def test_stopping_a_series_keeps_history_and_overdue_items(client):
    today = today_of(client)
    start = today - timedelta(days=3)
    with recurrence(client) as (session, service):
        series = service.create(
            TaskSeriesInput(title="Stretch", frequency="daily", start_date=start), today=start
        )
        service.ensure(today)
        done = session.scalar(select(Task).where(Task.occurrence_date == start))
        done.completed = True
        session.commit()
        series_id = series.id
    assert client.delete(f"/api/task-series/{series_id}").status_code == 204
    remaining = all_tasks(client)["items"]
    assert sorted(t["due_date"] for t in remaining) == [
        (start + timedelta(days=n)).isoformat() for n in range(3)
    ]
    assert all(t["series_id"] is None for t in remaining)
    assert client.get(f"/api/task-series/{series_id}").status_code == 404
    assert all_tasks(client)["total"] == 3  # nothing regenerates


def test_today_follows_profile_timezone_and_past_dates_are_not_backfilled(client):
    instant = datetime(2026, 11, 23, 12, tzinfo=timezone.utc)
    client.put("/api/settings", json={"timezone": "Pacific/Kiritimati"})  # UTC+14
    with recurrence(client) as (_, service):
        ahead = service.today(instant)
        series = service.create(
            TaskSeriesInput(title="Journal", frequency="daily", start_date=date(2026, 11, 23)),
            today=ahead,
        )
        assert series.start_date == date(2026, 11, 23)
    client.put("/api/settings", json={"timezone": "Pacific/Pago_Pago"})  # UTC-11
    with recurrence(client) as (_, service):
        assert service.today(instant) == date(2026, 11, 23)
    assert ahead == date(2026, 11, 24)
    # Changing timezone never shifts stored occurrence dates.
    dates = [t["occurrence_date"] for t in all_tasks(client)["items"]]
    assert "2026-11-23" not in dates and "2026-11-24" in dates


def test_validation_of_series_inputs(client):
    base = {"title": "x", "frequency": "monthly", "start_date": "2026-11-01"}
    for bad in [
        {"frequency": "yearly"},
        {"interval": 0},
        {"until_date": "2026-10-31"},
        {"user_id": "11111111-1111-1111-1111-111111111111"},
    ]:
        assert client.post("/api/task-series", json={**base, **bad}).status_code == 422


def test_series_are_isolated_between_accounts(raw_client):
    authenticate(raw_client, "Alice")
    today = today_of(raw_client)
    body = {"title": "Alice chore", "frequency": "daily", "start_date": today.isoformat()}
    series = raw_client.post("/api/task-series", json=body).json()
    bill_series = raw_client.post(
        "/api/bill-series",
        json={
            "name": "Alice rent",
            "amount": "9.00",
            "frequency": "monthly",
            "start_date": today.isoformat(),
        },
    ).json()
    occurrence = all_tasks(raw_client)["items"][0]
    bill = raw_client.get("/api/bills").json()["items"][0]
    with TestClient(app) as bob:
        authenticate(bob, "Bob")
        assert all_tasks(bob)["total"] == 0 and bob.get("/api/bills").json()["total"] == 0
        assert bob.get(f"/api/task-series/{series['id']}").status_code == 404
        assert bob.get(f"/api/bill-series/{bill_series['id']}").status_code == 404
        assert bob.delete(f"/api/task-series/{series['id']}").status_code == 404
        assert bob.put(f"/api/tasks/{occurrence['id']}/future", json=body).status_code == 404
        assert (
            bob.post(
                f"/api/bills/{bill['id']}/pay", json={"paid_on": today.isoformat()}
            ).status_code
            == 404
        )
        bob_id = UUID(bob.get("/api/auth/me").json()["user"]["id"])
    assert all_tasks(raw_client)["total"] == HORIZON_DAYS + 1
    # The database itself rejects an occurrence owned by someone other than its series owner.
    dependency = app.dependency_overrides[get_session]()
    session = next(dependency)
    session.add(
        Task(
            title="Forged",
            user_id=bob_id,
            series_id=UUID(series["id"]),
            occurrence_date=today + timedelta(days=500),
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()
    dependency.close()
