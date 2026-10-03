from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.settings.models import Settings


class SettingsRepository:
    def __init__(self, session: Session, user_id: UUID):
        self.session = session
        self.user_id = user_id

    def get(self):
        return self.session.scalar(select(Settings).where(Settings.user_id == self.user_id))

    def save(self, data):
        record = self.get() or Settings(user_id=self.user_id)
        for key, value in data.items():
            setattr(record, key, value)
        self.session.add(record)
        self.session.commit()
        self.session.refresh(record)
        return record
