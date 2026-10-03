from uuid import UUID

from app.core.errors import NotFound
from app.modules.groceries.models import Grocery
from app.modules.groceries.repository import GroceryRepository
from app.modules.groceries.schemas import GroceryInput


class GroceryService:
    def __init__(self, repository: GroceryRepository):
        self.repository = repository

    def list(self, offset: int, limit: int, status: bool | None):
        return self.repository.list(offset, limit, status)

    def get(self, record_id: UUID):
        record = self.repository.get(record_id)
        if record is None or record.user_id != self.repository.user_id:
            raise NotFound("This record could not be found.")
        return record

    def create(self, data: GroceryInput):
        return self.repository.save(Grocery(user_id=self.repository.user_id, **data.model_dump()))

    def update(self, record_id: UUID, data: GroceryInput):
        record = self.get(record_id)
        for key, value in data.model_dump().items():
            setattr(record, key, value)
        return self.repository.save(record)

    def delete(self, record_id: UUID):
        self.repository.delete(self.get(record_id))
