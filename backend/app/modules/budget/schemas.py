from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.core.schemas import Input, Output
from app.modules.bills.schemas import BillOutput

Money = Field(gt=0, max_digits=14, decimal_places=2)
CURRENCY = Field(pattern=r"^[A-Z]{3}$")


class ExpenseInput(Input):
    amount: Decimal = Money
    currency: str = CURRENCY
    category: str = Field(min_length=1, max_length=80)
    spent_on: date
    note: str = Field(default="", max_length=500)
    # Set only when a bill is paid; accepted for full-record echo and never written.
    bill_id: UUID | None = Field(default=None, exclude=True)


class ExpenseOutput(Output):
    id: UUID
    amount: Decimal
    currency: str
    category: str
    spent_on: date
    note: str
    bill_id: UUID | None


class BudgetInput(Input):
    category: str = Field(min_length=1, max_length=80)
    amount: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    currency: str = CURRENCY


class BudgetOutput(BudgetInput, Output):
    id: UUID


class CategoryLine(BaseModel):
    category: str
    currency: str
    budget_id: UUID | None
    budgeted: Decimal | None
    spent: Decimal
    remaining: Decimal | None


class CurrencyTotal(BaseModel):
    """Totals for one currency. Different currencies are never added together."""

    currency: str
    spent: Decimal
    budgeted: Decimal
    budgeted_spent: Decimal
    remaining: Decimal
    unbudgeted: Decimal


class ExpectedBills(BaseModel):
    currency: str
    amount: Decimal
    count: int


class Summary(BaseModel):
    month: date
    month_end: date
    today: date
    categories: list[CategoryLine]
    totals: list[CurrencyTotal]
    expected_bills: list[ExpectedBills]
    unpaid_bills: list[BillOutput]
