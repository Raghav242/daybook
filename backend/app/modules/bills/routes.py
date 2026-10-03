from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.infrastructure.database import get_session
from app.modules.bills.repository import BillRepository
from app.modules.bills.schemas import BillInput, BillOutput
from app.modules.bills.service import BillService

router = APIRouter(prefix="/bills", tags=["bills"])


def get_service(session: Session = Depends(get_session)):
    return BillService(BillRepository(session))


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


@router.delete("/{record_id}", status_code=204)
def delete(record_id: UUID, service: BillService = Depends(get_service)):
    service.delete(record_id)
    return Response(status_code=204)
