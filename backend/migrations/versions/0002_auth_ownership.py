"""Introduce auth and nullable ownership without assigning legacy records."""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

TABLES = ("tasks", "calendar", "groceries", "bills", "settings")


def upgrade():
    connection = op.get_bind()
    # Inspect before constraints; counts only, never personal content.
    counts = {name: connection.scalar(sa.text(f'SELECT count(*) FROM "{name}"')) for name in TABLES}
    print(f"Legacy personal-record counts (no owner assigned): {counts}")
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("username", sa.String(40), nullable=False),
        sa.Column("normalized_username", sa.String(40), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("normalized_username", name="uq_users_normalized_username"),
    )
    op.create_table(
        "auth_sessions",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"])
    op.create_index("ix_auth_sessions_expires_at", "auth_sessions", ["expires_at"])
    op.create_table(
        "auth_rate_limits",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_auth_rate_limits_expires_at", "auth_rate_limits", ["expires_at"])
    for name in TABLES:
        with op.batch_alter_table(name) as batch:
            if name == "settings":
                batch.drop_constraint("single_local_profile", type_="check")
            batch.add_column(sa.Column("user_id", sa.Uuid(), nullable=True))
            batch.create_foreign_key(f"fk_{name}_user_id", "users", ["user_id"], ["id"])
            if name == "settings":
                batch.create_unique_constraint("uq_settings_user_id", ["user_id"])
            else:
                batch.create_index(f"ix_{name}_user_id", ["user_id"])
    if connection.dialect.name == "postgresql":
        # Legacy settings explicitly inserted id=1 and may not have advanced SERIAL.
        connection.execute(
            sa.text(
                "SELECT setval(pg_get_serial_sequence('settings', 'id'), "
                "COALESCE(MAX(id), 1), MAX(id) IS NOT NULL) FROM settings"
            )
        )


def downgrade():
    raise RuntimeError(
        "Ownership migration is not automatically reversible. Restore a pre-migration backup."
    )
