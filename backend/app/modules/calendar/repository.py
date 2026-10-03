from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.modules.calendar.models import CalendarEntry


class CalendarEntryRepository:
    model = CalendarEntry

    def __init__(self, session: Session):
        self.session = session

    def list(self, offset: int, limit: int, period: str, now, today):
        query = select(self.model)
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
        return self.session.get(self.model, record_id)

    def save(self, record):
        self.session.add(record)
        self.session.commit()
        self.session.refresh(record)
        return record

    def delete(self, record):
        self.session.delete(record)
        self.session.commit()
