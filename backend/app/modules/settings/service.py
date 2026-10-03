from app.modules.settings.repository import SettingsRepository
from app.modules.settings.schemas import SettingsInput


class SettingsService:
    def __init__(self, repository: SettingsRepository):
        self.repository = repository

    def get(self):
        return self.repository.get() or SettingsInput()

    def update(self, data: SettingsInput):
        return self.repository.save(data.model_dump())
