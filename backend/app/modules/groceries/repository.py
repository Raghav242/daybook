from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.groceries.models import Grocery


class GroceryRepository:
    model = Grocery

    def __init__(self, session: Session):
        self.session = session

    def list(self, offset: int, limit: int, status: bool | None = None):
        query = select(self.model)
        if status is not None:
            query = query.where(self.model.purchased == status)
        total = self.session.scalar(select(func.count()).select_from(query.subquery()))
        items = self.session.scalars(
            query.order_by(
                self.model.purchased, self.model.category, self.model.name, self.model.id
            )
            .offset(offset)
            .limit(limit)
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
