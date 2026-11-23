from datetime import date
from uuid import UUID

from sqlalchemy import case, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import Conflict, NotFound
from app.modules.groceries.models import Grocery
from app.modules.meals.models import MEALS, GroceryImport, MealPlanEntry, Recipe

MEAL_ORDER = case({meal: index for index, meal in enumerate(MEALS)}, value=MealPlanEntry.meal)


class MealsRepository:
    def __init__(self, session: Session, user_id: UUID):
        self.session = session
        self.user_id = user_id

    def _owned(self, record):
        if record.user_id != self.user_id:
            raise NotFound("This record could not be found.")

    # Recipes
    def list_recipes(self, offset: int, limit: int):
        query = select(Recipe).where(Recipe.user_id == self.user_id)
        total = self.session.scalar(select(func.count()).select_from(query.subquery()))
        items = self.session.scalars(
            query.order_by(Recipe.name, Recipe.id).offset(offset).limit(limit)
        ).all()
        return {"items": items, "total": total, "offset": offset, "limit": limit}

    def get_recipe(self, record_id: UUID):
        return self.session.scalar(
            select(Recipe).where(Recipe.id == record_id, Recipe.user_id == self.user_id)
        )

    # Meal plan
    def entries_between(self, first: date, last: date):
        return self.session.scalars(
            select(MealPlanEntry)
            .where(
                MealPlanEntry.user_id == self.user_id,
                MealPlanEntry.plan_date >= first,
                MealPlanEntry.plan_date <= last,
            )
            .order_by(MealPlanEntry.plan_date, MEAL_ORDER, MealPlanEntry.id)
        ).all()

    def get_entry(self, record_id: UUID):
        return self.session.scalar(
            select(MealPlanEntry).where(
                MealPlanEntry.id == record_id, MealPlanEntry.user_id == self.user_id
            )
        )

    def entries_by_ids(self, ids: list[UUID]):
        return self.session.scalars(
            select(MealPlanEntry)
            .where(MealPlanEntry.user_id == self.user_id, MealPlanEntry.id.in_(ids))
            .order_by(MealPlanEntry.plan_date, MEAL_ORDER, MealPlanEntry.id)
        ).all()

    def open_groceries(self):
        return self.session.scalars(
            select(Grocery)
            .where(Grocery.user_id == self.user_id, Grocery.purchased.is_(False))
            .limit(1000)
        ).all()

    # Grocery additions
    def find_import(self, request_id: UUID):
        return self.session.scalar(
            select(GroceryImport).where(
                GroceryImport.user_id == self.user_id, GroceryImport.request_id == request_id
            )
        )

    def add_groceries(self, record: GroceryImport, entry_ids: list[UUID], groceries: list):
        """Claim the meals and add groceries in one transaction.

        Returns False if this request id was already accepted (a concurrent replay). Raises
        Conflict when another submission already added any of these meals. Existing grocery
        rows, including manual items, are never modified.
        """
        self._owned(record)
        for grocery in groceries:
            self._owned(grocery)
        self.session.add(record)
        try:
            self.session.flush()
        except IntegrityError:
            self.session.rollback()
            return False
        # The conditional update is the claim: a concurrent submission for the same meals
        # waits on these row locks and then matches fewer rows.
        claimed = self.session.execute(
            update(MealPlanEntry)
            .where(
                MealPlanEntry.user_id == self.user_id,
                MealPlanEntry.id.in_(entry_ids),
                MealPlanEntry.grocery_import_id.is_(None),
            )
            .values(grocery_import_id=record.id)
            .execution_options(synchronize_session=False)
        ).rowcount
        if claimed != len(entry_ids):
            self.session.rollback()
            raise Conflict(
                "Some of these meals were already added to groceries. Refresh the preview."
            )
        self.session.add_all(groceries)
        try:
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            return False
        return True

    def save(self, record):
        self._owned(record)
        self.session.add(record)
        self.session.commit()
        self.session.refresh(record)
        return record

    def delete(self, record):
        self._owned(record)
        self.session.delete(record)
        self.session.commit()
