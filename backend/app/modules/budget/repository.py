from datetime import date
from uuid import UUID

from sqlalchemy import func, literal, null, select, union_all
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import Conflict, NotFound
from app.modules.bills.models import Bill
from app.modules.budget.models import Budget, Expense, Income
from app.modules.categories.models import Category


def _month(column, first: date | None, last: date | None):
    return (column >= first, column <= last) if first and last else ()


class BudgetRepository:
    """Owner-scoped expenses, income, budgets and the bill reads the monthly summary needs."""

    def __init__(self, session: Session, user_id: UUID):
        self.session = session
        self.user_id = user_id

    def _page(self, model, order, offset, limit, *conditions):
        query = select(model).where(model.user_id == self.user_id, *conditions)
        total = self.session.scalar(select(func.count()).select_from(query.subquery()))
        items = self.session.scalars(query.order_by(*order).offset(offset).limit(limit)).all()
        return {"items": items, "total": total, "offset": offset, "limit": limit}

    def list_expenses(self, offset: int, limit: int, first: date | None, last: date | None):
        order = (Expense.spent_on.desc(), Expense.id)
        return self._page(Expense, order, offset, limit, *_month(Expense.spent_on, first, last))

    def list_income(self, offset: int, limit: int, first: date | None, last: date | None):
        order = (Income.received_on.desc(), Income.id)
        return self._page(Income, order, offset, limit, *_month(Income.received_on, first, last))

    def transactions(self, kind: str, offset: int, limit: int, first: date, last: date):
        """Expenses and income in one date-ordered page; amounts keep their own sign rules."""

        def rows(model, label, day, bill):
            return (
                select(
                    literal(label).label("kind"),
                    model.id.label("id"),
                    model.amount.label("amount"),
                    model.currency.label("currency"),
                    model.category_id.label("category_id"),
                    Category.name.label("category"),
                    day.label("date"),
                    model.note.label("note"),
                    bill.label("bill_id"),
                )
                .join(
                    Category,
                    (Category.id == model.category_id) & (Category.user_id == model.user_id),
                )
                .where(model.user_id == self.user_id, day >= first, day <= last)
            )

        parts = []
        if kind in ("all", "expense"):
            parts.append(rows(Expense, "expense", Expense.spent_on, Expense.bill_id))
        if kind in ("all", "income"):
            parts.append(rows(Income, "income", Income.received_on, null()))
        combined = (union_all(*parts) if len(parts) > 1 else parts[0]).subquery()
        total = self.session.scalar(select(func.count()).select_from(combined))
        items = self.session.execute(
            select(combined)
            .order_by(combined.c.date.desc(), combined.c.kind, combined.c.id)
            .offset(offset)
            .limit(limit)
        ).mappings()
        return {"items": list(items), "total": total, "offset": offset, "limit": limit}

    def get_expense(self, record_id: UUID):
        return self.session.scalar(
            select(Expense).where(Expense.id == record_id, Expense.user_id == self.user_id)
        )

    def get_income(self, record_id: UUID):
        return self.session.scalar(
            select(Income).where(Income.id == record_id, Income.user_id == self.user_id)
        )

    def list_budgets(self):
        return self.session.scalars(
            select(Budget)
            .where(Budget.user_id == self.user_id)
            .order_by(Budget.currency, Budget.category, Budget.id)
        ).all()

    def get_budget(self, record_id: UUID):
        return self.session.scalar(
            select(Budget).where(Budget.id == record_id, Budget.user_id == self.user_id)
        )

    def find_budget(self, category_id: UUID, currency: str):
        return self.session.scalar(
            select(Budget).where(
                Budget.user_id == self.user_id,
                Budget.category_id == category_id,
                Budget.currency == currency,
            )
        )

    def spending(self, first: date, last: date):
        """Recorded spending per (category, currency), summed exactly in SQL numerics."""
        return self.session.execute(
            select(
                Expense.category_id,
                Expense.currency,
                func.min(Category.name),
                func.sum(Expense.amount),
            )
            .join(
                Category,
                (Category.id == Expense.category_id) & (Category.user_id == Expense.user_id),
            )
            .where(
                Expense.user_id == self.user_id,
                Expense.spent_on >= first,
                Expense.spent_on <= last,
            )
            .group_by(Expense.category_id, Expense.currency)
        ).all()

    def income_totals(self, first: date, last: date):
        """Recorded income per currency for the month."""
        return self.session.execute(
            select(Income.currency, func.sum(Income.amount))
            .where(
                Income.user_id == self.user_id,
                Income.received_on >= first,
                Income.received_on <= last,
            )
            .group_by(Income.currency)
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
