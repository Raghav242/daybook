from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from app.core.schemas import Input, Output


class BillInput(Input):
    name: str = Field(min_length=1, max_length=200)
    amount: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$")
    due_date: date
    paid: bool = False


class BillOutput(BillInput, Output):
    id: UUID
