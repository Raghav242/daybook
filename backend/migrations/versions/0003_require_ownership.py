"""Require explicit ownership; stop safely when legacy rows need an owner."""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

TABLES = ("tasks", "calendar", "groceries", "bills", "settings")


def upgrade():
    connection = op.get_bind()
    counts = {
        name: connection.scalar(sa.text(f'SELECT count(*) FROM "{name}" WHERE user_id IS NULL'))
        for name in TABLES
    }
    if any(counts.values()):
        raise RuntimeError(
            f"Unowned legacy records: {counts}. No records were assigned or deleted. "
            "Run alembic upgrade 0002, then python -m app.manage create-user --username OWNER, "
            "then python -m app.manage claim-legacy --owner OWNER --apply, then alembic upgrade head."
        )
    for name in TABLES:
        with op.batch_alter_table(name) as batch:
            batch.alter_column("user_id", existing_type=sa.Uuid(), nullable=False)


def downgrade():
    for name in TABLES:
        with op.batch_alter_table(name) as batch:
            batch.alter_column("user_id", existing_type=sa.Uuid(), nullable=True)
