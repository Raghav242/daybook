from alembic import context
from sqlalchemy import create_engine, pool

from app.core.config import DATABASE_URL
from app.infrastructure.database import Base
from app.modules.auth.models import AuthRateLimit, AuthSession, User  # noqa: F401
from app.modules.bills.models import Bill  # noqa: F401
from app.modules.calendar.models import CalendarEntry  # noqa: F401
from app.modules.groceries.models import Grocery  # noqa: F401
from app.modules.settings.models import Settings  # noqa: F401
from app.modules.tasks.models import Task  # noqa: F401

config = context.config
target_metadata = Base.metadata
if context.is_offline_mode():
    context.configure(url=DATABASE_URL, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = create_engine(DATABASE_URL, poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
