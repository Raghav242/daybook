from decimal import Decimal
from uuid import UUID

from pydantic import Field

from app.core.schemas import Input, Output


class GroceryInput(Input):
    name: str = Field(min_length=1, max_length=200)
    quantity: Decimal = Field(default=Decimal("1"), gt=0, max_digits=12, decimal_places=3)
    unit: str = Field(default="", max_length=40)
    category_id: UUID | None = None
    purchased: bool = False
    # Read-only display name of the category; never written.
    category: str | None = Field(default=None, exclude=True)


class GroceryOutput(Output):
    id: UUID
    name: str
    quantity: Decimal
    unit: str
    category_id: UUID | None = None
    category: str | None = None
    purchased: bool
