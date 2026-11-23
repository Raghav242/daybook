from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database import Base
from app.infrastructure.types import UTCDateTime

MEALS = ("breakfast", "lunch", "dinner", "snack")


class Recipe(Base):
    __tablename__ = "recipes"
    __table_args__ = (
        UniqueConstraint("id", "user_id", name="uq_recipes_id_user"),
        CheckConstraint("servings > 0", name="recipe_servings_positive"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200))
    servings: Mapped[int] = mapped_column(Integer)
    notes: Mapped[str] = mapped_column(Text, default="")
    ingredients: Mapped[list["RecipeIngredient"]] = relationship(
        order_by="RecipeIngredient.position",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
    )


class RecipeIngredient(Base):
    __tablename__ = "recipe_ingredients"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ingredient_quantity_positive"),
        # The composite key keeps every ingredient with its recipe's owner.
        ForeignKeyConstraint(
            ["recipe_id", "user_id"],
            ["recipes.id", "recipes.user_id"],
            ondelete="CASCADE",
            name="fk_ingredients_recipe_owner",
        ),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    recipe_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    position: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(200))
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3))
    unit: Mapped[str] = mapped_column(String(40), default="")
    category: Mapped[str] = mapped_column(String(80), default="")


class GroceryImport(Base):
    """One accepted meal-to-grocery submission, keyed by the client's request id."""

    __tablename__ = "grocery_imports"
    __table_args__ = (
        UniqueConstraint("user_id", "request_id", name="uq_grocery_imports_request"),
        UniqueConstraint("id", "user_id", name="uq_grocery_imports_id_user"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    request_id: Mapped[UUID] = mapped_column(Uuid)
    item_count: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime())


class MealPlanEntry(Base):
    __tablename__ = "meal_plan_entries"
    __table_args__ = (
        CheckConstraint("servings > 0", name="meal_servings_positive"),
        CheckConstraint("meal IN ('breakfast', 'lunch', 'dinner', 'snack')", name="meal_plan_meal"),
        ForeignKeyConstraint(
            ["recipe_id", "user_id"],
            ["recipes.id", "recipes.user_id"],
            ondelete="CASCADE",
            name="fk_meal_plan_recipe_owner",
        ),
        ForeignKeyConstraint(
            ["grocery_import_id", "user_id"],
            ["grocery_imports.id", "grocery_imports.user_id"],
            name="fk_meal_plan_import_owner",
        ),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    plan_date: Mapped[date] = mapped_column(Date, index=True)
    meal: Mapped[str] = mapped_column(String(10))
    recipe_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    servings: Mapped[int] = mapped_column(Integer)
    # Set when this meal's ingredients were added to groceries (server-managed).
    grocery_import_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    recipe: Mapped[Recipe] = relationship(lazy="joined", viewonly=True)

    @property
    def recipe_name(self) -> str:
        return self.recipe.name

    @property
    def added_to_groceries(self) -> bool:
        return self.grocery_import_id is not None
