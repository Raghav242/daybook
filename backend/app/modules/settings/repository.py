from sqlalchemy.orm import Session

from app.modules.settings.models import Settings


class SettingsRepository:
    def __init__(self, session: Session):
        self.session = session

    def get(self):
        return self.session.get(Settings, 1)

    def save(self, data):
        record = self.get() or Settings(id=1)
        for key, value in data.items():
            setattr(record, key, value)
        self.session.add(record)
        self.session.commit()
        self.session.refresh(record)
        return record
