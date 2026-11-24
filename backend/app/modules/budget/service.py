from calendar import monthrange
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

from app.core.errors import Conflict, NotFound
from app.modules.budget.models import Budget, Expense, Income
from app.modules.budget.repository import BudgetRepository
from app.modules.budget.schemas import BudgetInput, ExpenseInput, IncomeInput
from app.modules.categories.service import CategoryService
from app.modules.recurrence.service import RecurrenceService
from app.modules.settings.service import SettingsService

CENT = Decimal("0.01")
ZERO = Decimal("0.00")


def money(value) -> Decimal:
    return Decimal(value or 0).quantize(CENT)


def month_bounds(month: date) -> tuple[date, date]:
    first = month.replace(day=1)
    return first, first.replace(day=monthrange(first.year, first.month)[1])


def summarize(budgets, spending, income=()) -> tuple[list[dict], list[dict]]:
    """Pure money arithmetic. Every figure is grouped by currency; none are converted.

    - A category's remaining amount is its budget minus its spending.
    - A currency's remaining amount is the total budget minus spending in budgeted
      categories; spending without a budget is reported separately as ``unbudgeted``.
    - ``net`` is recorded income minus recorded expenses. Income never reduces reported
      spending and never changes a budget limit.

    ``spending`` rows are (category_id, currency, category name, total) and ``income`` rows
    are (currency, total).
    """
    spent = {(cid, currency): (name, money(total)) for cid, currency, name, total in spending}
    lines, totals = [], {}

    def total_for(currency):
        return totals.setdefault(
            currency,
            dict(currency=currency, income=ZERO, spent=ZERO, budgeted=ZERO, budgeted_spent=ZERO),
        )

    for budget in budgets:
        _, amount = spent.pop((budget.category_id, budget.currency), (None, ZERO))
        limit = money(budget.amount)
        lines.append(
            dict(
                category_id=budget.category_id,
                category=budget.category,
                currency=budget.currency,
                budget_id=budget.id,
                budgeted=limit,
                spent=amount,
                remaining=limit - amount,
            )
        )
        total = total_for(budget.currency)
        total["budgeted"] += limit
        total["budgeted_spent"] += amount
        total["spent"] += amount
    for (category_id, currency), (name, amount) in spent.items():
        lines.append(
            dict(
                category_id=category_id,
                category=name,
                currency=currency,
                budget_id=None,
                budgeted=None,
                spent=amount,
                remaining=None,
            )
        )
        total_for(currency)["spent"] += amount
    for currency, amount in income:
        total_for(currency)["income"] += money(amount)
    for total in totals.values():
        total["remaining"] = total["budgeted"] - total["budgeted_spent"]
        total["unbudgeted"] = total["spent"] - total["budgeted_spent"]
        total["net"] = total["income"] - total["spent"]
    lines.sort(
        key=lambda line: (line["currency"], line["budgeted"] is None, line["category"].casefold())
    )
    return lines, [totals[currency] for currency in sorted(totals)]


