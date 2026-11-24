from datetime import date
from uuid import UUID

import pytest
from conftest import authenticate, category_id
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.infrastructure.database import get_session
from app.main import app
from app.modules.budget.models import Income


def income(client, amount, currency, category, day, note=""):
    response = client.post(
        "/api/income",
        json={
            "amount": amount,
            "currency": currency,
            "category_id": category,
            "received_on": day,
            "note": note,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_income_crud_and_validation(client):
    salary = category_id(client, "income", "Salary")
    record = income(client, "1250.50", "USD", salary, "2026-03-31", "March pay")
    assert record["category"] == "Salary" and record["amount"] == "1250.50"
    assert client.get(f"/api/income/{record['id']}").json() == record
    edited = client.put(
        f"/api/income/{record['id']}",
        json={k: v for k, v in record.items() if k != "id"}
        | {"amount": "1300.00", "note": "Corrected"},
    )
    assert edited.status_code == 200 and edited.json()["amount"] == "1300.00"
    groceries = category_id(client, "expense", "Groceries")
    for bad in [
        {"amount": "0"},
        {"amount": "-5"},
        {"amount": "1.005"},
        {"currency": "usd"},
        {"received_on": "2026-03-31T10:00:00Z"},  # a date, not an instant
        {"category_id": groceries},  # expense category, not an income source
    ]:
        body = {
            "amount": "1",
            "currency": "USD",
            "category_id": salary,
            "received_on": "2026-03-01",
            **bad,
        }
        assert client.post("/api/income", json=body).status_code == 422, bad
    assert client.delete(f"/api/income/{record['id']}").status_code == 204
    assert client.get(f"/api/income/{record['id']}").status_code == 404


def test_monthly_cash_flow_is_exact_per_currency_and_leaves_budgets_alone(client):
    salary = category_id(client, "income", "Salary")
    gift = category_id(client, "income", "Gift")
    dining = category_id(client, "expense", "Dining")
    for amount in ["0.10", "0.20"]:
        income(client, amount, "USD", gift, "2026-03-15")
    income(client, "1000.00", "USD", salary, "2026-03-31")  # last day counts in March
    income(client, "999.00", "USD", salary, "2026-04-01")  # first day of April does not
    income(client, "200.00", "EUR", salary, "2026-03-01")
    client.post(
        "/api/expenses",
        json={
            "amount": "40.00",
            "currency": "USD",
            "category_id": dining,
            "spent_on": "2026-03-10",
        },
    )
    client.post("/api/budgets", json={"category_id": dining, "amount": "30", "currency": "USD"})
    summary = client.get("/api/budget/summary", params={"month": "2026-03"}).json()
    totals = {t["currency"]: t for t in summary["totals"]}
    assert totals["USD"]["income"] == "1000.30"
    assert totals["USD"]["spent"] == "40.00"  # income does not reduce recorded spending
    assert totals["USD"]["net"] == "960.30"
    assert totals["USD"]["remaining"] == "-10.00"  # nor does it raise the budget
    assert summary["categories"][0]["remaining"] == "-10.00"
    assert totals["EUR"]["income"] == "200.00" and totals["EUR"]["net"] == "200.00"
    assert totals["EUR"]["spent"] == "0.00"  # currencies are never combined
    april = client.get("/api/budget/summary", params={"month": "2026-04"}).json()
    assert [(t["currency"], t["income"], t["net"]) for t in april["totals"]] == [
        ("USD", "999.00", "999.00")
    ]
    assert client.get("/api/income", params={"month": "2026-03"}).json()["total"] == 4


def test_transactions_combine_and_filter_expenses_and_income(client):
    salary = category_id(client, "income", "Salary")
    dining = category_id(client, "expense", "Dining")
    income(client, "500.00", "USD", salary, "2026-05-02")
    for day in ["2026-05-01", "2026-05-03", "2026-06-01"]:
        client.post(
            "/api/expenses",
            json={"amount": "9.99", "currency": "USD", "category_id": dining, "spent_on": day},
        )

    def page(kind, **params):
        response = client.get(
            "/api/transactions", params={"month": "2026-05", "kind": kind, **params}
        )
        assert response.status_code == 200, response.text
        return response.json()

    every = page("all")
    assert every["total"] == 3
    assert [(t["kind"], t["date"]) for t in every["items"]] == [
        ("expense", "2026-05-03"),
        ("income", "2026-05-02"),
        ("expense", "2026-05-01"),
    ]
    assert every["items"][1]["category"] == "Salary" and every["items"][1]["bill_id"] is None
    assert [t["kind"] for t in page("expense")["items"]] == ["expense", "expense"]
    assert [t["amount"] for t in page("income")["items"]] == ["500.00"]
    second = page("all", limit=2, offset=2)
    assert second["total"] == 3 and len(second["items"]) == 1
    assert client.get("/api/transactions", params={"kind": "transfer"}).status_code == 422


def test_income_is_isolated_between_accounts(raw_client):
    alice_user = authenticate(raw_client, "Alice")
    salary = category_id(raw_client, "income", "Salary")
    record = income(raw_client, "10.00", "USD", salary, date.today().isoformat())
    with TestClient(app) as bob:
        authenticate(bob, "Bob")
        assert bob.get("/api/income").json()["total"] == 0
        assert bob.get("/api/transactions").json()["total"] == 0
        assert bob.get(f"/api/income/{record['id']}").status_code == 404
        own = category_id(bob, "income", "Salary")
        echo = {k: v for k, v in record.items() if k != "id"} | {"category_id": own}
        assert bob.put(f"/api/income/{record['id']}", json=echo).status_code == 404
        assert bob.delete(f"/api/income/{record['id']}").status_code == 404
        assert all(t["income"] == "0.00" for t in bob.get("/api/budget/summary").json()["totals"])
        bob_id = UUID(bob.get("/api/auth/me").json()["user"]["id"])
    assert raw_client.get(f"/api/income/{record['id']}").json()["amount"] == "10.00"
    assert alice_user["id"] != str(bob_id)
    dependency = app.dependency_overrides[get_session]()
    session = next(dependency)
    session.add(
        Income(
            user_id=bob_id,
            amount=1,
            currency="USD",
            category_id=UUID(salary),
            received_on=date.today(),
            note="",
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()
    dependency.close()
