from datetime import timedelta
from uuid import UUID

from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.orm import Session

from app.modules.bills.models import Bill
from app.modules.budget.models import Expense, Income
from app.modules.calendar.models import CalendarEntry
from app.modules.groceries.models import Grocery
from app.modules.meals.models import Recipe
from app.modules.tasks.models import Task

UPCOMING_DAYS = 7


class DashboardRepository:
    """Owner-scoped reads for the Today screen. Every query filters by ``user_id``."""

    def __init__(self, session: Session, user_id: UUID):
        self.session = session
        self.user_id = user_id

    def _count(self, model, *conditions):
        return self.session.scalar(
            select(func.count())
            .select_from(model)
            .where(model.user_id == self.user_id, *conditions)
        )

    def _tasks(self, *conditions, limit):
        return self.session.scalars(
            select(Task)
            .where(Task.user_id == self.user_id, Task.completed.is_(False), *conditions)
            .order_by(
                Task.due_date.asc().nullslast(),
                Task.due_at.asc().nullslast(),
                (Task.priority == "high").desc(),
                Task.title,
                Task.id,
            )
            .limit(limit)
        ).all()

    def has_records(self) -> bool:
        """Whether the account has anything at all, to tell a new account from a quiet day."""
        models = (Task, CalendarEntry, Grocery, Bill, Expense, Income, Recipe)
        return any(
            self.session.scalar(select(exists().where(model.user_id == self.user_id)))
            for model in models
        )

    def summary(self, today, start, end, horizon):
        """``start``/``end`` bound today in UTC; ``horizon`` limits the unpaid-bill total."""
        soon = today + timedelta(days=UPCOMING_DAYS)
        due_today = or_(Task.due_date == today, and_(Task.due_at >= start, Task.due_at < end))
        overdue = or_(Task.due_date < today, Task.due_at < start)
        unscheduled = and_(Task.due_date.is_(None), Task.due_at.is_(None))
        upcoming_task = or_(
            and_(Task.due_date > today, Task.due_date <= soon),
            and_(Task.due_at >= end, Task.due_at < end + timedelta(days=UPCOMING_DAYS)),
        )
        open_task = Task.completed.is_(False)
        unpaid = Bill.paid.is_(False)
        counts = {
            "tasks_today": self._count(Task, open_task, due_today),
            "tasks_overdue": self._count(Task, open_task, overdue),
            "tasks_unscheduled": self._count(Task, open_task, unscheduled),
            "groceries_remaining": self._count(Grocery, Grocery.purchased.is_(False)),
            "bills_overdue": self._count(Bill, unpaid, Bill.due_date < today),
        }
        events_today = or_(
            and_(
                CalendarEntry.all_day.is_(False),
                CalendarEntry.start < end,
                CalendarEntry.end > start,
            ),
            and_(
                CalendarEntry.all_day.is_(True),
                CalendarEntry.start_date <= today,
                CalendarEntry.end_date > today,
            ),
        )
        events_soon = or_(
            and_(
                CalendarEntry.all_day.is_(False),
                CalendarEntry.start >= end,
                CalendarEntry.start < end + timedelta(days=UPCOMING_DAYS),
            ),
            and_(
                CalendarEntry.all_day.is_(True),
                CalendarEntry.start_date > today,
                CalendarEntry.start_date <= soon,
            ),
        )

        def events(condition, limit):
            return self.session.scalars(
                select(CalendarEntry)
                .where(CalendarEntry.user_id == self.user_id, condition)
                .order_by(CalendarEntry.start, CalendarEntry.id)
                .limit(limit)
            ).all()

        def bills(condition, limit):
            return self.session.scalars(
                select(Bill)
                .where(Bill.user_id == self.user_id, unpaid, condition)
                .order_by(Bill.due_date, Bill.name, Bill.id)
                .limit(limit)
            ).all()

        totals = self.session.execute(
            select(Bill.currency, func.sum(Bill.amount))
            .where(Bill.user_id == self.user_id, unpaid, Bill.due_date <= horizon)
            .group_by(Bill.currency)
            .order_by(Bill.currency)
        ).all()
        return dict(
            counts=counts,
            has_records=self.has_records(),
            overdue_tasks=self._tasks(overdue, limit=5),
            due_today=self._tasks(due_today, limit=12),
            unscheduled=self._tasks(unscheduled, limit=3),
            upcoming_tasks=self._tasks(upcoming_task, limit=6),
            agenda=events(events_today, 12),
            upcoming=events(events_soon, 6),
            groceries=self.session.scalars(
                select(Grocery)
                .where(Grocery.user_id == self.user_id, Grocery.purchased.is_(False))
                .order_by(Grocery.category.asc().nullslast(), Grocery.name, Grocery.id)
                .limit(5)
            ).all(),
            overdue_bills=bills(Bill.due_date < today, 5),
            upcoming_bills=bills(and_(Bill.due_date >= today, Bill.due_date <= soon), 6),
            bill_totals={currency: format(amount, ".2f") for currency, amount in totals},
        )
