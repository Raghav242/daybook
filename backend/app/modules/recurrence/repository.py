from datetime import date
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.infrastructure.upsert import insert_ignoring_duplicates


class SeriesRepository:
    """Owner-scoped storage for a recurrence definition and its occurrence rows.

    Feature modules subclass this with their series model, occurrence model and the
    boolean column that marks an occurrence as done (completed or paid).
    """

    series_model: type
    occurrence_model: type
    done_field: str

    def __init__(self, session: Session, user_id: UUID):
        self.session = session
        self.user_id = user_id

    def get_series(self, series_id: UUID):
        model = self.series_model
        return self.session.scalar(
            select(model).where(model.id == series_id, model.user_id == self.user_id)
        )

    def get_occurrence(self, record_id: UUID):
        model = self.occurrence_model
        return self.session.scalar(
            select(model).where(model.id == record_id, model.user_id == self.user_id)
        )

    def needing_generation(self, through: date):
        model = self.series_model
        return self.session.scalars(
            select(model)
            .where(
                model.user_id == self.user_id,
                model.generated_through < through,
                or_(model.until_date.is_(None), model.generated_through < model.until_date),
            )
            .order_by(model.id)
        ).all()

    def occurrences_from(self, series_id: UUID, first: date):
        model = self.occurrence_model
        return self.session.scalars(
            select(model)
            .where(
                model.user_id == self.user_id,
                model.series_id == series_id,
                model.occurrence_date >= first,
            )
            .order_by(model.occurrence_date, model.id)
        ).all()

    def insert_occurrences(self, rows: list[dict]):
        for row in rows:
            row["user_id"] = self.user_id
        insert_ignoring_duplicates(
            self.session, self.occurrence_model, rows, ["series_id", "occurrence_date"]
        )

    def add(self, record):
        if record.user_id != self.user_id:
            raise ValueError("Series records must belong to the authenticated owner.")
        self.session.add(record)
        self.session.flush()

    def delete_occurrence(self, record):
        self.session.delete(record)

    def delete_series(self, record):
        self.session.delete(record)

    def flush(self):
        self.session.flush()

    def commit(self):
        self.session.commit()

    def refresh(self, record):
        self.session.refresh(record)
