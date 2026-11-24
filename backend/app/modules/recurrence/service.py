from collections.abc import Callable
from datetime import date, datetime, timedelta, timezone
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from app.core.errors import Conflict, NotFound
from app.modules.recurrence.repository import SeriesRepository
from app.modules.recurrence.rules import HORIZON_DAYS, MAX_PER_PASS, Rule, occurrences
from app.modules.recurrence.schemas import RecurrenceFields
from app.modules.settings.service import SettingsService

DAY = timedelta(days=1)


class RecurrenceService:
    """Series lifecycle shared by recurring tasks and recurring bills.

    Occurrences are ordinary task/bill rows linked by (series_id, occurrence_date), which is
    unique, so repeated or concurrent generation never creates duplicates. Completing or
    paying an occurrence only changes that row. ``generated_through`` remembers how far a
    series has been materialized, so an occurrence the user deleted is not recreated.
    """

    def __init__(
        self,
        repository: SeriesRepository,
        settings: SettingsService,
        validate: Callable[[RecurrenceFields, object | None], object] | None = None,
    ):
        """``validate(data, current_series)`` checks feature fields, such as a category."""
        if repository.user_id != settings.repository.user_id:
            raise ValueError("Recurrence and settings must use the same authenticated owner.")
        self.repository = repository
        self.settings = settings
        self.validate = validate

    def today(self, now: datetime | None = None) -> date:
        zone = ZoneInfo(self.settings.get().timezone)
        return (now or datetime.now(timezone.utc)).astimezone(zone).date()

    def _generate(self, series, first: date, through: date):
        rule = Rule(series.frequency, series.interval, series.start_date, series.until_date)
        days = occurrences(rule, max(first, series.start_date), through)
        self.repository.insert_occurrences(
            [
                {
                    "id": uuid4(),
                    "series_id": series.id,
                    "occurrence_date": day,
                    **series.occurrence_values(day),
                }
                for day in days
            ]
        )
        reached = days[-1] if len(days) == MAX_PER_PASS else through
        series.generated_through = max(series.generated_through, reached)

    def ensure(self, today: date | None = None) -> date:
        """Idempotently materialize occurrences through the horizon. Returns today."""
        today = today or self.today()
        through = today + timedelta(days=HORIZON_DAYS)
        pending = self.repository.needing_generation(through)
        for series in pending:
            self._generate(series, series.generated_through + DAY, through)
        if pending:
            self.repository.commit()
        return today

    def get(self, series_id: UUID):
        series = self.repository.get_series(series_id)
        if series is None:
            raise NotFound("This repeating item could not be found.")
        return series

    def create(self, data: RecurrenceFields, today: date | None = None):
        today = today or self.today()
        if self.validate:
            self.validate(data, None)
        # Past dates are not backfilled; the start date still anchors the schedule.
        first = max(data.start_date, today)
        series = self.repository.series_model(
            user_id=self.repository.user_id, generated_through=first - DAY, **data.model_dump()
        )
        self.repository.add(series)
        self._generate(series, first, today + timedelta(days=HORIZON_DAYS))
        self.repository.commit()
        self.repository.refresh(series)
        return series

    def update_future(self, occurrence_id: UUID, data: RecurrenceFields, today=None):
        """Apply ``data`` to this occurrence and every later one in its series.

        Earlier occurrences keep the old definition: the series is split at the cut date.
        Completed/paid occurrences from the cut onward keep their state and move to the
        new definition, which also prevents a duplicate open occurrence on their dates.
        Open overdue occurrences keep their dates and receive the new details. Open
        upcoming occurrences are replaced from the new definition.
        """
        today = today or self.today()
        occurrence = self.repository.get_occurrence(occurrence_id)
        if occurrence is None:
            raise NotFound("This record could not be found.")
        if occurrence.series_id is None:
            raise Conflict("This item does not repeat.")
        series = self.get(occurrence.series_id)
        if self.validate:
            self.validate(data, series)
        cut = min(occurrence.occurrence_date, data.start_date)
        values = data.model_dump()
        if cut <= series.start_date:
            target = series
            for key, value in values.items():
                setattr(target, key, value)
        else:
            series.until_date = cut - DAY
            target = self.repository.series_model(
                user_id=self.repository.user_id, generated_through=cut - DAY, **values
            )
            self.repository.add(target)
        upcoming = max(cut, today)
        done_field = self.repository.done_field
        for row in self.repository.occurrences_from(series.id, cut):
            done = getattr(row, done_field)
            if not done and row.occurrence_date >= upcoming:
                self.repository.delete_occurrence(row)
                continue
            row.series_id = target.id
            if not done:
                for key, value in target.occurrence_values(row.due_date).items():
                    if key not in {"due_date", done_field}:
                        setattr(row, key, value)
        self.repository.flush()
        target.generated_through = upcoming - DAY
        self._generate(target, upcoming, today + timedelta(days=HORIZON_DAYS))
        self.repository.commit()
        self.repository.refresh(target)
        return target

    def delete(self, series_id: UUID, today: date | None = None):
        """Stop repeating. Upcoming open occurrences are removed; history is kept.

        Completed/paid and overdue open occurrences stay as standalone records.
        """
        today = today or self.today()
        series = self.get(series_id)
        done_field = self.repository.done_field
        for row in self.repository.occurrences_from(series.id, date.min):
            if not getattr(row, done_field) and row.occurrence_date >= today:
                self.repository.delete_occurrence(row)
            else:
                row.series_id = None
        self.repository.flush()
        self.repository.delete_series(series)
        self.repository.commit()
