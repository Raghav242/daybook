from typing import Literal
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    select,
)
from sqlalchemy.orm import Mapped, column_property, mapped_column

from app.infrastructure.database import Base

Scope = Literal["task", "expense", "income", "grocery"]
SCOPES: tuple[str, ...] = ("task", "expense", "income", "grocery")

# Starting lists, created once per account and scope. Users can rename, archive and add.
DEFAULTS: dict[str, tuple[str, ...]] = {
    "task": ("Personal", "Study", "Work", "Home", "Health", "Errands"),
    "expense": (
        "Housing",
        "Groceries",
        "Dining",
        "Transport",
        "Utilities",
        "Education",
        "Health",
        "Shopping",
        "Subscriptions",
        "Other",
    ),
    "income": ("Salary", "Part-time Work", "Scholarship", "Freelance", "Gift", "Other"),
    "grocery": (
        "Produce",
        "Dairy & Eggs",
        "Pantry",
        "Frozen",
        "Snacks",
        "Beverages",
        "Household",
        "Other",
    ),
}


def clean_name(name: str) -> str:
    """Display form: surrounding and repeated whitespace removed."""
    return " ".join(name.split())


def category_key(name: str) -> str:
    """Identity within a scope: case- and spacing-insensitive ("Eating  out" == "eating out")."""
    return clean_name(name).casefold()


class Category(Base):
    """A user's named category within one scope.

    Expenses and budgets share the ``expense`` scope, so a budget and the spending it limits
    reference the same row. Records keep pointing at archived categories, which stay readable
    but are not offered for new records.
    """

    __tablename__ = "categories"
    __table_args__ = (
        UniqueConstraint("user_id", "scope", "key", name="uq_categories_scope_key"),
        # Target of the same-owner composite foreign keys on every categorized table.
        UniqueConstraint("id", "user_id", name="uq_categories_id_user"),
        CheckConstraint("scope IN ('task', 'expense', 'income', 'grocery')", name="category_scope"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    scope: Mapped[str] = mapped_column(String(10))
    name: Mapped[str] = mapped_column(String(80))
    key: Mapped[str] = mapped_column(String(80))
    position: Mapped[int] = mapped_column(Integer, default=0)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)


def category_name(model):
    """Read-only display name for ``model.category_id`` (archived categories included)."""
    return column_property(
        select(Category.name)
        .where(Category.id == model.category_id, Category.user_id == model.user_id)
        .correlate_except(Category)
        .scalar_subquery()
    )


def category_owner_key(table: str):
    """Composite key that keeps a record's category within the record owner's account."""
    return ForeignKeyConstraint(
        ["category_id", "user_id"],
        ["categories.id", "categories.user_id"],
        name=f"fk_{table}_category_owner",
    )
