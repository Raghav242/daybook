from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from conftest import authenticate, category_id
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.infrastructure.database import get_session
from app.main import app
from app.modules.budget.models import Expense
from app.modules.budget.service import summarize


def test_summary_math_is_per_currency_and_separates_unbudgeted_spending():
    groceries, dining, gifts = uuid4(), uuid4(), uuid4()
    budgets = [
        SimpleNamespace(
            id=uuid4(),
            category_id=groceries,
            category="Groceries",
            currency="USD",
            amount=Decimal("400"),
        ),
        SimpleNamespace(
            id=uuid4(), category_id=dining, category="Dining", currency="USD", amount=Decimal("100")
        ),
        SimpleNamespace(
            id=uuid4(),
            category_id=groceries,
            category="Groceries",
            currency="EUR",
            amount=Decimal("50"),
        ),
    ]
    spending = [
        (groceries, "USD", "Groceries", Decimal("123.45")),
        (dining, "USD", "Dining", Decimal("120.00")),
        (gifts, "USD", "Gifts", Decimal("30.10")),
        (groceries, "EUR", "Groceries", Decimal("10.00")),
    ]
    income = [("USD", Decimal("1000.00")), ("INR", Decimal("500"))]
    lines, totals = summarize(budgets, spending, income)
    by = {(line["category"], line["currency"]): line for line in lines}
    assert by[("Groceries", "USD")]["remaining"] == Decimal("276.55")
    assert by[("Dining", "USD")]["remaining"] == Decimal("-20.00")  # overspent stays visible
    assert by[("Gifts", "USD")]["budgeted"] is None and by[("Gifts", "USD")]["remaining"] is None
    eur, inr, usd = totals
    assert eur == dict(
        currency="EUR",
        income=Decimal("0.00"),
        spent=Decimal("10.00"),
        net=Decimal("-10.00"),
        budgeted=Decimal("50.00"),
        budgeted_spent=Decimal("10.00"),
        remaining=Decimal("40.00"),
        unbudgeted=Decimal("0.00"),
    )
    # Income in a currency with no spending still gets its own line; nothing is converted.
    assert inr["income"] == Decimal("500.00") and inr["spent"] == Decimal("0.00")
    assert inr["net"] == Decimal("500.00")
    assert usd["spent"] == Decimal("273.55") and usd["budgeted"] == Decimal("500.00")
    assert usd["remaining"] == Decimal("256.55") and usd["unbudgeted"] == Decimal("30.10")
    # Income never reduces reported spending or changes a budget.
    assert usd["income"] == Decimal("1000.00") and usd["net"] == Decimal("726.45")


def month_of(client):
    today = date.fromisoformat(client.get("/api/dashboard").json()["today"])
    return today, today.strftime("%Y-%m")


