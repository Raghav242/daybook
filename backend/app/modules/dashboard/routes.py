from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.infrastructure.database import get_session
from app.modules.bills.schemas import BillOutput
from app.modules.calendar.schemas import CalendarEntryOutput
from app.modules.dashboard.repository import DashboardRepository
from app.modules.dashboard.service import DashboardService
from app.modules.groceries.schemas import GroceryOutput
from app.modules.settings.repository import SettingsRepository
from app.modules.settings.service import SettingsService
from app.modules.tasks.schemas import TaskOutput

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


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


@router.get("", response_model=Summary)
def get_dashboard(session: Session = Depends(get_session)):
    service = DashboardService(
        DashboardRepository(session), SettingsService(SettingsRepository(session))
    )
    return service.get()
