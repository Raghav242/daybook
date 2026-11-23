from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base
from app.infrastructure.types import UTCDateTime


class TaskSeries(Base):
    """A recurring task definition. Its occurrences are rows in ``tasks``."""

    __tablename__ = "task_series"
    __table_args__ = (
        UniqueConstraint("id", "user_id", name="uq_task_series_id_user"),
        CheckConstraint(
            "frequency IN ('daily', 'weekly', 'monthly')", name="task_series_frequency"
        ),
        CheckConstraint("repeat_interval >= 1", name="task_series_interval"),
        CheckConstraint("until_date IS NULL OR until_date >= start_date", name="task_series_until"),
        CheckConstraint("priority IN ('low', 'normal', 'high')", name="task_series_priority"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200))
    notes: Mapped[str] = mapped_column(Text, default="")
    priority: Mapped[str] = mapped_column(String(10), default="normal")
    category: Mapped[str] = mapped_column(String(80), default="")
    frequency: Mapped[str] = mapped_column(String(10))
    # "interval" is a PostgreSQL keyword, so the column is named repeat_interval.
    interval: Mapped[int] = mapped_column("repeat_interval", Integer, default=1)
    start_date: Mapped[date] = mapped_column(Date)
    until_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    generated_through: Mapped[date] = mapped_column(Date)

    def occurrence_values(self, day: date):
        return dict(
            title=self.title,
            notes=self.notes,
            priority=self.priority,
            category=self.category,
            due_date=day,
            due_at=None,
            completed=False,
        )


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        CheckConstraint("due_date IS NULL OR due_at IS NULL", name="task_deadline_exclusive"),
        CheckConstraint("priority IN ('low', 'normal', 'high')", name="task_priority"),
        CheckConstraint(
            "series_id IS NULL OR occurrence_date IS NOT NULL", name="task_occurrence_date"
        ),
        UniqueConstraint("series_id", "occurrence_date", name="uq_tasks_series_occurrence"),
        ForeignKeyConstraint(
            ["series_id", "user_id"],
            ["task_series.id", "task_series.user_id"],
            name="fk_tasks_series_owner",
        ),
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
    # Set only by recurrence generation; read-only through the API.
    series_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    occurrence_date: Mapped[date | None] = mapped_column(Date, nullable=True)
