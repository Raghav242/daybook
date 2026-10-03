from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base
from app.infrastructure.types import UTCDateTime


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        CheckConstraint("due_date IS NULL OR due_at IS NULL", name="task_deadline_exclusive"),
        CheckConstraint("priority IN ('low', 'normal', 'high')", name="task_priority"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200))
    notes: Mapped[str] = mapped_column(Text, default="")
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    due_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True, index=True)
    priority: Mapped[str] = mapped_column(String(10), default="normal")
    category: Mapped[str] = mapped_column(String(80), default="")
    completed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
