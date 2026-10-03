from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.infrastructure.database import get_session
from app.modules.auth.dependencies import current_user
from app.modules.groceries.repository import GroceryRepository
from app.modules.groceries.schemas import GroceryInput, GroceryOutput
from app.modules.groceries.service import GroceryService

router = APIRouter(prefix="/groceries", tags=["groceries"])


def get_service(session: Session = Depends(get_session), user=Depends(current_user)):
    return GroceryService(GroceryRepository(session, user.id))


class Page(BaseModel):
    items: list[GroceryOutput]
    total: int
    offset: int
    limit: int


@router.get("", response_model=Page)
def list_records(
    offset: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
    purchased: bool | None = None,
    service: GroceryService = Depends(get_service),
):
    return service.list(offset, limit, purchased)


@router.get("/{record_id}", response_model=GroceryOutput)
def get_record(record_id: UUID, service: GroceryService = Depends(get_service)):
    return service.get(record_id)


@router.post("", response_model=GroceryOutput, status_code=201)
def create(data: GroceryInput, service: GroceryService = Depends(get_service)):
    return service.create(data)


@router.put("/{record_id}", response_model=GroceryOutput)
def update(record_id: UUID, data: GroceryInput, service: GroceryService = Depends(get_service)):
    return service.update(record_id, data)


@router.delete("/{record_id}", status_code=204)
def delete(record_id: UUID, service: GroceryService = Depends(get_service)):
    service.delete(record_id)
    return Response(status_code=204)
