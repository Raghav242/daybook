from datetime import date
from typing import Literal

from pydantic import Field, model_validator

from app.core.schemas import Input


class RecurrenceFields(Input):
    """Date-only recurrence. Weekly repeats on the start date's weekday."""

    frequency: Literal["daily", "weekly", "monthly"]
    interval: int = Field(default=1, ge=1, le=99)
    start_date: date
    until_date: date | None = None

    @model_validator(mode="after")
    def ordered(self):
        if self.until_date is not None and self.until_date < self.start_date:
            raise ValueError("The repeat end date must be on or after the start date.")
        return self
