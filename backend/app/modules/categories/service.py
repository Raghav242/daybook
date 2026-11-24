from uuid import UUID

from app.core.errors import Conflict, Invalid, NotFound
from app.modules.categories.models import SCOPES, Category, category_key
from app.modules.categories.repository import CategoryRepository
from app.modules.categories.schemas import CategoryInput, CategoryUpdate

SCOPE_LABELS = {
    "task": "task",
    "expense": "expense",
    "income": "income",
    "grocery": "grocery",
}


class CategoryService:
    """The single source of categories for tasks, groceries, expenses/budgets and income."""

    def __init__(self, repository: CategoryRepository):
        self.repository = repository

    def ensure_defaults(self):
        """Give each scope its starting list once. Archiving never brings defaults back."""
        missing = [scope for scope in SCOPES if scope not in self.repository.seeded_scopes()]
        if missing:
            self.repository.insert_defaults(missing)

    def list(self, scope: str | None = None, include_archived: bool = True):
        self.ensure_defaults()
        return self.repository.list(scope, include_archived)

    def get(self, record_id: UUID):
        record = self.repository.get(record_id)
        if record is None:
            raise NotFound("This category could not be found.")
        return record

    def create(self, data: CategoryInput) -> tuple[Category, bool]:
        """Add a category, or return the equivalent one (restoring it if archived).

        Names that differ only by case or spacing are the same category, so a repeated
        submission returns the existing record instead of creating a duplicate.
        """
        self.ensure_defaults()
        key = category_key(data.name)
        existing = self.repository.find(data.scope, key)
        if existing is not None:
            if existing.archived:
                existing.archived = False
                return self.repository.save(existing), False
            return existing, False
        record = Category(
            user_id=self.repository.user_id,
            scope=data.scope,
            name=data.name,
            key=key,
            position=self.repository.next_position(data.scope),
            archived=False,
        )
        try:
            return self.repository.save(record), True
        except Conflict:
            # A concurrent request added the same name first.
            return self.repository.find(data.scope, key), False

    def update(self, record_id: UUID, data: CategoryUpdate):
        """Rename or archive. Existing records keep their category either way."""
        record = self.get(record_id)
        key = category_key(data.name)
        existing = self.repository.find(record.scope, key)
        if existing is not None and existing.id != record.id:
            raise Conflict(f"“{existing.name}” already exists in this list.")
        record.name, record.key, record.archived = data.name, key, data.archived
        return self.repository.save(record)

    def require(
        self,
        scope: str,
        category_id: UUID | None,
        current: UUID | None = None,
        optional: bool = False,
        allow_archived: bool = False,
    ) -> Category | None:
        """Validate a submitted category: owned, in the right scope, and not archived.

        A record may keep an archived category it already has (``current``) so editing
        other fields never forces a change. Another account's id is reported exactly like
        a missing one.
        """
        if category_id is None:
            if optional:
                return None
            raise Invalid(f"Choose a {SCOPE_LABELS[scope]} category.")
        record = self.repository.get(category_id)
        if record is None or record.scope != scope:
            raise Invalid(f"Choose one of your {SCOPE_LABELS[scope]} categories.")
        if record.archived and record.id != current and not allow_archived:
            raise Invalid(f"“{record.name}” is archived. Choose another category or restore it.")
        return record
