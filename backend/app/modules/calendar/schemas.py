from datetime import date, timezone
from uuid import UUID

from pydantic import AwareDatetime, Field, model_validator

from app.core.schemas import Input, Output


class CalendarEntryInput(Input):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=10000)
    start: AwareDatetime
    end: AwareDatetime
    all_day: bool = False
    start_date: date | None = None
    end_date: date | None = None

    @model_validator(mode="after")
    def order(self):
        if self.end <= self.start:
            raise ValueError("End must be after start.")
        if self.all_day:
            if not self.start_date or not self.end_date or self.end_date <= self.start_date:
                raise ValueError(
                    "All-day entries require a start date and an exclusive end date after it."
                )
        elif self.start_date or self.end_date:
            raise ValueError("Date fields are only for all-day entries.")
        self.start = self.start.astimezone(timezone.utc)
        self.end = self.end.astimezone(timezone.utc)
        return self


class CalendarEntryOutput(CalendarEntryInput, Output):
    id: UUID
