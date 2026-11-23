from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from conftest import authenticate
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.infrastructure.database import get_session
from app.main import app
from app.modules.budget.models import Expense
from app.modules.budget.service import summarize


def test_summary_math_is_per_currency_and_separates_unbudgeted_spending():
    budgets = [
        SimpleNamespace(
            id=uuid4(),
            category="Groceries",
            category_key="groceries",
            currency="USD",
            amount=Decimal("400"),
        ),
        SimpleNamespace(
            id=uuid4(),
            category="Dining",
            category_key="dining",
            currency="USD",
            amount=Decimal("100"),
        ),
        SimpleNamespace(
            id=uuid4(),
            category="Groceries",
            category_key="groceries",
            currency="EUR",
            amount=Decimal("50"),
        ),
    ]
    spending = [
        ("groceries", "USD", "groceries", Decimal("123.45")),
        ("dining", "USD", "Dining", Decimal("120.00")),
        ("gifts", "USD", "Gifts", Decimal("30.10")),
        ("groceries", "EUR", "Groceries", Decimal("10.00")),
    ]
    lines, totals = summarize(budgets, spending)
    by = {(line["category"], line["currency"]): line for line in lines}
    assert by[("Groceries", "USD")]["remaining"] == Decimal("276.55")
    assert by[("Dining", "USD")]["remaining"] == Decimal("-20.00")  # overspent stays visible
    assert by[("Gifts", "USD")]["budgeted"] is None and by[("Gifts", "USD")]["remaining"] is None
    usd, eur = totals[1], totals[0]
    assert eur == dict(
        currency="EUR",
        spent=Decimal("10.00"),
        budgeted=Decimal("50.00"),
        budgeted_spent=Decimal("10.00"),
        remaining=Decimal("40.00"),
        unbudgeted=Decimal("0.00"),
    )
    assert usd["spent"] == Decimal("273.55") and usd["budgeted"] == Decimal("500.00")
    assert usd["remaining"] == Decimal("256.55") and usd["unbudgeted"] == Decimal("30.10")


def month_of(client):
    today = date.fromisoformat(client.get("/api/dashboard").json()["today"])
    return today, today.strftime("%Y-%m")


def test_expenses_and_budgets_give_exact_monthly_totals(client):
    today, month = month_of(client)
    for amount in ["0.10", "0.20"]:
        assert (
            client.post(
                "/api/expenses",
                json={
                    "amount": amount,
                    "currency": "USD",
                    "category": "Coffee",
                    "spent_on": today.isoformat(),
                },
            ).status_code
            == 201
        )
    client.post(
        "/api/expenses",
        json={
            "amount": "3.00",
            "currency": "EUR",
            "category": " coffee ",
            "spent_on": today.isoformat(),
        },
    )
    last_month = today.replace(day=1) - timedelta(days=1)
    client.post(
        "/api/expenses",
        json={
            "amount": "99.00",
            "currency": "USD",
            "category": "Coffee",
            "spent_on": last_month.isoformat(),
        },
    )
    budget = client.post(
        "/api/budgets", json={"category": "COFFEE", "amount": "10.00", "currency": "USD"}
    )
    assert budget.status_code == 201
    duplicate = client.post(
        "/api/budgets", json={"category": "coffee", "amount": "5", "currency": "USD"}
    )
    assert duplicate.status_code == 409
    summary = client.get("/api/budget/summary", params={"month": month}).json()
    totals = {t["currency"]: t for t in summary["totals"]}
    assert totals["USD"]["spent"] == "0.30" and totals["USD"]["remaining"] == "9.70"
    assert totals["EUR"] == {
        "currency": "EUR",
        "spent": "3.00",
        "budgeted": "0.00",
        "budgeted_spent": "0.00",
        "remaining": "0.00",
        "unbudgeted": "3.00",
    }
    lines = {(line["category"], line["currency"]) for line in summary["categories"]}
    assert lines == {("COFFEE", "USD"), ("coffee", "EUR")}
    assert client.get("/api/expenses", params={"month": month}).json()["total"] == 3
    for bad in [{"amount": "0"}, {"amount": "1.001"}, {"currency": "usd"}, {"category": ""}]:
        body = {
            "amount": "1",
            "currency": "USD",
            "category": "x",
            "spent_on": today.isoformat(),
            **bad,
        }
        assert client.post("/api/expenses", json=body).status_code == 422
    assert client.get("/api/budget/summary", params={"month": "2026-13"}).status_code == 422


