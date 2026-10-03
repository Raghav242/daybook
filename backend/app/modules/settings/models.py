from uuid import UUID

from sqlalchemy import JSON, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base


class Settings(Base):
    __tablename__ = "settings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False, unique=True)
    timezone: Mapped[str] = mapped_column(String(80), default="America/New_York")
    default_currency: Mapped[str] = mapped_column(String(3), default="USD")
    enabled_modules: Mapped[list] = mapped_column(
        JSON, default=lambda: ["tasks", "calendar", "groceries", "bills"]
    )
