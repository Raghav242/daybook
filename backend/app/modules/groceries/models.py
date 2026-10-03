from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base


class Grocery(Base):
    __tablename__ = "groceries"
    __table_args__ = (CheckConstraint("quantity > 0", name="grocery_quantity_positive"),)
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(200))
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=1)
    unit: Mapped[str] = mapped_column(String(40), default="")
    category: Mapped[str] = mapped_column(String(80), default="")
    purchased: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
