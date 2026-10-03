from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import NotFound
from app.modules.calendar.models import CalendarEntry


class CalendarEntryRepository:
    model = CalendarEntry

    def __init__(self, session: Session, user_id: UUID):
        self.session = session
        self.user_id = user_id

    def list(self, offset: int, limit: int, period: str, now, today):
        query = select(self.model).where(self.model.user_id == self.user_id)
        upcoming = or_(
            and_(self.model.all_day.is_(False), self.model.end > now),
            and_(self.model.all_day.is_(True), self.model.end_date > today),
        )
        if period == "upcoming":
            query = query.where(upcoming)
        elif period == "past":
            query = query.where(~upcoming)
        total = self.session.scalar(select(func.count()).select_from(query.subquery()))
        order = self.model.start.desc() if period == "past" else self.model.start.asc()
        items = self.session.scalars(
            query.order_by(order, self.model.title, self.model.id).offset(offset).limit(limit)
        ).all()
        return {"items": items, "total": total, "offset": offset, "limit": limit}

    def get(self, record_id: UUID):
        return self.session.scalar(
            select(self.model).where(self.model.id == record_id, self.model.user_id == self.user_id)
        )

    def save(self, record):
        if record.user_id != self.user_id:
            raise NotFound("This record could not be found.")
        self.session.add(record)
        self.session.commit()
        self.session.refresh(record)
        return record

    def delete(self, record):
        if record.user_id != self.user_id:
            raise NotFound("This record could not be found.")
        self.session.delete(record)
        self.session.commit()
