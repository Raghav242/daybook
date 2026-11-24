from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from conftest import authenticate, category_id
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.infrastructure.database import get_session
from app.main import app
from app.modules.categories.models import DEFAULTS
from app.modules.groceries.models import Grocery
from app.modules.tasks.models import Task


def echo(record, **changes):
    """A full record as a client would send it back: everything but its id."""
    return {**{k: v for k, v in record.items() if k != "id"}, **changes}


def listing(client, scope, include_archived=True):
    response = client.get(
        "/api/categories", params={"scope": scope, "include_archived": include_archived}
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_every_account_starts_with_the_default_lists_once(client):
    everything = client.get("/api/categories").json()
    for scope, names in DEFAULTS.items():
        assert [c["name"] for c in everything if c["scope"] == scope] == list(names)
    assert [c["name"] for c in listing(client, "expense")][:3] == ["Housing", "Groceries", "Dining"]
    assert len(client.get("/api/categories").json()) == len(everything)  # not seeded twice
    assert client.get("/api/categories", params={"scope": "bank"}).status_code == 422


def test_custom_categories_are_unique_per_scope_after_normalizing(client):
    created = client.post("/api/categories", json={"scope": "task", "name": "  Side   project "})
    assert created.status_code == 201 and created.json()["name"] == "Side project"
    again = client.post("/api/categories", json={"scope": "task", "name": "side PROJECT"})
    assert again.status_code == 200 and again.json()["id"] == created.json()["id"]
    elsewhere = client.post("/api/categories", json={"scope": "expense", "name": "Side project"})
    assert elsewhere.status_code == 201 and elsewhere.json()["id"] != created.json()["id"]
    assert [c["name"] for c in listing(client, "task")][-1] == "Side project"
    for bad in [{"scope": "task", "name": "   "}, {"scope": "nope", "name": "X"}]:
        assert client.post("/api/categories", json=bad).status_code == 422
    work = next(c for c in listing(client, "task") if c["name"] == "Work")
    clash = client.put(f"/api/categories/{work['id']}", json={"name": "side project"})
    assert clash.status_code == 409
    renamed = client.put(f"/api/categories/{work['id']}", json={"name": "Job"})
    assert renamed.status_code == 200 and renamed.json()["name"] == "Job"
    assert client.put(f"/api/categories/{uuid4()}", json={"name": "Ghost"}).status_code == 404


def test_archived_categories_stay_on_records_but_are_not_offered(client):
    study = category_id(client, "task", "Study")
    task = client.post("/api/tasks", json={"title": "Essay", "category_id": study}).json()
    assert task["category"] == "Study"
    archived = client.put(f"/api/categories/{study}", json={"name": "Study", "archived": True})
    assert archived.status_code == 200 and archived.json()["archived"] is True
    assert study not in [c["id"] for c in listing(client, "task", include_archived=False)]
    assert study in [c["id"] for c in listing(client, "task")]
    # Existing records still read their category and can be edited without changing it.
    assert client.get(f"/api/tasks/{task['id']}").json()["category"] == "Study"
    edited = client.put(f"/api/tasks/{task['id']}", json=echo(task, title="Essay v2"))
    assert edited.status_code == 200 and edited.json()["category_id"] == study
    # New records cannot choose it.
    fresh = client.post("/api/tasks", json={"title": "New", "category_id": study})
    assert fresh.status_code == 422 and "archived" in fresh.json()["error"]["message"]
    # Archiving never brings the starting list back, and adding the name again restores it.
    assert len(listing(client, "task")) == len(DEFAULTS["task"])
    restored = client.post("/api/categories", json={"scope": "task", "name": "study"})
    assert restored.status_code == 200 and restored.json() == {**archived.json(), "archived": False}


def test_records_validate_category_scope_and_keep_names(client):
    produce = category_id(client, "grocery", "Produce")
    personal = category_id(client, "task", "Personal")
    grocery = client.post(
        "/api/groceries", json={"name": "Apples", "quantity": "3", "category_id": produce}
    )
    assert grocery.status_code == 201 and grocery.json()["category"] == "Produce"
    wrong = client.post("/api/groceries", json={"name": "Pears", "category_id": personal})
    assert wrong.status_code == 422
    plain = client.post("/api/tasks", json={"title": "No category"}).json()
    assert plain["category_id"] is None and plain["category"] is None
    # The display name is read-only: echoing it back never renames or re-links anything.
    echoed = client.put(
        f"/api/groceries/{grocery.json()['id']}", json=echo(grocery.json(), category="Hacked")
    ).json()
    assert echoed["category"] == "Produce"
    renamed = client.put(f"/api/categories/{produce}", json={"name": "Fruit & veg"})
    assert renamed.status_code == 200
    assert client.get(f"/api/groceries/{echoed['id']}").json()["category"] == "Fruit & veg"
    series = client.post(
        "/api/task-series",
        json={
            "title": "Gym",
            "frequency": "weekly",
            "start_date": "2026-11-02",
            "category_id": produce,
        },
    )
    assert series.status_code == 422  # a grocery aisle is not a task category


def test_categories_are_private_to_each_account(raw_client):
    authenticate(raw_client, "Alice")
    secret = category_id(raw_client, "expense", "Therapy")
    study = category_id(raw_client, "task", "Study")
    task = raw_client.post("/api/tasks", json={"title": "Read", "category_id": study}).json()
    with TestClient(app) as bob:
        authenticate(bob, "Bob")
        names = [c["name"] for c in bob.get("/api/categories").json()]
        assert "Therapy" not in names
        assert bob.put(f"/api/categories/{secret}", json={"name": "Mine"}).status_code == 404
        for path, body in [
            ("/api/tasks", {"title": "x", "category_id": study}),
            ("/api/groceries", {"name": "x", "category_id": study}),
            (
                "/api/income",
                {
                    "amount": "5",
                    "currency": "USD",
                    "category_id": secret,
                    "received_on": "2026-11-02",
                },
            ),
            (
                "/api/task-series",
                {
                    "title": "x",
                    "frequency": "daily",
                    "start_date": "2026-11-02",
                    "category_id": study,
                },
            ),
            (
                "/api/recipes",
                {
                    "name": "x",
                    "servings": 1,
                    "ingredients": [{"name": "x", "quantity": "1", "category_id": study}],
                },
            ),
        ]:
            response = bob.post(path, json=body)
            assert response.status_code == 422, (path, response.text)
            assert "Therapy" not in response.text and "Study" not in response.text
        bob_id = UUID(bob.get("/api/auth/me").json()["user"]["id"])
    assert raw_client.get(f"/api/tasks/{task['id']}").json()["category"] == "Study"
    # The database rejects records pointing at another account's category.
    dependency = app.dependency_overrides[get_session]()
    session = next(dependency)
    for record in [
        Task(user_id=bob_id, title="Forged", category_id=UUID(study)),
        Grocery(user_id=bob_id, name="Forged", quantity=Decimal(1), category_id=UUID(study)),
    ]:
        session.add(record)
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
    dependency.close()
