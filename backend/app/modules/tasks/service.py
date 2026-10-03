from uuid import UUID

from app.core.errors import NotFound
from app.modules.tasks.models import Task
from app.modules.tasks.repository import TaskRepository
from app.modules.tasks.schemas import TaskInput


class TaskService:
    def __init__(self, repository: TaskRepository):
        self.repository = repository

    def list(self, offset: int, limit: int, status: bool | None):
        return self.repository.list(offset, limit, status)

    def get(self, record_id: UUID):
        record = self.repository.get(record_id)
        if record is None:
            raise NotFound("This record could not be found.")
        return record

    def create(self, data: TaskInput):
        return self.repository.save(Task(**data.model_dump()))

    def update(self, record_id: UUID, data: TaskInput):
        record = self.get(record_id)
        for key, value in data.model_dump().items():
            setattr(record, key, value)
        return self.repository.save(record)

    def delete(self, record_id: UUID):
        self.repository.delete(self.get(record_id))
