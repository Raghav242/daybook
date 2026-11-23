from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from conftest import authenticate
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.infrastructure.database import get_session
from app.main import app
from app.modules.meals.domain import Ingredient, merge, normalize_unit, scale
from app.modules.meals.models import RecipeIngredient


def test_scaling_is_exact_and_never_rounds_to_zero():
    assert scale(Decimal("200"), 4, 6) == Decimal("300.000")
    assert scale(Decimal("1"), 3, 1) == Decimal("0.333")
    assert scale(Decimal("2"), 3, 1) == Decimal("0.667")  # half-up
    assert scale(Decimal("0.001"), 8, 1) == Decimal("0.001")
    with pytest.raises(ValueError):
        scale(Decimal("1"), 0, 2)


def test_merging_requires_matching_names_and_units():
    lines = merge(
        [
            Ingredient("Flour", Decimal("1.5"), "cups", "Pantry", "Pancakes"),
            Ingredient(" flour ", Decimal("0.5"), "Cup", "Pantry", "Bread"),
            Ingredient("Flour", Decimal("200"), "g", "Pantry", "Bread"),
            Ingredient("flour", Decimal("50"), "grams", "", "Cake"),
            Ingredient("Eggs", Decimal("2"), "", "Fridge", "Pancakes"),
            Ingredient("Egg whites", Decimal("2"), "", "Fridge", "Cake"),
        ]
    )
    by_key = {line.key: line for line in lines}
    assert by_key["flour|cup"].quantity == Decimal("2.0")
    assert by_key["flour|cup"].sources == ["Pancakes", "Bread"]
    assert by_key["flour|g"].quantity == Decimal("250")  # spelling only, no conversion
    assert by_key["flour|cup"].other_units and by_key["flour|g"].other_units
    assert not by_key["eggs|"].other_units and "egg whites|" in by_key
    assert normalize_unit("tablespoons") == normalize_unit("Tbsp.") == "tbsp"
    assert normalize_unit("cup") != normalize_unit("ml")


