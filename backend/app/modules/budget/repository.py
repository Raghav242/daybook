from datetime import date
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import Conflict, NotFound
from app.modules.bills.models import Bill
from app.modules.budget.models import Budget, Expense


class BudgetRepository:
    """Owner-scoped expenses, budgets and the bill reads the monthly summary needs."""

    def __init__(self, session: Session, user_id: UUID):
        self.session = session
        self.user_id = user_id

    def list_expenses(self, offset: int, limit: int, first: date | None, last: date | None):
        query = select(Expense).where(Expense.user_id == self.user_id)
        if first and last:
            query = query.where(Expense.spent_on >= first, Expense.spent_on <= last)
        total = self.session.scalar(select(func.count()).select_from(query.subquery()))
        items = self.session.scalars(
            query.order_by(Expense.spent_on.desc(), Expense.category, Expense.id)
            .offset(offset)
            .limit(limit)
        ).all()
        return {"items": items, "total": total, "offset": offset, "limit": limit}

    def get_expense(self, record_id: UUID):
        return self.session.scalar(
            select(Expense).where(Expense.id == record_id, Expense.user_id == self.user_id)
        )

    def list_budgets(self):
        return self.session.scalars(
            select(Budget)
            .where(Budget.user_id == self.user_id)
            .order_by(Budget.currency, Budget.category_key, Budget.id)
        ).all()

    def get_budget(self, record_id: UUID):
        return self.session.scalar(
            select(Budget).where(Budget.id == record_id, Budget.user_id == self.user_id)
        )

    def find_budget(self, key: str, currency: str):
        return self.session.scalar(
            select(Budget).where(
                Budget.user_id == self.user_id,
                Budget.category_key == key,
                Budget.currency == currency,
            )
        )

    def spending(self, first: date, last: date):
        """Recorded spending per (category, currency), summed exactly in SQL numerics."""
        return self.session.execute(
            select(
                Expense.category_key,
                Expense.currency,
                func.min(Expense.category),
                func.sum(Expense.amount),
            )
            .where(
                Expense.user_id == self.user_id,
                Expense.spent_on >= first,
                Expense.spent_on <= last,
            )
            .group_by(Expense.category_key, Expense.currency)
        ).all()

    def expected_bills(self, first: date, last: date):
        unpaid = (
            Bill.user_id == self.user_id,
            Bill.paid.is_(False),
            Bill.due_date >= first,
            Bill.due_date <= last,
        )
        totals = self.session.execute(
            select(Bill.currency, func.sum(Bill.amount), func.count())
            .where(*unpaid)
            .group_by(Bill.currency)
            .order_by(Bill.currency)
        ).all()
        bills = self.session.scalars(
            select(Bill).where(*unpaid).order_by(Bill.due_date, Bill.name, Bill.id).limit(8)
        ).all()
        return totals, bills

    def save(self, record):
        if record.user_id != self.user_id:
            raise NotFound("This record could not be found.")
        self.session.add(record)
        try:
            self.session.commit()
        except IntegrityError:
            # A concurrent request created the same category budget.
            self.session.rollback()
            raise Conflict("That budget already exists. Refresh and try again.") from None
        self.session.refresh(record)
        return record

    def delete(self, record):
        if record.user_id != self.user_id:
            raise NotFound("This record could not be found.")
        self.session.delete(record)
        self.session.commit()
