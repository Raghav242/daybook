from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from app.core.errors import NotFound
from app.modules.auth.service import now_utc
from app.modules.categories.service import CategoryService
from app.modules.groceries.models import Grocery
from app.modules.meals.domain import Ingredient, merge, normalize_text, normalize_unit, scale
from app.modules.meals.models import GroceryImport, MealPlanEntry, Recipe, RecipeIngredient
from app.modules.meals.repository import MealsRepository
from app.modules.meals.schemas import AdditionInput, MealPlanInput, RecipeInput


class MealsService:
    def __init__(self, repository: MealsRepository, categories: CategoryService):
        if repository.user_id != categories.repository.user_id:
            raise ValueError("Meals and categories must use the same authenticated owner.")
        self.repository = repository
        self.categories = categories

    # Recipes
    def list_recipes(self, offset: int, limit: int):
        return self.repository.list_recipes(offset, limit)

    def get_recipe(self, record_id: UUID):
        record = self.repository.get_recipe(record_id)
        if record is None:
            raise NotFound("This recipe could not be found.")
        return record

    def _ingredients(self, data: RecipeInput, recipe: Recipe | None = None):
        # Ingredients may keep an archived aisle they already had.
        kept = {item.category_id for item in recipe.ingredients} if recipe else set()
        for item in data.ingredients:
            current = item.category_id if item.category_id in kept else None
            self.categories.require("grocery", item.category_id, current, optional=True)
        return [
            RecipeIngredient(user_id=self.repository.user_id, position=index, **item.model_dump())
            for index, item in enumerate(data.ingredients)
        ]

    def create_recipe(self, data: RecipeInput):
        ingredients = self._ingredients(data)
        recipe = Recipe(user_id=self.repository.user_id, **data.model_dump(exclude={"ingredients"}))
        recipe.ingredients = ingredients
        return self.repository.save(recipe)

    def update_recipe(self, record_id: UUID, data: RecipeInput):
        """Replace the recipe and its ingredient list. Future previews use the new list."""
        recipe = self.get_recipe(record_id)
        ingredients = self._ingredients(data, recipe)
        for key, value in data.model_dump(exclude={"ingredients"}).items():
            setattr(recipe, key, value)
        recipe.ingredients = ingredients
        return self.repository.save(recipe)

    def delete_recipe(self, record_id: UUID):
        """Delete a recipe and its planned meals. Groceries already added are kept."""
        self.repository.delete(self.get_recipe(record_id))

    # Meal plan
    def entries(self, first: date, days: int = 7):
        return self.repository.entries_between(first, first + timedelta(days=days - 1))

    def get_entry(self, record_id: UUID):
        record = self.repository.get_entry(record_id)
        if record is None:
            raise NotFound("This planned meal could not be found.")
        return record

    def create_entry(self, data: MealPlanInput):
        self.get_recipe(data.recipe_id)
        entry = self.repository.save(
            MealPlanEntry(user_id=self.repository.user_id, **data.model_dump())
        )
        return self.get_entry(entry.id)

    def update_entry(self, record_id: UUID, data: MealPlanInput):
        entry = self.get_entry(record_id)
        self.get_recipe(data.recipe_id)
        for key, value in data.model_dump().items():
            setattr(entry, key, value)
        self.repository.save(entry)
        return self.get_entry(record_id)

    def delete_entry(self, record_id: UUID):
        self.repository.delete(self.get_entry(record_id))

    def _selected(self, entry_ids: list[UUID]):
        ids = list(dict.fromkeys(entry_ids))
        entries = self.repository.entries_by_ids(ids)
        if len(entries) != len(ids):
            raise NotFound("A selected meal could not be found.")
        return ids, entries

    def preview(self, entry_ids: list[UUID]):
        """Scaled, merged grocery lines for the selected meals. Nothing is written.

        Meals whose groceries were already added are listed in ``skipped_entry_ids`` and
        contribute nothing, so previewing again cannot double the list.
        """
        _, entries = self._selected(entry_ids)
        ingredients = [
            Ingredient(
                name=item.name,
                quantity=scale(item.quantity, entry.recipe.servings, entry.servings),
                unit=item.unit,
                category=item.category or "",
                category_id=item.category_id,
                source=entry.recipe.name,
            )
            for entry in entries
            if entry.grocery_import_id is None
            for item in entry.recipe.ingredients
        ]
        on_list: dict[str, Decimal] = {}
        for grocery in self.repository.open_groceries():
            key = f"{normalize_text(grocery.name)}|{normalize_unit(grocery.unit)}"
            on_list[key] = on_list.get(key, Decimal(0)) + grocery.quantity
        return dict(
            entries=entries,
            items=[dict(vars(line), on_list=on_list.get(line.key)) for line in merge(ingredients)],
            skipped_entry_ids=[entry.id for entry in entries if entry.grocery_import_id],
        )

    def add_to_groceries(self, data: AdditionInput):
        """Add the reviewed items as new grocery rows, exactly once per request id."""
        previous = self.repository.find_import(data.request_id)
        if previous is not None:
            return dict(request_id=data.request_id, created=False, added=previous.item_count)
        ids, _ = self._selected(data.entry_ids)
        for item in data.items:
            # Reviewed lines carry the recipe's aisle, which may since have been archived.
            self.categories.require("grocery", item.category_id, optional=True, allow_archived=True)
        user_id = self.repository.user_id
        record = GroceryImport(
            user_id=user_id,
            request_id=data.request_id,
            item_count=len(data.items),
            created_at=now_utc(),
        )
        groceries = [
            Grocery(user_id=user_id, purchased=False, **item.model_dump()) for item in data.items
        ]
        if not self.repository.add_groceries(record, ids, groceries):
            previous = self.repository.find_import(data.request_id)
            return dict(request_id=data.request_id, created=False, added=previous.item_count)
        return dict(request_id=data.request_id, created=True, added=len(groceries))
