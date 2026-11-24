from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import Conflict, NotFound
from app.infrastructure.upsert import insert_ignoring_duplicates
from app.modules.categories.models import DEFAULTS, Category, category_key


class CategoryRepository:
    def __init__(self, session: Session, user_id: UUID):
        self.session = session
        self.user_id = user_id

    def seeded_scopes(self) -> set[str]:
        return set(
            self.session.scalars(
                select(Category.scope).where(Category.user_id == self.user_id).distinct()
            )
        )

    def insert_defaults(self, scopes: list[str]):
        """Create the starting list for scopes that have none (safe under concurrency)."""
        rows = [
            dict(
                id=uuid4(),
                user_id=self.user_id,
                scope=scope,
                name=name,
                key=category_key(name),
                position=position,
                archived=False,
            )
            for scope in scopes
            for position, name in enumerate(DEFAULTS[scope])
        ]
        insert_ignoring_duplicates(self.session, Category, rows, ["user_id", "scope", "key"])
        self.session.commit()

    def list(self, scope: str | None, include_archived: bool):
        query = select(Category).where(Category.user_id == self.user_id)
        if scope:
            query = query.where(Category.scope == scope)
        if not include_archived:
            query = query.where(Category.archived.is_(False))
        return self.session.scalars(
            query.order_by(Category.scope, Category.position, Category.key, Category.id)
        ).all()

    def get(self, record_id: UUID):
        return self.session.scalar(
            select(Category).where(Category.id == record_id, Category.user_id == self.user_id)
        )

    def find(self, scope: str, key: str):
        return self.session.scalar(
            select(Category).where(
                Category.user_id == self.user_id, Category.scope == scope, Category.key == key
            )
        )

    def next_position(self, scope: str) -> int:
        current = self.session.scalar(
            select(func.max(Category.position)).where(
                Category.user_id == self.user_id, Category.scope == scope
            )
        )
        return 0 if current is None else current + 1

    def save(self, record):
        if record.user_id != self.user_id:
            raise NotFound("This category could not be found.")
        self.session.add(record)
        try:
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            raise Conflict("A category with that name already exists.") from None
        self.session.refresh(record)
        return record
