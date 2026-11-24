from uuid import UUID

from app.core.errors import NotFound
from app.modules.categories.service import CategoryService
from app.modules.recurrence.service import RecurrenceService
from app.modules.tasks.models import Task
from app.modules.tasks.repository import TaskRepository
from app.modules.tasks.schemas import TaskInput


class TaskService:
    def __init__(
        self,
        repository: TaskRepository,
        categories: CategoryService,
        recurrence: RecurrenceService | None = None,
    ):
        self.repository = repository
        self.categories = categories
        self.recurrence = recurrence
        owners = {repository.user_id, categories.repository.user_id}
        if recurrence:
            owners.add(recurrence.repository.user_id)
        if len(owners) != 1:
            raise ValueError("Task services must use the same authenticated owner.")

    def list(self, offset: int, limit: int, status: bool | None):
        if self.recurrence:
            self.recurrence.ensure()
        return self.repository.list(offset, limit, status)

    def get(self, record_id: UUID):
        record = self.repository.get(record_id)
        if record is None or record.user_id != self.repository.user_id:
            raise NotFound("This record could not be found.")
        return record

    def create(self, data: TaskInput):
        self.categories.require("task", data.category_id, optional=True)
        return self.repository.save(Task(user_id=self.repository.user_id, **data.model_dump()))

    def update(self, record_id: UUID, data: TaskInput):
        """Edit only this record. For a repeating task, later occurrences are unchanged."""
        record = self.get(record_id)
        self.categories.require("task", data.category_id, record.category_id, optional=True)
        for key, value in data.model_dump().items():
            setattr(record, key, value)
        return self.repository.save(record)

    def delete(self, record_id: UUID):
        """Delete only this record; a repeating task does not regenerate it."""
        self.repository.delete(self.get(record_id))