class BudgetService:
    def __init__(
        self,
        repository: BudgetRepository,
        settings: SettingsService,
        categories: CategoryService,
        bill_recurrence: RecurrenceService | None = None,
    ):
        owners = {
            repository.user_id,
            settings.repository.user_id,
            categories.repository.user_id,
        }
        if bill_recurrence:
            owners.add(bill_recurrence.repository.user_id)
        if len(owners) != 1:
            raise ValueError("Budget services must use the same authenticated owner.")
        self.repository = repository
        self.settings = settings
        self.categories = categories
        self.bill_recurrence = bill_recurrence

    def today(self, now: datetime | None = None) -> date:
        zone = ZoneInfo(self.settings.get().timezone)
        return (now or datetime.now(timezone.utc)).astimezone(zone).date()

    def summary(self, month: date | None = None, today: date | None = None):
        today = today or self.today()
        first, last = month_bounds(month or today)
        if self.bill_recurrence:
            self.bill_recurrence.ensure(today)
        categories, totals = summarize(
            self.repository.list_budgets(),
            self.repository.spending(first, last),
            self.repository.income_totals(first, last),
        )
        bill_totals, bills = self.repository.expected_bills(first, last)
        return dict(
            month=first,
            month_end=last,
            today=today,
            categories=categories,
            totals=totals,
            expected_bills=[
                dict(currency=currency, amount=money(amount), count=count)
                for currency, amount, count in bill_totals
            ],
            unpaid_bills=bills,
        )

    def transactions(self, kind: str, offset: int, limit: int, month: date | None):
        first, last = month_bounds(month or self.today())
        return self.repository.transactions(kind, offset, limit, first, last)

    # Expenses
    def list_expenses(self, offset: int, limit: int, month: date | None):
        first, last = month_bounds(month) if month else (None, None)
        return self.repository.list_expenses(offset, limit, first, last)

    def get_expense(self, record_id: UUID):
        record = self.repository.get_expense(record_id)
        if record is None:
            raise NotFound("This expense could not be found.")
        return record

    def create_expense(self, data: ExpenseInput):
        self.categories.require("expense", data.category_id)
        return self.repository.save(Expense(user_id=self.repository.user_id, **data.model_dump()))

    def update_expense(self, record_id: UUID, data: ExpenseInput):
        record = self.get_expense(record_id)
        self.categories.require("expense", data.category_id, current=record.category_id)
        for key, value in data.model_dump().items():
            setattr(record, key, value)
        return self.repository.save(record)

    def delete_expense(self, record_id: UUID):
        """Delete recorded spending. A linked bill stays paid."""
        self.repository.delete(self.get_expense(record_id))

    # Income
    def list_income(self, offset: int, limit: int, month: date | None):
        first, last = month_bounds(month) if month else (None, None)
        return self.repository.list_income(offset, limit, first, last)

    def get_income(self, record_id: UUID):
        record = self.repository.get_income(record_id)
        if record is None:
            raise NotFound("This income could not be found.")
        return record

    def create_income(self, data: IncomeInput):
        self.categories.require("income", data.category_id)
        return self.repository.save(Income(user_id=self.repository.user_id, **data.model_dump()))

    def update_income(self, record_id: UUID, data: IncomeInput):
        record = self.get_income(record_id)
        self.categories.require("income", data.category_id, current=record.category_id)
        for key, value in data.model_dump().items():
            setattr(record, key, value)
        return self.repository.save(record)

    def delete_income(self, record_id: UUID):
        self.repository.delete(self.get_income(record_id))

    # Budgets
    def list_budgets(self):
        return self.repository.list_budgets()

    def get_budget(self, record_id: UUID):
        record = self.repository.get_budget(record_id)
        if record is None:
            raise NotFound("This budget could not be found.")
        return record

    def _check_unique(self, data: BudgetInput, current: UUID | None = None):
        existing = self.repository.find_budget(data.category_id, data.currency)
        if existing is not None and existing.id != current:
            raise Conflict(f"A {data.currency} budget for “{existing.category}” already exists.")

    def create_budget(self, data: BudgetInput):
        self.categories.require("expense", data.category_id)
        self._check_unique(data)
        return self.repository.save(Budget(user_id=self.repository.user_id, **data.model_dump()))

    def update_budget(self, record_id: UUID, data: BudgetInput):
        record = self.get_budget(record_id)
        self.categories.require("expense", data.category_id, current=record.category_id)
        self._check_unique(data, record.id)
        for key, value in data.model_dump().items():
            setattr(record, key, value)
        return self.repository.save(record)

    def delete_budget(self, record_id: UUID):
        self.repository.delete(self.get_budget(record_id))


def parse_month(value: str | None) -> date | None:
    """Parse YYYY-MM; the route pattern has already validated its shape."""
    return datetime.strptime(value, "%Y-%m").date() if value else None