def test_paying_a_bill_records_one_linked_expense_without_double_counting(client):
    today, month = month_of(client)
    bill = client.post(
        "/api/bills", json={"name": "Internet", "amount": "54.99", "due_date": today.isoformat()}
    ).json()
    before = client.get("/api/budget/summary", params={"month": month}).json()
    assert before["expected_bills"] == [{"currency": "USD", "amount": "54.99", "count": 1}]
    assert before["totals"] == []  # expected payments are not spending
    pay = {"paid_on": today.isoformat(), "category": "Utilities"}
    first = client.post(f"/api/bills/{bill['id']}/pay", json=pay)
    second = client.post(f"/api/bills/{bill['id']}/pay", json=pay)
    assert first.status_code == second.status_code == 200
    assert first.json()["expense_id"] == second.json()["expense_id"] is not None
    expenses = client.get("/api/expenses").json()
    assert expenses["total"] == 1 and expenses["items"][0]["bill_id"] == bill["id"]
    after = client.get("/api/budget/summary", params={"month": month}).json()
    assert after["expected_bills"] == []
    assert after["totals"][0]["spent"] == "54.99"
    # Unpaying while the expense exists would count the bill as both spent and owed.
    paid_bill = first.json()
    paid_bill.pop("id")
    conflict = client.put(f"/api/bills/{bill['id']}", json={**paid_bill, "paid": False})
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "conflict"
    # Deleting the expense keeps the bill paid; it can then be unpaid explicitly.
    expense_id = expenses["items"][0]["id"]
    assert client.delete(f"/api/expenses/{expense_id}").status_code == 204
    assert client.get(f"/api/bills/{bill['id']}").json()["paid"] is True
    assert (
        client.put(f"/api/bills/{bill['id']}", json={**paid_bill, "paid": False}).status_code == 200
    )


def test_paying_without_recording_and_deleting_a_paid_bill(client):
    today, month = month_of(client)
    quiet = client.post(
        "/api/bills", json={"name": "Gym", "amount": "20.00", "due_date": today.isoformat()}
    ).json()
    response = client.post(
        f"/api/bills/{quiet['id']}/pay",
        json={"paid_on": today.isoformat(), "record_expense": False},
    )
    assert response.json()["paid"] is True and response.json()["expense_id"] is None
    bill = client.post(
        "/api/bills", json={"name": "Water", "amount": "15.00", "due_date": today.isoformat()}
    ).json()
    client.post(f"/api/bills/{bill['id']}/pay", json={"paid_on": today.isoformat()})
    assert client.delete(f"/api/bills/{bill['id']}").status_code == 204
    kept = client.get("/api/expenses").json()["items"]
    assert len(kept) == 1 and kept[0]["bill_id"] is None and kept[0]["amount"] == "15.00"
    summary = client.get("/api/budget/summary", params={"month": month}).json()
    assert summary["totals"][0]["spent"] == "15.00" and summary["expected_bills"] == []


