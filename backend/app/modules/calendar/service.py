from datetime import datetime, timezone
from uuid import UUID
from zoneinfo import ZoneInfo

from app.core.errors import NotFound
from app.modules.calendar.models import CalendarEntry
from app.modules.calendar.repository import CalendarEntryRepository
from app.modules.calendar.schemas import CalendarEntryInput
from app.modules.settings.service import SettingsService


class CalendarEntryService:
    def __init__(self, repository: CalendarEntryRepository, settings: SettingsService):
        self.repository = repository
        self.settings = settings

    def list(self, offset: int, limit: int, period: str):
        now = datetime.now(timezone.utc)
        today = now.astimezone(ZoneInfo(self.settings.get().timezone)).date()
        return self.repository.list(offset, limit, period, now, today)

    def get(self, record_id: UUID):
        record = self.repository.get(record_id)
        if record is None:
            raise NotFound("This record could not be found.")
        return record

    def create(self, data: CalendarEntryInput):
        return self.repository.save(CalendarEntry(**data.model_dump()))

    def update(self, record_id: UUID, data: CalendarEntryInput):
        record = self.get(record_id)
        for key, value in data.model_dump().items():
            setattr(record, key, value)
        return self.repository.save(record)

    def delete(self, record_id: UUID):
        self.repository.delete(self.get(record_id))
