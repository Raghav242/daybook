from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.core.schemas import Input, Output

Meal = Literal["breakfast", "lunch", "dinner", "snack"]
Quantity = Field(gt=0, max_digits=12, decimal_places=3)


class IngredientInput(Input):
    name: str = Field(min_length=1, max_length=200)
    quantity: Decimal = Quantity
    unit: str = Field(default="", max_length=40)
    # Grocery category used when this ingredient is added to the list.
    category_id: UUID | None = None
    category: str | None = Field(default=None, exclude=True)
    id: UUID | None = Field(default=None, exclude=True)


class IngredientOutput(Output):
    id: UUID
    name: str
    quantity: Decimal
    unit: str
    category_id: UUID | None = None
    category: str | None = None


class RecipeInput(Input):
    name: str = Field(min_length=1, max_length=200)
    servings: int = Field(ge=1, le=1000)
    notes: str = Field(default="", max_length=10000)
    ingredients: list[IngredientInput] = Field(default_factory=list, max_length=100)


class RecipeOutput(Output):
    id: UUID
    name: str
    servings: int
    notes: str
    ingredients: list[IngredientOutput]


class RecipePage(BaseModel):
    items: list[RecipeOutput]
    total: int
    offset: int
    limit: int


class MealPlanInput(Input):
    plan_date: date
    meal: Meal
    recipe_id: UUID
    servings: int = Field(ge=1, le=1000)
    # Read-only fields accepted for full-record echo; never written.
    recipe_name: str | None = Field(default=None, exclude=True)
    added_to_groceries: bool | None = Field(default=None, exclude=True)


class MealPlanOutput(Output):
    id: UUID
    plan_date: date
    meal: Meal
    recipe_id: UUID
    recipe_name: str
    servings: int
    added_to_groceries: bool


class PreviewInput(Input):
    entry_ids: list[UUID] = Field(min_length=1, max_length=100)


class PreviewLine(BaseModel):
    key: str
    name: str
    unit: str
    quantity: Decimal
    category_id: UUID | None
    category: str
    sources: list[str]
    other_units: bool
    on_list: Decimal | None


class Preview(BaseModel):
    entries: list[MealPlanOutput]
    items: list[PreviewLine]
    skipped_entry_ids: list[UUID]


class AdditionItem(Input):
    name: str = Field(min_length=1, max_length=200)
    quantity: Decimal = Quantity
    unit: str = Field(default="", max_length=40)
    category_id: UUID | None = None


class AdditionInput(Input):
    request_id: UUID
    entry_ids: list[UUID] = Field(min_length=1, max_length=100)
    items: list[AdditionItem] = Field(min_length=1, max_length=200)


class AdditionResult(BaseModel):
    request_id: UUID
    created: bool
    added: int
