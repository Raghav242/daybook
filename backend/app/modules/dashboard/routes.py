from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.infrastructure.database import get_session
from app.modules.auth.dependencies import current_user
from app.modules.bills.routes import get_recurrence as get_bill_recurrence
from app.modules.bills.schemas import BillOutput
from app.modules.budget.routes import get_service as get_budget_service
from app.modules.budget.schemas import CurrencyTotal, ExpectedBills
from app.modules.calendar.schemas import CalendarEntryOutput
from app.modules.dashboard.repository import DashboardRepository
from app.modules.dashboard.service import DashboardService
from app.modules.groceries.schemas import GroceryOutput
from app.modules.meals.routes import get_service as get_meals_service
from app.modules.meals.schemas import MealPlanOutput
from app.modules.settings.repository import SettingsRepository
from app.modules.settings.service import SettingsService
from app.modules.tasks.routes import get_recurrence as get_task_recurrence
from app.modules.tasks.schemas import TaskOutput

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


class RecurringItem(BaseModel):
    kind: Literal["task", "bill"]
    id: UUID
    title: str
    due_date: date
    amount: Decimal | None
    currency: str | None
    overdue: bool


class Spending(BaseModel):
    month: date
    totals: list[CurrencyTotal]
    expected_bills: list[ExpectedBills]


class Summary(BaseModel):
    today: date
    timezone: str
    bill_horizon: date
    counts: dict[str, int]
    tasks: list[TaskOutput]
    agenda: list[CalendarEntryOutput]
    upcoming: list[CalendarEntryOutput]
    groceries: list[GroceryOutput]
    bills: list[BillOutput]
    bill_totals: dict[str, str]
    recurring: list[RecurringItem]
    meals_today: list[MealPlanOutput]
    spending: Spending | None


@router.get("", response_model=Summary)
def get_dashboard(session: Session = Depends(get_session), user=Depends(current_user)):
    service = DashboardService(
        DashboardRepository(session, user.id),
        SettingsService(SettingsRepository(session, user.id)),
        recurrences=(get_task_recurrence(session, user), get_bill_recurrence(session, user)),
        meals=get_meals_service(session, user),
        budget=get_budget_service(session, user),
    )
    return service.get()
