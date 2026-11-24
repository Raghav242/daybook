from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from app.modules.budget.service import BudgetService
from app.modules.dashboard.repository import DashboardRepository
from app.modules.meals.service import MealsService
from app.modules.recurrence.service import RecurrenceService
from app.modules.settings.service import SettingsService


class DashboardService:
    """Composes feature services; it owns no calculations of its own beyond date bounds."""

    def __init__(
        self,
        repository: DashboardRepository,
        settings: SettingsService,
        *,
        recurrences: tuple[RecurrenceService, ...] = (),
        meals: MealsService | None = None,
        budget: BudgetService | None = None,
    ):
        self.repository = repository
        self.settings = settings
        self.recurrences = recurrences
        self.meals = meals
        self.budget = budget
        owners = {repository.user_id, settings.repository.user_id}
        owners |= {service.repository.user_id for service in recurrences}
        owners |= {service.repository.user_id for service in (meals, budget) if service}
        if len(owners) != 1:
            raise ValueError("Dashboard services must use the same authenticated owner.")

    def get(self, now: datetime | None = None):
        settings = self.settings.get()
        zone = ZoneInfo(settings.timezone)
        today = (now or datetime.now(timezone.utc)).astimezone(zone).date()
        start = datetime.combine(today, time.min, zone).astimezone(timezone.utc)
        end = datetime.combine(today + timedelta(days=1), time.min, zone).astimezone(timezone.utc)
        horizon = today + timedelta(days=30)
        for recurrence in self.recurrences:
            recurrence.ensure(today)
        spending = None
        if self.budget:
            month = self.budget.summary(today=today)
            spending = dict(
                month=month["month"],
                totals=month["totals"],
                expected_bills=month["expected_bills"],
                over_budget=[
                    line
                    for line in month["categories"]
                    if line["remaining"] is not None and line["remaining"] < 0
                ],
            )
        return {
            "today": today,
            "timezone": settings.timezone,
            "bill_horizon": horizon,
            **self.repository.summary(today, start, end, horizon),
            "meals_today": self.meals.entries(today, 1) if self.meals else [],
            "spending": spending,
        }
