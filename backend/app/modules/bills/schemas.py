from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from app.core.schemas import Input, Output
from app.modules.recurrence.schemas import RecurrenceFields


class BillInput(Input):
    name: str = Field(min_length=1, max_length=200)
    amount: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$")
    due_date: date
    paid: bool = False
    # Read-only links, accepted for full-record echo and excluded from writes.
    series_id: UUID | None = Field(default=None, exclude=True)
    occurrence_date: date | None = Field(default=None, exclude=True)
    expense_id: UUID | None = Field(default=None, exclude=True)


class BillOutput(Output):
    id: UUID
    name: str
    amount: Decimal
    currency: str
    due_date: date
    paid: bool
    series_id: UUID | None = None
    occurrence_date: date | None = None
    expense_id: UUID | None = None


class BillSeriesInput(RecurrenceFields):
    name: str = Field(min_length=1, max_length=200)
    amount: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$")


class BillSeriesOutput(BillSeriesInput, Output):
    id: UUID


class PayInput(Input):
    paid_on: date
    record_expense: bool = True
    # Expense category for the recorded payment; required when record_expense is true.
    category_id: UUID | None = None
    note: str = Field(default="", max_length=500)
