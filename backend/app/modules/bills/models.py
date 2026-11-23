from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
    select,
)
from sqlalchemy.orm import Mapped, column_property, mapped_column

from app.infrastructure.database import Base
from app.modules.budget.models import Expense


class BillSeries(Base):
    """A recurring bill definition. Its occurrences are rows in ``bills``."""

    __tablename__ = "bill_series"
    __table_args__ = (
        UniqueConstraint("id", "user_id", name="uq_bill_series_id_user"),
        CheckConstraint(
            "frequency IN ('daily', 'weekly', 'monthly')", name="bill_series_frequency"
        ),
        CheckConstraint("repeat_interval >= 1", name="bill_series_interval"),
        CheckConstraint("until_date IS NULL OR until_date >= start_date", name="bill_series_until"),
        CheckConstraint("amount >= 0", name="bill_series_amount_nonnegative"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200))
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    frequency: Mapped[str] = mapped_column(String(10))
    # "interval" is a PostgreSQL keyword, so the column is named repeat_interval.
    interval: Mapped[int] = mapped_column("repeat_interval", Integer, default=1)
    start_date: Mapped[date] = mapped_column(Date)
    until_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    generated_through: Mapped[date] = mapped_column(Date)

    def occurrence_values(self, day: date):
        return dict(
            name=self.name, amount=self.amount, currency=self.currency, due_date=day, paid=False
        )


class Bill(Base):
    __tablename__ = "bills"
    __table_args__ = (
        CheckConstraint("amount >= 0", name="bill_amount_nonnegative"),
        CheckConstraint(
            "series_id IS NULL OR occurrence_date IS NOT NULL", name="bill_occurrence_date"
        ),
        UniqueConstraint("id", "user_id", name="uq_bills_id_user"),
        UniqueConstraint("series_id", "occurrence_date", name="uq_bills_series_occurrence"),
        ForeignKeyConstraint(
            ["series_id", "user_id"],
            ["bill_series.id", "bill_series.user_id"],
            name="fk_bills_series_owner",
        ),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200))
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    due_date: Mapped[date] = mapped_column(Date, index=True)
    paid: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    # Set only by recurrence generation; read-only through the API.
    series_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    occurrence_date: Mapped[date | None] = mapped_column(Date, nullable=True)


# The expense recorded when this bill was paid, if any (read-only).
Bill.expense_id = column_property(
    select(Expense.id)
    .where(Expense.bill_id == Bill.id, Expense.user_id == Bill.user_id)
    .correlate_except(Expense)
    .scalar_subquery()
)
