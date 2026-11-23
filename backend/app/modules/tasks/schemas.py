from datetime import date, timezone
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, Field, model_validator

from app.core.schemas import Input, Output
from app.modules.recurrence.schemas import RecurrenceFields


class TaskInput(Input):
    title: str = Field(min_length=1, max_length=200)
    notes: str = Field(default="", max_length=10000)
    due_date: date | None = None
    due_at: AwareDatetime | None = None
    priority: Literal["low", "normal", "high"] = "normal"
    category: str = Field(default="", max_length=80)
    completed: bool = False
    # Read-only recurrence links. Accepted so clients can echo a full record back on PUT,
    # but excluded from writes: series membership is only changed by the server.
    series_id: UUID | None = Field(default=None, exclude=True)
    occurrence_date: date | None = Field(default=None, exclude=True)

    @model_validator(mode="after")
    def deadline(self):
        if self.due_date and self.due_at:
            raise ValueError("Choose a date or a timed deadline, not both.")
        if self.due_at:
            self.due_at = self.due_at.astimezone(timezone.utc)
        return self


class TaskOutput(Output):
    id: UUID
    title: str
    notes: str
    due_date: date | None
    due_at: AwareDatetime | None
    priority: Literal["low", "normal", "high"]
    category: str
    completed: bool
    series_id: UUID | None = None
    occurrence_date: date | None = None


class TaskSeriesInput(RecurrenceFields):
    title: str = Field(min_length=1, max_length=200)
    notes: str = Field(default="", max_length=10000)
    priority: Literal["low", "normal", "high"] = "normal"
    category: str = Field(default="", max_length=80)


class TaskSeriesOutput(TaskSeriesInput, Output):
    id: UUID
