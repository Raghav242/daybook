from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.core.schemas import Input, Output
from app.modules.bills.schemas import BillOutput

Money = Field(gt=0, max_digits=14, decimal_places=2)
CURRENCY = Field(pattern=r"^[A-Z]{3}$")
# Display names are server-managed; accepted for full-record echo and never written.
READ_ONLY = Field(default=None, exclude=True)


class ExpenseInput(Input):
    amount: Decimal = Money
    currency: str = CURRENCY
    category_id: UUID
    spent_on: date
    note: str = Field(default="", max_length=500)
    category: str | None = READ_ONLY
    # Set only when a bill is paid; accepted for full-record echo and never written.
    bill_id: UUID | None = READ_ONLY


class ExpenseOutput(Output):
    id: UUID
    amount: Decimal
    currency: str
    category_id: UUID
    category: str
    spent_on: date
    note: str
    bill_id: UUID | None


class IncomeInput(Input):
    amount: Decimal = Money
    currency: str = CURRENCY
    category_id: UUID
    received_on: date
    note: str = Field(default="", max_length=500)
    category: str | None = READ_ONLY


class IncomeOutput(Output):
    id: UUID
    amount: Decimal
    currency: str
    category_id: UUID
    category: str
    received_on: date
    note: str


class BudgetInput(Input):
    category_id: UUID
    amount: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    currency: str = CURRENCY
    category: str | None = READ_ONLY


class BudgetOutput(Output):
    id: UUID
    category_id: UUID
    category: str
    amount: Decimal
    currency: str


class Transaction(BaseModel):
    """One expense or income row for the combined, date-ordered transactions list."""

    kind: Literal["expense", "income"]
    id: UUID
    amount: Decimal
    currency: str
    category_id: UUID
    category: str
    date: date
    note: str
    bill_id: UUID | None


class TransactionPage(BaseModel):
    items: list[Transaction]
    total: int
    offset: int
    limit: int


class CategoryLine(BaseModel):
    category_id: UUID
    category: str
    currency: str
    budget_id: UUID | None
    budgeted: Decimal | None
    spent: Decimal
    remaining: Decimal | None


class CurrencyTotal(BaseModel):
    """Totals for one currency. Different currencies are never added together.

    ``net`` is recorded income minus recorded expenses for the month: a cash-flow figure,
    not a balance. Unpaid bills are not included.
    """

    currency: str
    income: Decimal
    spent: Decimal
    net: Decimal
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