def make_recipe(client, **overrides):
    body = {
        "name": "Pancakes",
        "servings": 4,
        "ingredients": [
            {"name": "Flour", "quantity": "200", "unit": "g", "category": "Pantry"},
            {"name": "Milk", "quantity": "1.5", "unit": "cups", "category": "Fridge"},
            {"name": "Egg", "quantity": "2", "unit": ""},
        ],
        **overrides,
    }
    response = client.post("/api/recipes", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def plan(client, recipe, servings, day="2026-11-23", meal="breakfast"):
    response = client.post(
        "/api/meal-plan",
        json={"plan_date": day, "meal": meal, "recipe_id": recipe["id"], "servings": servings},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_recipe_crud_preserves_ingredient_order(client):
    recipe = make_recipe(client)
    assert [i["name"] for i in recipe["ingredients"]] == ["Flour", "Milk", "Egg"]
    recipe_id = recipe.pop("id")
    recipe["ingredients"] = [{"name": "Oats", "quantity": "1", "unit": "cup"}]
    updated = client.put(f"/api/recipes/{recipe_id}", json=recipe)
    assert updated.status_code == 200, updated.text
    assert [i["name"] for i in updated.json()["ingredients"]] == ["Oats"]
    assert client.post("/api/recipes", json={"name": "x", "servings": 0}).status_code == 422
    bad = {"name": "x", "servings": 1, "ingredients": [{"name": "y", "quantity": "0"}]}
    assert client.post("/api/recipes", json=bad).status_code == 422


def test_weekly_plan_and_scaled_preview(client):
    pancakes = make_recipe(client)
    bread = make_recipe(
        client,
        name="Bread",
        servings=2,
        ingredients=[
            {"name": "flour", "quantity": "300", "unit": "grams"},
            {"name": "Flour", "quantity": "1", "unit": "cup"},
        ],
    )
    breakfast = plan(client, pancakes, 6)
    dinner = plan(client, bread, 1, day="2026-11-25", meal="dinner")
    plan(client, pancakes, 2, day="2026-12-01")  # outside the week
    week = client.get("/api/meal-plan", params={"start": "2026-11-23"}).json()
    assert [entry["id"] for entry in week] == [breakfast["id"], dinner["id"]]
    assert week[0]["recipe_name"] == "Pancakes" and week[0]["added_to_groceries"] is False
    client.post("/api/groceries", json={"name": "Milk", "quantity": "1", "unit": "cup"})
    preview = client.post(
        "/api/meal-plan/grocery-preview", json={"entry_ids": [breakfast["id"], dinner["id"]]}
    )
    assert preview.status_code == 200, preview.text
    items = {item["key"]: item for item in preview.json()["items"]}
    assert Decimal(items["flour|g"]["quantity"]) == Decimal("450")  # 300 + 150
    assert Decimal(items["milk|cup"]["quantity"]) == Decimal("2.25")
    assert Decimal(items["milk|cup"]["on_list"]) == Decimal("1")
    assert Decimal(items["egg|"]["quantity"]) == Decimal("3")
    assert Decimal(items["flour|cup"]["quantity"]) == Decimal("0.5")
    assert items["flour|cup"]["other_units"] is True
    assert sorted(items["flour|g"]["sources"]) == ["Bread", "Pancakes"]
    assert client.get("/api/groceries").json()["total"] == 1  # preview writes nothing


def test_repeated_grocery_submissions_add_items_once(client):
    recipe = make_recipe(client)
    entry = plan(client, recipe, 4)
    manual = client.post(
        "/api/groceries", json={"name": "Flour", "quantity": "1", "unit": "kg", "category": "Mine"}
    ).json()
    preview = client.post("/api/meal-plan/grocery-preview", json={"entry_ids": [entry["id"]]})
    reviewed = [
        {k: item[k] for k in ("name", "quantity", "unit", "category")}
        for item in preview.json()["items"]
    ]
    next(item for item in reviewed if item["name"] == "Flour")["quantity"] = "150"  # reviewed
    body = {"request_id": str(uuid4()), "entry_ids": [entry["id"]], "items": reviewed}
    first = client.post("/api/meal-plan/grocery-additions", json=body)
    assert first.status_code == 201 and first.json() == {
        **first.json(),
        "created": True,
        "added": 3,
    }
    replay = client.post("/api/meal-plan/grocery-additions", json=body)
    assert replay.status_code == 200 and replay.json()["created"] is False
    again = client.post(
        "/api/meal-plan/grocery-additions", json={**body, "request_id": str(uuid4())}
    )
    assert again.status_code == 409
    groceries = client.get("/api/groceries", params={"limit": 100}).json()["items"]
    assert len(groceries) == 4
    assert next(g for g in groceries if g["id"] == manual["id"]) == manual
    assert {g["quantity"] for g in groceries if g["name"] == "Flour" and g["unit"] == "g"} == {
        "150.000"
    }
    # A later preview flags the meal as already added and contributes no lines.
    later = client.post("/api/meal-plan/grocery-preview", json={"entry_ids": [entry["id"]]}).json()
    assert later["items"] == [] and later["skipped_entry_ids"] == [entry["id"]]
    assert later["entries"][0]["added_to_groceries"] is True


def test_deleting_a_recipe_removes_its_plans_but_keeps_added_groceries(client):
    recipe = make_recipe(client)
    entry = plan(client, recipe, 4)
    client.post(
        "/api/meal-plan/grocery-additions",
        json={
            "request_id": str(uuid4()),
            "entry_ids": [entry["id"]],
            "items": [{"name": "Flour", "quantity": "200", "unit": "g"}],
        },
    )
    assert client.delete(f"/api/recipes/{recipe['id']}").status_code == 204
    assert client.get("/api/meal-plan", params={"start": "2026-11-23"}).json() == []
    assert client.get("/api/groceries").json()["total"] == 1


def test_meals_are_isolated_between_accounts(raw_client):
    authenticate(raw_client, "Alice")
    recipe = make_recipe(raw_client)
    entry = plan(raw_client, recipe, 2)
    with TestClient(app) as bob:
        authenticate(bob, "Bob")
        assert bob.get("/api/recipes").json()["total"] == 0
        assert bob.get(f"/api/recipes/{recipe['id']}").status_code == 404
        assert bob.get("/api/meal-plan", params={"start": "2026-11-23"}).json() == []
        # Bob cannot plan with, preview, or add groceries from Alice's records.
        attempt = {
            "plan_date": "2026-11-23",
            "meal": "lunch",
            "recipe_id": recipe["id"],
            "servings": 1,
        }
        assert bob.post("/api/meal-plan", json=attempt).status_code == 404
        assert bob.put(f"/api/meal-plan/{entry['id']}", json=attempt).status_code == 404
        assert (
            bob.post(
                "/api/meal-plan/grocery-preview", json={"entry_ids": [entry["id"]]}
            ).status_code
            == 404
        )
        additions = {
            "request_id": str(uuid4()),
            "entry_ids": [entry["id"]],
            "items": [{"name": "x", "quantity": "1"}],
        }
        assert bob.post("/api/meal-plan/grocery-additions", json=additions).status_code == 404
        assert bob.get("/api/groceries").json()["total"] == 0
        bob_id = UUID(bob.get("/api/auth/me").json()["user"]["id"])
    assert raw_client.get(f"/api/recipes/{recipe['id']}").status_code == 200
    dependency = app.dependency_overrides[get_session]()
    session = next(dependency)
    session.add(
        RecipeIngredient(
            recipe_id=UUID(recipe["id"]),
            user_id=bob_id,
            position=9,
            name="Forged",
            quantity=Decimal(1),
            unit="",
            category="",
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()
    dependency.close()
