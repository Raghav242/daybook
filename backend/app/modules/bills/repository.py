from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import NotFound
from app.modules.bills.models import Bill


class BillRepository:
    model = Bill

    def __init__(self, session: Session, user_id: UUID):
        self.session = session
        self.user_id = user_id

    def list(self, offset: int, limit: int, status: bool | None = None):
        query = select(self.model).where(self.model.user_id == self.user_id)
        if status is not None:
            query = query.where(self.model.paid == status)
        total = self.session.scalar(select(func.count()).select_from(query.subquery()))
        items = self.session.scalars(
            query.order_by(self.model.paid, self.model.due_date, self.model.name, self.model.id)
            .offset(offset)
            .limit(limit)
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
