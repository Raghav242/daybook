from app.core.errors import NotFound
from app.modules.settings.repository import SettingsRepository
from app.modules.settings.schemas import SettingsInput


class SettingsService:
    def __init__(self, repository: SettingsRepository):
        self.repository = repository

    def get(self):
        record = self.repository.get()
        if record is not None and record.user_id != self.repository.user_id:
            raise NotFound("This record could not be found.")
        return record or SettingsInput()

    def update(self, data: SettingsInput):
        return self.repository.save(data.model_dump())
