from alembic import context
from sqlalchemy import create_engine, pool

from app.infrastructure.database import Base
from app.infrastructure.migrations import migration_lock, migration_url
from app.modules.auth.models import AuthRateLimit, AuthSession, User  # noqa: F401
from app.modules.bills.models import Bill, BillSeries  # noqa: F401
from app.modules.budget.models import Budget, Expense, Income  # noqa: F401
from app.modules.calendar.models import CalendarEntry  # noqa: F401
from app.modules.categories.models import Category  # noqa: F401
from app.modules.groceries.models import Grocery  # noqa: F401
from app.modules.meals.models import (  # noqa: F401
    GroceryImport,
    MealPlanEntry,
    Recipe,
    RecipeIngredient,
)
from app.modules.settings.models import Settings  # noqa: F401
from app.modules.tasks.models import Task, TaskSeries  # noqa: F401

config = context.config
target_metadata = Base.metadata
# Prefer MIGRATION_DATABASE_URL (a direct connection); fall back to DATABASE_URL.
url = migration_url()
if context.is_offline_mode():
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = create_engine(url, poolclass=pool.NullPool)
    try:
        # Concurrent starts (e.g. overlapping deploys) wait here instead of racing.
        with migration_lock(engine):
            with engine.connect() as connection:
                context.configure(connection=connection, target_metadata=target_metadata)
                with context.begin_transaction():
                    context.run_migrations()
    finally:
        engine.dispose()