def expense(client, amount, currency, category, day, **extra):
    response = client.post(
        "/api/expenses",
        json={
            "amount": amount,
            "currency": currency,
            "category_id": category,
            "spent_on": day.isoformat(),
            **extra,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_expenses_and_budgets_give_exact_monthly_totals(client):
    today, month = month_of(client)
    coffee = category_id(client, "expense", "Coffee")
    assert category_id(client, "expense", " coffee ") == coffee  # one category, not two
    for amount in ["0.10", "0.20"]:
        expense(client, amount, "USD", coffee, today)
    expense(client, "3.00", "EUR", coffee, today)
    last_month = today.replace(day=1) - timedelta(days=1)
    expense(client, "99.00", "USD", coffee, last_month)
    budget = client.post(
        "/api/budgets", json={"category_id": coffee, "amount": "10.00", "currency": "USD"}
    )
    assert budget.status_code == 201 and budget.json()["category"] == "Coffee"
    duplicate = client.post(
        "/api/budgets", json={"category_id": coffee, "amount": "5", "currency": "USD"}
    )
    assert duplicate.status_code == 409
    summary = client.get("/api/budget/summary", params={"month": month}).json()
    totals = {t["currency"]: t for t in summary["totals"]}
    assert totals["USD"]["spent"] == "0.30" and totals["USD"]["remaining"] == "9.70"
    assert totals["EUR"] == {
        "currency": "EUR",
        "income": "0.00",
        "spent": "3.00",
        "net": "-3.00",
        "budgeted": "0.00",
        "budgeted_spent": "0.00",
        "remaining": "0.00",
        "unbudgeted": "3.00",
    }
    lines = {(line["category"], line["currency"]) for line in summary["categories"]}
    assert lines == {("Coffee", "USD"), ("Coffee", "EUR")}
    assert client.get("/api/expenses", params={"month": month}).json()["total"] == 3
    for bad in [
        {"amount": "0"},
        {"amount": "1.001"},
        {"currency": "usd"},
        {"category_id": None},
        {"category_id": str(uuid4())},
        {"category_id": category_id(client, "income", "Salary")},  # wrong scope
    ]:
        body = {
            "amount": "1",
            "currency": "USD",
            "category_id": coffee,
            "spent_on": today.isoformat(),
            **bad,
        }
        assert client.post("/api/expenses", json=body).status_code == 422, bad
    assert client.get("/api/budget/summary", params={"month": "2026-13"}).status_code == 422


def test_paying_a_bill_records_one_linked_expense_without_double_counting(client):
    today, month = month_of(client)
    utilities = category_id(client, "expense", "Utilities")
    bill = client.post(
        "/api/bills", json={"name": "Internet", "amount": "54.99", "due_date": today.isoformat()}
    ).json()
    before = client.get("/api/budget/summary", params={"month": month}).json()
    assert before["expected_bills"] == [{"currency": "USD", "amount": "54.99", "count": 1}]
    assert before["totals"] == []  # expected payments are not spending
    # Recording the payment needs an expense category; nothing is guessed.
    missing = client.post(f"/api/bills/{bill['id']}/pay", json={"paid_on": today.isoformat()})
    assert missing.status_code == 422
    assert client.get(f"/api/bills/{bill['id']}").json()["paid"] is False
    pay = {"paid_on": today.isoformat(), "category_id": utilities}
    first = client.post(f"/api/bills/{bill['id']}/pay", json=pay)
    second = client.post(f"/api/bills/{bill['id']}/pay", json=pay)
    assert first.status_code == second.status_code == 200
    assert first.json()["expense_id"] == second.json()["expense_id"] is not None
    expenses = client.get("/api/expenses").json()
    assert expenses["total"] == 1 and expenses["items"][0]["bill_id"] == bill["id"]
    assert expenses["items"][0]["category"] == "Utilities"
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
    utilities = category_id(client, "expense", "Utilities")
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
    client.post(
        f"/api/bills/{bill['id']}/pay",
        json={"paid_on": today.isoformat(), "category_id": utilities},
    )
    assert client.delete(f"/api/bills/{bill['id']}").status_code == 204
    kept = client.get("/api/expenses").json()["items"]
    assert len(kept) == 1 and kept[0]["bill_id"] is None and kept[0]["amount"] == "15.00"
    summary = client.get("/api/budget/summary", params={"month": month}).json()
    assert summary["totals"][0]["spent"] == "15.00" and summary["expected_bills"] == []


def test_budget_records_are_isolated_between_accounts(raw_client):
    authenticate(raw_client, "Alice")
    today, month = month_of(raw_client)
    books = category_id(raw_client, "expense", "Books")
    record = expense(raw_client, "8.00", "USD", books, today)
    budget = raw_client.post(
        "/api/budgets", json={"category_id": books, "amount": "20", "currency": "USD"}
    ).json()
    bill = raw_client.post(
        "/api/bills", json={"name": "Alice bill", "amount": "5.00", "due_date": today.isoformat()}
    ).json()
    with TestClient(app) as bob:
        authenticate(bob, "Bob")
        assert bob.get("/api/expenses").json()["total"] == 0
        assert bob.get("/api/budgets").json() == []
        assert bob.get(f"/api/expenses/{record['id']}").status_code == 404
        bob_books = category_id(bob, "expense", "Books")
        assert bob_books != books
        echo = {k: record[k] for k in ("amount", "currency", "spent_on")}
        echo["category_id"] = bob_books
        assert bob.put(f"/api/expenses/{record['id']}", json=echo).status_code == 404
        assert bob.delete(f"/api/expenses/{record['id']}").status_code == 404
        assert bob.delete(f"/api/budgets/{budget['id']}").status_code == 404
        # Alice's category cannot be used for Bob's records.
        stolen = bob.post("/api/expenses", json={**echo, "category_id": books})
        assert stolen.status_code == 422
        stolen_budget = bob.post(
            "/api/budgets", json={"category_id": books, "amount": "1", "currency": "USD"}
        )
        assert stolen_budget.status_code == 422
        # A supplied bill_id is ignored, never used to link another account's bill.
        forged = bob.post("/api/expenses", json={**echo, "bill_id": bill["id"]})
        assert forged.status_code == 201 and forged.json()["bill_id"] is None
        # Paying Alice's bill, even with Bob's own category, is not possible.
        assert (
            bob.post(
                f"/api/bills/{bill['id']}/pay",
                json={"paid_on": today.isoformat(), "category_id": bob_books},
            ).status_code
            == 404
        )
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
    # The database rejects a forged row linking Bob's expense to Alice's bill and category.
    for forged in [
        dict(category_id=UUID(bob_books), bill_id=UUID(bill["id"])),
        dict(category_id=UUID(books), bill_id=None),
    ]:
        session.add(
            Expense(
                user_id=bob_id,
                amount=Decimal(1),
                currency="USD",
                spent_on=today,
                note="",
                **forged,
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
    dependency.close()


def test_dashboard_composes_meals_spending_and_upcoming_items(client):
    today, _ = month_of(client)
    empty = client.get("/api/dashboard").json()
    assert empty["has_records"] is False
    assert empty["meals_today"] == [] and empty["upcoming_tasks"] == []
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
    food = category_id(client, "expense", "Food")
    expense(client, "12.00", "EUR", food, today)
    client.post("/api/budgets", json={"category_id": food, "amount": "10", "currency": "EUR"})
    summary = client.get("/api/dashboard").json()
    assert summary["has_records"] is True
    assert [m["recipe_name"] for m in summary["meals_today"]] == ["Soup"]
    # Today's occurrence is due today; next week's is upcoming, not crowding today.
    assert [t["due_date"] for t in summary["due_today"]] == [today.isoformat()]
    next_week = (today + timedelta(days=7)).isoformat()
    assert [t["due_date"] for t in summary["upcoming_tasks"]] == [next_week]
    assert [b["name"] for b in summary["upcoming_bills"]] == ["Rent"]
    assert summary["spending"]["totals"][0]["currency"] == "EUR"
    assert summary["spending"]["expected_bills"][0] == {
        "currency": "USD",
        "amount": "900.00",
        "count": 1,
    }
    over = summary["spending"]["over_budget"]
    assert [(line["category"], line["remaining"]) for line in over] == [("Food", "-2.00")]
    # Spending in EUR and owed USD rent are never combined into one figure.
    assert len(summary["spending"]["totals"]) == 1
