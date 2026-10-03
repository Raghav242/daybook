from decimal import Decimal
from uuid import UUID

from pydantic import Field

from app.core.schemas import Input, Output


class GroceryInput(Input):
    name: str = Field(min_length=1, max_length=200)
    quantity: Decimal = Field(default=Decimal("1"), gt=0, max_digits=12, decimal_places=3)
    unit: str = Field(default="", max_length=40)
    category: str = Field(default="", max_length=80)
    purchased: bool = False


class GroceryOutput(GroceryInput, Output):
    id: UUID
