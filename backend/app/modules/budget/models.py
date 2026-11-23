from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    ForeignKeyConstraint,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base


def category_key(name: str) -> str:
    """Case- and spacing-insensitive category identity, e.g. "Eating  out" == "eating out"."""
    return " ".join(name.split()).casefold()


class Expense(Base):
    """Recorded spending. Expected bill payments are bills, not expenses."""

    __tablename__ = "expenses"
    __table_args__ = (
        CheckConstraint("amount > 0", name="expense_amount_positive"),
        # One expense per bill: paying twice cannot double count.
        UniqueConstraint("bill_id", name="uq_expenses_bill_id"),
        ForeignKeyConstraint(
            ["bill_id", "user_id"], ["bills.id", "bills.user_id"], name="fk_expenses_bill_owner"
        ),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(3))
    category: Mapped[str] = mapped_column(String(80))
    category_key: Mapped[str] = mapped_column(String(80))
    spent_on: Mapped[date] = mapped_column(Date, index=True)
    note: Mapped[str] = mapped_column(String(500), default="")
    bill_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)


class Budget(Base):
    """A standing monthly limit for one category in one currency."""

    __tablename__ = "budgets"
    __table_args__ = (
        CheckConstraint("amount >= 0", name="budget_amount_nonnegative"),
        UniqueConstraint("user_id", "category_key", "currency", name="uq_budgets_category"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(80))
    category_key: Mapped[str] = mapped_column(String(80))
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(3))