def test_budget_records_are_isolated_between_accounts(raw_client):
    authenticate(raw_client, "Alice")
    today, month = month_of(raw_client)
    expense = raw_client.post(
        "/api/expenses",
        json={
            "amount": "8.00",
            "currency": "USD",
            "category": "Books",
            "spent_on": today.isoformat(),
        },
    ).json()
    budget = raw_client.post(
        "/api/budgets", json={"category": "Books", "amount": "20", "currency": "USD"}
    ).json()
    bill = raw_client.post(
        "/api/bills", json={"name": "Alice bill", "amount": "5.00", "due_date": today.isoformat()}
    ).json()
    with TestClient(app) as bob:
        authenticate(bob, "Bob")
        assert bob.get("/api/expenses").json()["total"] == 0
        assert bob.get("/api/budgets").json() == []
        assert bob.get(f"/api/expenses/{expense['id']}").status_code == 404
        echo = {k: expense[k] for k in ("amount", "currency", "category", "spent_on")}
        assert bob.put(f"/api/expenses/{expense['id']}", json=echo).status_code == 404
        assert bob.delete(f"/api/expenses/{expense['id']}").status_code == 404
        assert bob.delete(f"/api/budgets/{budget['id']}").status_code == 404
        # A supplied bill_id is ignored, never used to link another account's bill.
        forged = bob.post("/api/expenses", json={**echo, "bill_id": bill["id"]})
        assert forged.status_code == 201 and forged.json()["bill_id"] is None
        summary = bob.get("/api/budget/summary", params={"month": month}).json()
        assert summary["expected_bills"] == []
        # Only Bob's own expense appears, and Alice's "Books" budget is not applied to it.
        assert [(c["spent"], c["budget_id"]) for c in summary["categories"]] == [("8.00", None)]
        bob_id = UUID(bob.get("/api/auth/me").json()["user"]["id"])
    assert (
        raw_client.get("/api/budget/summary", params={"month": month}).json()["totals"][0]["spent"]
        == "8.00"
    )
    dependency = app.dependency_overrides[get_session]()
    session = next(dependency)
    session.add(
        Expense(
            user_id=bob_id,
            amount=Decimal(1),
            currency="USD",
            category="x",
            category_key="x",
            spent_on=today,
            note="",
            bill_id=UUID(bill["id"]),
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()
    dependency.close()


def test_dashboard_composes_meals_spending_and_recurring_items(client):
    today, _ = month_of(client)
    empty = client.get("/api/dashboard").json()
    assert empty["meals_today"] == [] and empty["recurring"] == []
    assert empty["spending"]["totals"] == [] and empty["spending"]["expected_bills"] == []
    recipe = client.post("/api/recipes", json={"name": "Soup", "servings": 2}).json()
    client.post(
        "/api/meal-plan",
        json={
            "plan_date": today.isoformat(),
            "meal": "dinner",
            "recipe_id": recipe["id"],
            "servings": 2,
        },
    )
    client.post(
        "/api/bill-series",
        json={
            "name": "Rent",
            "amount": "900.00",
            "frequency": "monthly",
            "start_date": today.isoformat(),
        },
    )
    client.post(
        "/api/task-series",
        json={"title": "Laundry", "frequency": "weekly", "start_date": today.isoformat()},
    )
    client.post(
        "/api/expenses",
        json={
            "amount": "12.00",
            "currency": "EUR",
            "category": "Food",
            "spent_on": today.isoformat(),
        },
    )
    summary = client.get("/api/dashboard").json()
    assert [m["recipe_name"] for m in summary["meals_today"]] == ["Soup"]
    recurring = [(r["kind"], r["title"], r["due_date"]) for r in summary["recurring"]]
    next_week = (today + timedelta(days=7)).isoformat()
    assert recurring == [
        ("bill", "Rent", today.isoformat()),
        ("task", "Laundry", today.isoformat()),
        ("task", "Laundry", next_week),
    ]
    assert not any(r["overdue"] for r in summary["recurring"])
    # Next steps show today's occurrence only; later ones stay under recurring items.
    assert [t["due_date"] for t in summary["tasks"]] == [today.isoformat()]
    assert summary["spending"]["totals"][0]["currency"] == "EUR"
    assert summary["spending"]["expected_bills"][0] == {
        "currency": "USD",
        "amount": "900.00",
        "count": 1,
    }
    # Spending in EUR and owed USD rent are never combined into one figure.
    assert len(summary["spending"]["totals"]) == 1
