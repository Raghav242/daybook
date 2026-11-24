from uuid import UUID

from pydantic import Field, field_validator

from app.core.schemas import Input, Output
from app.modules.categories.models import Scope, clean_name


class CategoryName(Input):
    name: str = Field(min_length=1, max_length=80)

    @field_validator("name")
    @classmethod
    def collapse_spaces(cls, value: str) -> str:
        return clean_name(value)


class CategoryInput(CategoryName):
    scope: Scope


class CategoryUpdate(CategoryName):
    archived: bool = False


class CategoryOutput(Output):
    id: UUID
    scope: Scope
    name: str
    archived: bool
