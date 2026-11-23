from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import NotFound
from app.modules.bills.models import Bill, BillSeries
from app.modules.budget.models import Expense
from app.modules.recurrence.repository import SeriesRepository


def detach_expense(session: Session, bill: Bill):
    """Keep recorded spending when its bill is deleted; only the link is removed."""
    session.execute(
        update(Expense)
        .where(Expense.bill_id == bill.id, Expense.user_id == bill.user_id)
        .values(bill_id=None)
    )


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

    def pay(self, bill: Bill, expense: Expense | None):
        """Mark paid and optionally link one expense, atomically.

        Returns False when a concurrent request already linked an expense; the unique
        bill_id constraint guarantees a bill is never counted as spending twice.
        """
        if bill.user_id != self.user_id or (expense and expense.user_id != self.user_id):
            raise NotFound("This record could not be found.")
        bill.paid = True
        self.session.add(bill)
        if expense:
            self.session.add(expense)
        try:
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            return False
        return True

    def delete(self, record):
        if record.user_id != self.user_id:
            raise NotFound("This record could not be found.")
        detach_expense(self.session, record)
        self.session.delete(record)
        self.session.commit()


class BillSeriesRepository(SeriesRepository):
    series_model = BillSeries
    occurrence_model = Bill
    done_field = "paid"

    def delete_occurrence(self, record):
        detach_expense(self.session, record)
        self.session.delete(record)
