from datetime import timedelta
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.modules.bills.models import Bill
from app.modules.calendar.models import CalendarEntry
from app.modules.groceries.models import Grocery
from app.modules.tasks.models import Task


class DashboardRepository:
    def __init__(self, session: Session, user_id: UUID):
        self.session = session
        self.user_id = user_id

    def summary(self, today, start, end, horizon):
        task_due = or_(Task.due_date <= today, Task.due_at < end)
        task_overdue = or_(Task.due_date < today, Task.due_at < start)
        active = Task.completed.is_(False)
        counts = {
            "tasks_today": self.session.scalar(
                select(func.count())
                .select_from(Task)
                .where(Task.user_id == self.user_id, active, task_due)
            ),
            "tasks_overdue": self.session.scalar(
                select(func.count())
                .select_from(Task)
                .where(Task.user_id == self.user_id, active, task_overdue)
            ),
            "groceries_remaining": self.session.scalar(
                select(func.count())
                .select_from(Grocery)
                .where(Grocery.user_id == self.user_id, Grocery.purchased.is_(False))
            ),
            "bills_overdue": self.session.scalar(
                select(func.count())
                .select_from(Bill)
                .where(Bill.user_id == self.user_id, Bill.paid.is_(False), Bill.due_date < today)
            ),
        }
        # Later occurrences of repeating tasks appear under recurring items instead.
        not_later_occurrence = or_(Task.series_id.is_(None), Task.due_date <= today)
        tasks = self.session.scalars(
            select(Task)
            .where(Task.user_id == self.user_id, active, not_later_occurrence)
            .order_by(
                task_due.desc().nullslast(),
                (Task.priority == "high").desc(),
                Task.due_date.asc().nullslast(),
                Task.due_at.asc().nullslast(),
                Task.title,
                Task.id,
            )
            .limit(6)
        ).all()
        agenda_condition = or_(
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
        agenda = self.session.scalars(
            select(CalendarEntry)
            .where(CalendarEntry.user_id == self.user_id, agenda_condition)
            .order_by(CalendarEntry.start, CalendarEntry.id)
            .limit(8)
        ).all()
        upcoming = self.session.scalars(
            select(CalendarEntry)
            .where(
                CalendarEntry.user_id == self.user_id,
                or_(
                    and_(CalendarEntry.all_day.is_(False), CalendarEntry.start >= end),
                    and_(CalendarEntry.all_day.is_(True), CalendarEntry.start_date > today),
                ),
            )
            .order_by(CalendarEntry.start, CalendarEntry.id)
            .limit(3)
        ).all()
        groceries = self.session.scalars(
            select(Grocery)
            .where(Grocery.user_id == self.user_id, Grocery.purchased.is_(False))
            .order_by(Grocery.category, Grocery.name, Grocery.id)
            .limit(5)
        ).all()
        bills = self.session.scalars(
            select(Bill)
            .where(Bill.user_id == self.user_id, Bill.paid.is_(False), Bill.due_date <= horizon)
            .order_by(Bill.due_date, Bill.id)
            .limit(5)
        ).all()
        totals = self.session.execute(
            select(Bill.currency, func.sum(Bill.amount))
            .where(Bill.user_id == self.user_id, Bill.paid.is_(False), Bill.due_date <= horizon)
            .group_by(Bill.currency)
            .order_by(Bill.currency)
        ).all()
        return dict(
            counts=counts,
            recurring=self.recurring(today, today + timedelta(days=7)),
            tasks=tasks,
            agenda=agenda,
            upcoming=upcoming,
            groceries=groceries,
            bills=bills,
            bill_totals={currency: format(amount, ".2f") for currency, amount in totals},
        )

    def recurring(self, today, through, limit=6):
        """Open occurrences of repeating tasks and bills, overdue first, through ``through``."""
        tasks = self.session.scalars(
            select(Task)
            .where(
                Task.user_id == self.user_id,
                Task.series_id.is_not(None),
                Task.completed.is_(False),
                Task.due_date <= through,
            )
            .order_by(Task.due_date, Task.title, Task.id)
            .limit(limit)
        ).all()
        bills = self.session.scalars(
            select(Bill)
            .where(
                Bill.user_id == self.user_id,
                Bill.series_id.is_not(None),
                Bill.paid.is_(False),
                Bill.due_date <= through,
            )
            .order_by(Bill.due_date, Bill.name, Bill.id)
            .limit(limit)
        ).all()
        items = [
            dict(
                kind="task", id=t.id, title=t.title, due_date=t.due_date, amount=None, currency=None
            )
            for t in tasks
        ] + [
            dict(
                kind="bill",
                id=b.id,
                title=b.name,
                due_date=b.due_date,
                amount=b.amount,
                currency=b.currency,
            )
            for b in bills
        ]
        items.sort(key=lambda item: (item["due_date"], item["kind"], item["title"]))
        for item in items:
            item["overdue"] = item["due_date"] < today
        return items[:limit]
