from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.infrastructure.database import get_session
from app.modules.auth.dependencies import current_user
from app.modules.tasks.repository import TaskRepository
from app.modules.tasks.schemas import TaskInput, TaskOutput
from app.modules.tasks.service import TaskService

router = APIRouter(prefix="/tasks", tags=["tasks"])


def get_service(session: Session = Depends(get_session), user=Depends(current_user)):
    return TaskService(TaskRepository(session, user.id))


class Page(BaseModel):
    items: list[TaskOutput]
    total: int
    offset: int
    limit: int


@router.get("", response_model=Page)
def list_records(
    offset: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
    completed: bool | None = None,
    service: TaskService = Depends(get_service),
):
    return service.list(offset, limit, completed)


@router.get("/{record_id}", response_model=TaskOutput)
def get_record(record_id: UUID, service: TaskService = Depends(get_service)):
    return service.get(record_id)


@router.post("", response_model=TaskOutput, status_code=201)
def create(data: TaskInput, service: TaskService = Depends(get_service)):
    return service.create(data)


@router.put("/{record_id}", response_model=TaskOutput)
def update(record_id: UUID, data: TaskInput, service: TaskService = Depends(get_service)):
    return service.update(record_id, data)


@router.delete("/{record_id}", status_code=204)
def delete(record_id: UUID, service: TaskService = Depends(get_service)):
    service.delete(record_id)
    return Response(status_code=204)
