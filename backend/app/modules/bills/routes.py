from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.infrastructure.database import get_session
from app.modules.auth.dependencies import current_user
from app.modules.bills.repository import BillRepository, BillSeriesRepository
from app.modules.bills.schemas import (
    BillInput,
    BillOutput,
    BillSeriesInput,
    BillSeriesOutput,
    PayInput,
)
from app.modules.bills.service import BillService
from app.modules.recurrence.service import RecurrenceService
from app.modules.settings.repository import SettingsRepository
from app.modules.settings.service import SettingsService

router = APIRouter(prefix="/bills", tags=["bills"])
series_router = APIRouter(prefix="/bill-series", tags=["bills"])


def get_recurrence(session: Session = Depends(get_session), user=Depends(current_user)):
    return RecurrenceService(
        BillSeriesRepository(session, user.id),
        SettingsService(SettingsRepository(session, user.id)),
    )


def get_service(session: Session = Depends(get_session), user=Depends(current_user)):
    return BillService(BillRepository(session, user.id), get_recurrence(session, user))


class Page(BaseModel):
    items: list[BillOutput]
    total: int
    offset: int
    limit: int


@router.get("", response_model=Page)
def list_records(
    offset: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
    paid: bool | None = None,
    service: BillService = Depends(get_service),
):
    return service.list(offset, limit, paid)


@router.get("/{record_id}", response_model=BillOutput)
def get_record(record_id: UUID, service: BillService = Depends(get_service)):
    return service.get(record_id)


@router.post("", response_model=BillOutput, status_code=201)
def create(data: BillInput, service: BillService = Depends(get_service)):
    return service.create(data)


@router.put("/{record_id}", response_model=BillOutput)
def update(record_id: UUID, data: BillInput, service: BillService = Depends(get_service)):
    return service.update(record_id, data)


@router.post("/{record_id}/pay", response_model=BillOutput)
def pay(record_id: UUID, data: PayInput, service: BillService = Depends(get_service)):
    """Record a payment the user made elsewhere. Daybook never moves money."""
    return service.pay(record_id, data)


@router.put("/{record_id}/future", response_model=BillSeriesOutput)
def update_future(
    record_id: UUID, data: BillSeriesInput, service: RecurrenceService = Depends(get_recurrence)
):
    """Edit this occurrence and all later occurrences of its repeating bill."""
    return service.update_future(record_id, data)


@router.delete("/{record_id}", status_code=204)
def delete(record_id: UUID, service: BillService = Depends(get_service)):
    service.delete(record_id)
    return Response(status_code=204)


@series_router.post("", response_model=BillSeriesOutput, status_code=201)
def create_series(data: BillSeriesInput, service: RecurrenceService = Depends(get_recurrence)):
    return service.create(data)


@series_router.get("/{series_id}", response_model=BillSeriesOutput)
def get_series(series_id: UUID, service: RecurrenceService = Depends(get_recurrence)):
    return service.get(series_id)


@series_router.delete("/{series_id}", status_code=204)
def delete_series(series_id: UUID, service: RecurrenceService = Depends(get_recurrence)):
    service.delete(series_id)
    return Response(status_code=204)
