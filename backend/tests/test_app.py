from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

import pytest
from sqlalchemy.orm import Session

from app.infrastructure.database import get_session
from app.main import app
from app.modules.dashboard.repository import DashboardRepository
from app.modules.dashboard.service import DashboardService
from app.modules.settings.repository import SettingsRepository
from app.modules.settings.service import SettingsService


def create(client, module, data):
    response = client.post("/api/" + module, json=data)
    assert response.status_code == 201, response.text
    return response.json()


def test_task_completion_persists_and_changes_dashboard(client):
    today = client.get("/api/dashboard").json()["today"]
    task = create(client, "tasks", {"title": "Submit essay", "due_date": today, "priority": "high"})
    assert client.get("/api/dashboard").json()["counts"]["tasks_today"] == 1
    task_id = task.pop("id")
    task["completed"] = True
    assert client.put("/api/tasks/" + task_id, json=task).status_code == 200
    assert client.get("/api/tasks/" + task_id).json()["completed"] is True
    assert client.get("/api/tasks?completed=false").json()["total"] == 0
    assert client.get("/api/tasks?completed=true").json()["total"] == 1
    assert client.get("/api/dashboard").json()["counts"]["tasks_today"] == 0
    assert client.delete("/api/tasks/" + task_id).status_code == 204
    assert client.get("/api/tasks/" + task_id).status_code == 404


def test_deadlines_and_timezone_boundaries(client):
    client.put("/api/settings", json={"timezone": "America/Los_Angeles"})
    dated = create(client, "tasks", {"title": "Date only", "due_date": "2026-10-02"})
    timed = create(client, "tasks", {"title": "Timed", "due_at": "2026-10-03T01:00:00Z"})
    tomorrow = create(client, "tasks", {"title": "Tomorrow", "due_at": "2026-10-03T08:00:00Z"})
    assert dated["due_date"] == "2026-10-02" and dated["due_at"] is None
    assert timed["due_date"] is None and timed["due_at"].endswith("Z")
    dependency = app.dependency_overrides[get_session]()
    session: Session = next(dependency)
    service = DashboardService(
        DashboardRepository(session, UUID(client.get("/api/auth/me").json()["user"]["id"])),
        SettingsService(
            SettingsRepository(session, UUID(client.get("/api/auth/me").json()["user"]["id"]))
        ),
    )
    summary = service.get(datetime(2026, 10, 3, 2, tzinfo=timezone.utc))
    assert summary["today"].isoformat() == "2026-10-02"
    assert summary["counts"]["tasks_today"] == 2
    assert summary["counts"]["tasks_overdue"] == 0
    dependency.close()
    assert tomorrow["due_at"].endswith("Z")
    assert (
        client.post(
            "/api/tasks",
            json={"title": "Invalid", "due_date": "2026-10-02", "due_at": timed["due_at"]},
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/tasks", json={"title": "Naive", "due_at": "2026-10-02T10:00:00"}
        ).status_code
        == 422
    )


def test_money_totals_are_exact_and_separated_by_currency(client):
    today = client.get("/api/dashboard").json()["today"]
    for amount in ["0.10", "0.20"]:
        create(client, "bills", {"name": "Small bill", "amount": amount, "due_date": today})
    paid = create(
        client, "bills", {"name": "Paid", "amount": "12.00", "due_date": today, "paid": True}
    )
    create(
        client, "bills", {"name": "Euro", "amount": "5.25", "currency": "EUR", "due_date": today}
    )
    totals = client.get("/api/dashboard").json()["bill_totals"]
    assert totals == {"EUR": "5.25", "USD": "0.30"}
    assert sum(
        Decimal(b["amount"])
        for b in client.get("/api/bills?paid=false").json()["items"]
        if b["currency"] == "USD"
    ) == Decimal("0.30")
    assert client.get("/api/bills?paid=true").json()["items"][0]["id"] == paid["id"]
    assert (
        client.post(
            "/api/bills", json={"name": "Bad precision", "amount": "1.001", "due_date": today}
        ).status_code
        == 422
    )


@pytest.mark.parametrize(
    "module,data,change",
    [
        (
            "calendar",
            {
                "title": "Study group",
                "start": "2026-10-02T14:00:00-04:00",
                "end": "2026-10-02T15:00:00-04:00",
            },
            {"title": "New study group"},
        ),
        ("groceries", {"name": "Apples", "quantity": "1.5", "unit": "kg"}, {"purchased": True}),
        (
            "bills",
            {"name": "Internet", "amount": "54.99", "due_date": "2026-10-08"},
            {"paid": True},
        ),
    ],
)
def test_feature_crud(client, module, data, change):
    item = create(client, module, data)
    record_id = item.pop("id")
    item.update(change)
    response = client.put(f"/api/{module}/{record_id}", json=item)
    assert response.status_code == 200, response.text
    assert client.get(f"/api/{module}/{record_id}").json().items() >= change.items()
    assert client.get(f"/api/{module}").json()["total"] == 1
    assert client.delete(f"/api/{module}/{record_id}").status_code == 204
    assert client.get(f"/api/{module}").json()["total"] == 0


def test_validation_and_error_shape(client):
    bad_inputs = [
        ("tasks", {"title": "  "}),
        ("tasks", {"title": "A", "priority": "urgent"}),
        ("groceries", {"name": "Rice", "quantity": "0"}),
        ("bills", {"name": "Rent", "amount": "-2", "due_date": "2026-10-01"}),
        (
            "calendar",
            {"title": "Invalid", "start": "2026-10-02T14:00:00Z", "end": "2026-10-02T13:00:00Z"},
        ),
        (
            "calendar",
            {
                "title": "Invalid day",
                "start": "2026-10-02T00:00:00Z",
                "end": "2026-10-03T00:00:00Z",
                "all_day": True,
            },
        ),
    ]
    for module, value in bad_inputs:
        response = client.post("/api/" + module, json=value)
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "validation"
    assert client.get("/api/tasks?limit=101").status_code == 422
    assert client.get("/api/tasks/not-a-uuid").status_code == 422
    assert client.get("/api/missing").json()["error"]["code"] == "http_error"


