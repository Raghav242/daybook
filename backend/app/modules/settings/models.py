from sqlalchemy import JSON, CheckConstraint, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base


class Settings(Base):
    __tablename__ = "settings"
    __table_args__ = (CheckConstraint("id = 1", name="single_local_profile"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    timezone: Mapped[str] = mapped_column(String(80), default="America/New_York")
    default_currency: Mapped[str] = mapped_column(String(3), default="USD")
    enabled_modules: Mapped[list] = mapped_column(
        JSON, default=lambda: ["tasks", "calendar", "groceries", "bills"]
    )
