from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.infrastructure.database import get_session
from app.modules.auth.dependencies import current_user
from app.modules.bills.routes import get_recurrence as get_bill_recurrence
from app.modules.budget.repository import BudgetRepository
from app.modules.budget.schemas import (
    BudgetInput,
    BudgetOutput,
    ExpenseInput,
    ExpenseOutput,
    IncomeInput,
    IncomeOutput,
    Summary,
    TransactionPage,
)
from app.modules.budget.service import BudgetService, parse_month
from app.modules.categories.routes import get_service as get_categories
from app.modules.settings.repository import SettingsRepository
from app.modules.settings.service import SettingsService

router = APIRouter(tags=["budget"])
MONTH = r"^\d{4}-(0[1-9]|1[0-2])$"


def get_service(session: Session = Depends(get_session), user=Depends(current_user)):
    return BudgetService(
        BudgetRepository(session, user.id),
        SettingsService(SettingsRepository(session, user.id)),
        get_categories(session, user),
        get_bill_recurrence(session, user),
    )


class ExpensePage(BaseModel):
    items: list[ExpenseOutput]
    total: int
    offset: int
    limit: int


class IncomePage(BaseModel):
    items: list[IncomeOutput]
    total: int
    offset: int
    limit: int


@router.get("/budget/summary", response_model=Summary)
def summary(
    month: str | None = Query(None, pattern=MONTH), service: BudgetService = Depends(get_service)
):
    """Income, recorded spending against budgets, and unpaid bills shown separately."""
    return service.summary(parse_month(month))


@router.get("/transactions", response_model=TransactionPage)
def transactions(
    month: str | None = Query(None, pattern=MONTH),
    kind: Literal["all", "expense", "income"] = "all",
    offset: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
    service: BudgetService = Depends(get_service),
):
    """Expenses and income for one month, newest first. Defaults to the current month."""
    return service.transactions(kind, offset, limit, parse_month(month))


@router.get("/expenses", response_model=ExpensePage)
def list_expenses(
    offset: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
    month: str | None = Query(None, pattern=MONTH),
    service: BudgetService = Depends(get_service),
):
    return service.list_expenses(offset, limit, parse_month(month))


@router.get("/expenses/{record_id}", response_model=ExpenseOutput)
def get_expense(record_id: UUID, service: BudgetService = Depends(get_service)):
    return service.get_expense(record_id)


@router.post("/expenses", response_model=ExpenseOutput, status_code=201)
def create_expense(data: ExpenseInput, service: BudgetService = Depends(get_service)):
    return service.create_expense(data)


@router.put("/expenses/{record_id}", response_model=ExpenseOutput)
def update_expense(
    record_id: UUID, data: ExpenseInput, service: BudgetService = Depends(get_service)
):
    return service.update_expense(record_id, data)


@router.delete("/expenses/{record_id}", status_code=204)
def delete_expense(record_id: UUID, service: BudgetService = Depends(get_service)):
    service.delete_expense(record_id)
    return Response(status_code=204)


@router.get("/income", response_model=IncomePage)
def list_income(
    offset: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
    month: str | None = Query(None, pattern=MONTH),
    service: BudgetService = Depends(get_service),
):
    return service.list_income(offset, limit, parse_month(month))


@router.get("/income/{record_id}", response_model=IncomeOutput)
def get_income(record_id: UUID, service: BudgetService = Depends(get_service)):
    return service.get_income(record_id)


@router.post("/income", response_model=IncomeOutput, status_code=201)
def create_income(data: IncomeInput, service: BudgetService = Depends(get_service)):
    return service.create_income(data)


@router.put("/income/{record_id}", response_model=IncomeOutput)
def update_income(
    record_id: UUID, data: IncomeInput, service: BudgetService = Depends(get_service)
):
    return service.update_income(record_id, data)


@router.delete("/income/{record_id}", status_code=204)
def delete_income(record_id: UUID, service: BudgetService = Depends(get_service)):
    service.delete_income(record_id)
    return Response(status_code=204)


@router.get("/budgets", response_model=list[BudgetOutput])
def list_budgets(service: BudgetService = Depends(get_service)):
    return service.list_budgets()


@router.post("/budgets", response_model=BudgetOutput, status_code=201)
def create_budget(data: BudgetInput, service: BudgetService = Depends(get_service)):
    return service.create_budget(data)


@router.put("/budgets/{record_id}", response_model=BudgetOutput)
def update_budget(
    record_id: UUID, data: BudgetInput, service: BudgetService = Depends(get_service)
):
    return service.update_budget(record_id, data)


@router.delete("/budgets/{record_id}", status_code=204)
def delete_budget(record_id: UUID, service: BudgetService = Depends(get_service)):
    service.delete_budget(record_id)
    return Response(status_code=204)
