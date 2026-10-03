from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.infrastructure.database import get_session
from app.modules.auth.dependencies import current_user
from app.modules.calendar.repository import CalendarEntryRepository
from app.modules.calendar.schemas import CalendarEntryInput, CalendarEntryOutput
from app.modules.calendar.service import CalendarEntryService
from app.modules.settings.repository import SettingsRepository
from app.modules.settings.service import SettingsService

router = APIRouter(prefix="/calendar", tags=["calendar"])


def get_service(session: Session = Depends(get_session), user=Depends(current_user)):
    return CalendarEntryService(
        CalendarEntryRepository(session, user.id),
        SettingsService(SettingsRepository(session, user.id)),
    )


class Page(BaseModel):
    items: list[CalendarEntryOutput]
    total: int
    offset: int
    limit: int


@router.get("", response_model=Page)
def list_records(
    offset: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
    period: Literal["all", "upcoming", "past"] = "all",
    service: CalendarEntryService = Depends(get_service),
):
    return service.list(offset, limit, period)


@router.get("/{record_id}", response_model=CalendarEntryOutput)
def get_record(record_id: UUID, service: CalendarEntryService = Depends(get_service)):
    return service.get(record_id)


@router.post("", response_model=CalendarEntryOutput, status_code=201)
def create(data: CalendarEntryInput, service: CalendarEntryService = Depends(get_service)):
    return service.create(data)


@router.put("/{record_id}", response_model=CalendarEntryOutput)
def update(
    record_id: UUID, data: CalendarEntryInput, service: CalendarEntryService = Depends(get_service)
):
    return service.update(record_id, data)


@router.delete("/{record_id}", status_code=204)
def delete(record_id: UUID, service: CalendarEntryService = Depends(get_service)):
    service.delete(record_id)
    return Response(status_code=204)
