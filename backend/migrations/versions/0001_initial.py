"""Initial Phase 1 tables. No personal records are created."""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "tasks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("priority", sa.String(10), nullable=False),
        sa.Column("category", sa.String(80), nullable=False),
        sa.Column("completed", sa.Boolean(), nullable=False),
        sa.CheckConstraint("due_date IS NULL OR due_at IS NULL", name="task_deadline_exclusive"),
        sa.CheckConstraint("priority IN ('low', 'normal', 'high')", name="task_priority"),
    )
    for field in ["due_date", "due_at", "completed"]:
        op.create_index("ix_tasks_" + field, "tasks", [field])
    op.create_table(
        "calendar",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("all_day", sa.Boolean(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.CheckConstraint('"end" > start', name="event_time_order"),
        sa.CheckConstraint(
            "(all_day = false AND start_date IS NULL AND end_date IS NULL) OR (all_day = true AND start_date IS NOT NULL AND end_date IS NOT NULL AND end_date > start_date)",
            name="event_date_order",
        ),
    )
    op.create_index("ix_calendar_start", "calendar", ["start"])
    op.create_table(
        "groceries",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 3), nullable=False),
        sa.Column("unit", sa.String(40), nullable=False),
        sa.Column("category", sa.String(80), nullable=False),
        sa.Column("purchased", sa.Boolean(), nullable=False),
        sa.CheckConstraint("quantity > 0", name="grocery_quantity_positive"),
    )
    op.create_index("ix_groceries_purchased", "groceries", ["purchased"])
    op.create_table(
        "bills",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("paid", sa.Boolean(), nullable=False),
        sa.CheckConstraint("amount >= 0", name="bill_amount_nonnegative"),
    )
    for field in ["due_date", "paid"]:
        op.create_index("ix_bills_" + field, "bills", [field])
    op.create_table(
        "settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("timezone", sa.String(80), nullable=False),
        sa.Column("default_currency", sa.String(3), nullable=False),
        sa.Column("enabled_modules", sa.JSON(), nullable=False),
        sa.CheckConstraint("id = 1", name="single_local_profile"),
    )


def downgrade():
    for table in ["settings", "bills", "groceries", "calendar", "tasks"]:
        op.drop_table(table)
