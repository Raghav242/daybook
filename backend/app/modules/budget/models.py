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
from app.modules.categories.models import category_name, category_owner_key


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
        category_owner_key("expenses"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(3))
    # An ``expense``-scope category, shared with budgets.
    category_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    spent_on: Mapped[date] = mapped_column(Date, index=True)
    note: Mapped[str] = mapped_column(String(500), default="")
    bill_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)


class Budget(Base):
    """A standing monthly limit for one expense category in one currency."""

    __tablename__ = "budgets"
    __table_args__ = (
        CheckConstraint("amount >= 0", name="budget_amount_nonnegative"),
        UniqueConstraint("user_id", "category_id", "currency", name="uq_budgets_category"),
        category_owner_key("budgets"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    category_id: Mapped[UUID] = mapped_column(Uuid)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(3))


class Income(Base):
    """Money the user reports receiving. Entered manually; never inferred or connected."""

    __tablename__ = "income"
    __table_args__ = (
        CheckConstraint("amount > 0", name="income_amount_positive"),
        category_owner_key("income"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(3))
    # An ``income``-scope category (the source, such as Salary or Scholarship).
    category_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    received_on: Mapped[date] = mapped_column(Date, index=True)
    note: Mapped[str] = mapped_column(String(500), default="")


Expense.category = category_name(Expense)
Budget.category = category_name(Budget)
Income.category = category_name(Income)
