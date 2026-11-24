from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.infrastructure.database import get_session
from app.modules.auth.dependencies import current_user
from app.modules.categories.models import Scope
from app.modules.categories.repository import CategoryRepository
from app.modules.categories.schemas import CategoryInput, CategoryOutput, CategoryUpdate
from app.modules.categories.service import CategoryService

router = APIRouter(prefix="/categories", tags=["categories"])


def get_service(session: Session = Depends(get_session), user=Depends(current_user)):
    return CategoryService(CategoryRepository(session, user.id))


@router.get("", response_model=list[CategoryOutput])
def list_categories(
    scope: Scope | None = None,
    include_archived: bool = Query(True),
    service: CategoryService = Depends(get_service),
):
    """The account's categories, starting lists included. Archived ones are flagged."""
    return service.list(scope, include_archived)


@router.post("", response_model=CategoryOutput, status_code=201)
def create_category(
    data: CategoryInput, response: Response, service: CategoryService = Depends(get_service)
):
    record, created = service.create(data)
    if not created:
        response.status_code = 200
    return record


@router.put("/{record_id}", response_model=CategoryOutput)
def update_category(
    record_id: UUID, data: CategoryUpdate, service: CategoryService = Depends(get_service)
):
    return service.update(record_id, data)
