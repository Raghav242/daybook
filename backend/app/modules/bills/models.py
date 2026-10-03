from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base


class Bill(Base):
    __tablename__ = "bills"
    __table_args__ = (CheckConstraint("amount >= 0", name="bill_amount_nonnegative"),)
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200))
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    due_date: Mapped[date] = mapped_column(Date, index=True)
    paid: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
