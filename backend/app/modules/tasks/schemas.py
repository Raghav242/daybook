from datetime import date, timezone
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, Field, model_validator

from app.core.schemas import Input, Output


class TaskInput(Input):
    title: str = Field(min_length=1, max_length=200)
    notes: str = Field(default="", max_length=10000)
    due_date: date | None = None
    due_at: AwareDatetime | None = None
    priority: Literal["low", "normal", "high"] = "normal"
    category: str = Field(default="", max_length=80)
    completed: bool = False

    @model_validator(mode="after")
    def deadline(self):
        if self.due_date and self.due_at:
            raise ValueError("Choose a date or a timed deadline, not both.")
        if self.due_at:
            self.due_at = self.due_at.astimezone(timezone.utc)
        return self


class TaskOutput(TaskInput, Output):
    id: UUID
