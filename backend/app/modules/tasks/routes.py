from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.infrastructure.database import get_session
from app.modules.auth.dependencies import current_user
from app.modules.categories.routes import get_service as get_categories
from app.modules.recurrence.service import RecurrenceService
from app.modules.settings.repository import SettingsRepository
from app.modules.settings.service import SettingsService
from app.modules.tasks.repository import TaskRepository, TaskSeriesRepository
from app.modules.tasks.schemas import TaskInput, TaskOutput, TaskSeriesInput, TaskSeriesOutput
from app.modules.tasks.service import TaskService

router = APIRouter(prefix="/tasks", tags=["tasks"])
series_router = APIRouter(prefix="/task-series", tags=["tasks"])


def get_recurrence(session: Session = Depends(get_session), user=Depends(current_user)):
    categories = get_categories(session, user)
    return RecurrenceService(
        TaskSeriesRepository(session, user.id),
        SettingsService(SettingsRepository(session, user.id)),
        validate=lambda data, series: categories.require(
            "task", data.category_id, series.category_id if series else None, optional=True
        ),
    )


def get_service(session: Session = Depends(get_session), user=Depends(current_user)):
    return TaskService(
        TaskRepository(session, user.id),
        get_categories(session, user),
        get_recurrence(session, user),
    )


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


@router.put("/{record_id}/future", response_model=TaskSeriesOutput)
def update_future(
    record_id: UUID, data: TaskSeriesInput, service: RecurrenceService = Depends(get_recurrence)
):
    """Edit this occurrence and all later occurrences of its repeating task."""
    return service.update_future(record_id, data)


@router.delete("/{record_id}", status_code=204)
def delete(record_id: UUID, service: TaskService = Depends(get_service)):
    service.delete(record_id)
    return Response(status_code=204)


@series_router.post("", response_model=TaskSeriesOutput, status_code=201)
def create_series(data: TaskSeriesInput, service: RecurrenceService = Depends(get_recurrence)):
    return service.create(data)


@series_router.get("/{series_id}", response_model=TaskSeriesOutput)
def get_series(series_id: UUID, service: RecurrenceService = Depends(get_recurrence)):
    return service.get(series_id)


@series_router.delete("/{series_id}", status_code=204)
def delete_series(series_id: UUID, service: RecurrenceService = Depends(get_recurrence)):
    service.delete(series_id)
    return Response(status_code=204)