def test_settings_persist_and_do_not_delete_disabled_records(client):
    create(client, "tasks", {"title": "Keep this"})
    value = {"timezone": "Asia/Kolkata", "default_currency": "INR", "enabled_modules": ["bills"]}
    assert client.put("/api/settings", json=value).status_code == 200
    assert client.get("/api/settings").json() == value
    assert client.get("/api/tasks").json()["total"] == 1
    assert client.put("/api/settings", json={**value, "timezone": "Not/AZone"}).status_code == 422


def test_all_day_agenda_uses_date_not_utc_instant(client):
    create(
        client,
        "calendar",
        {
            "title": "Away",
            "start": "2026-10-01T22:00:00Z",
            "end": "2026-10-02T22:00:00Z",
            "all_day": True,
            "start_date": "2026-10-02",
            "end_date": "2026-10-03",
        },
    )
    client.put("/api/settings", json={"timezone": "America/Los_Angeles"})
    dependency = app.dependency_overrides[get_session]()
    session = next(dependency)
    service = DashboardService(
        DashboardRepository(session, UUID(client.get("/api/auth/me").json()["user"]["id"])),
        SettingsService(
            SettingsRepository(session, UUID(client.get("/api/auth/me").json()["user"]["id"]))
        ),
    )
    assert len(service.get(datetime(2026, 10, 2, 18, tzinfo=timezone.utc))["agenda"]) == 1
    assert len(service.get(datetime(2026, 10, 3, 18, tzinfo=timezone.utc))["agenda"]) == 0
    dependency.close()


def test_pagination_and_empty_dashboard(client):
    assert client.get("/api/dashboard").json()["counts"]["groceries_remaining"] == 0
    for i in range(4):
        create(client, "tasks", {"title": f"Task {i}"})
    first = client.get("/api/tasks?limit=2").json()
    second = client.get("/api/tasks?limit=2&offset=2").json()
    assert first["total"] == second["total"] == 4
    assert {i["id"] for i in first["items"]}.isdisjoint(i["id"] for i in second["items"])


def test_overdue_bills_and_30_day_horizon(client):
    from datetime import date

    today = date.fromisoformat(client.get("/api/dashboard").json()["today"])
    create(
        client,
        "bills",
        {"name": "Overdue", "amount": "1", "due_date": str(today - timedelta(days=1))},
    )
    create(
        client,
        "bills",
        {"name": "Later", "amount": "100", "due_date": str(today + timedelta(days=31))},
    )
    summary = client.get("/api/dashboard").json()
    assert summary["counts"]["bills_overdue"] == 1
    assert summary["bill_totals"] == {"USD": "1.00"}


def test_calendar_upcoming_and_past_filters(client):
    now = datetime.now(timezone.utc)
    create(
        client,
        "calendar",
        {
            "title": "Past",
            "start": (now - timedelta(days=2)).isoformat(),
            "end": (now - timedelta(days=1)).isoformat(),
        },
    )
    create(
        client,
        "calendar",
        {
            "title": "Ongoing",
            "start": (now - timedelta(hours=1)).isoformat(),
            "end": (now + timedelta(hours=1)).isoformat(),
        },
    )
    create(
        client,
        "calendar",
        {
            "title": "Future",
            "start": (now + timedelta(days=1)).isoformat(),
            "end": (now + timedelta(days=1, hours=1)).isoformat(),
        },
    )
    assert {e["title"] for e in client.get("/api/calendar?period=upcoming").json()["items"]} == {
        "Ongoing",
        "Future",
    }
    assert [e["title"] for e in client.get("/api/calendar?period=past").json()["items"]] == ["Past"]
    assert client.get("/api/calendar?period=invalid").status_code == 422


def test_dashboard_daylight_saving_day_is_not_fixed_24_hours(client):
    client.put("/api/settings", json={"timezone": "America/Los_Angeles"})
    create(client, "tasks", {"title": "Before local midnight", "due_at": "2026-03-09T06:30:00Z"})
    create(client, "tasks", {"title": "After local midnight", "due_at": "2026-03-09T07:30:00Z"})
    dependency = app.dependency_overrides[get_session]()
    session = next(dependency)
    service = DashboardService(
        DashboardRepository(session, UUID(client.get("/api/auth/me").json()["user"]["id"])),
        SettingsService(
            SettingsRepository(session, UUID(client.get("/api/auth/me").json()["user"]["id"]))
        ),
    )
    summary = service.get(datetime(2026, 3, 8, 18, tzinfo=timezone.utc))
    assert summary["today"].isoformat() == "2026-03-08"
    assert summary["counts"]["tasks_today"] == 1
    dependency.close()


def test_seed_idempotence_and_clear_preserve_personal_records(client, monkeypatch):
    from app import seed

    create(client, "tasks", {"title": "Personal record"})
    dependency = app.dependency_overrides[get_session]()
    session = next(dependency)
    monkeypatch.setattr(seed, "engine", session.get_bind())
    seed.seed("test-user")
    seed.seed("test-user")
    assert client.get("/api/tasks").json()["total"] == 4
    seed.seed("test-user", clear=True)
    assert client.get("/api/tasks").json()["items"][0]["title"] == "Personal record"
    assert client.get("/api/tasks").json()["total"] == 1
    assert client.get("/api/calendar").json()["total"] == 0
    assert client.get("/api/bills").json()["total"] == 0
    dependency.close()
