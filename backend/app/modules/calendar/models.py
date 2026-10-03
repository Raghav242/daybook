from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, Date, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base
from app.infrastructure.types import UTCDateTime


class CalendarEntry(Base):
    __tablename__ = "calendar"
    __table_args__ = (
        CheckConstraint('"end" > start', name="event_time_order"),
        CheckConstraint(
            "(all_day = false AND start_date IS NULL AND end_date IS NULL) OR (all_day = true AND start_date IS NOT NULL AND end_date IS NOT NULL AND end_date > start_date)",
            name="event_date_order",
        ),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    start: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    end: Mapped[datetime] = mapped_column(UTCDateTime())
    all_day: Mapped[bool] = mapped_column(Boolean, default=False)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
