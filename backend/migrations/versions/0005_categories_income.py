"""Shared categories and manual income.

Upgrade
- Creates ``categories`` (per user and scope: task, expense, income, grocery) and gives every
  existing account the starting lists.
- Converts the free-text category columns on tasks, task_series, groceries,
  recipe_ingredients, expenses and budgets into ``category_id`` references. Existing values
  are preserved: each distinct value becomes a category of the matching scope. Values that
  differ only by case or spacing ("Coffee", " coffee ") are merged into one category,
  named by the commonest spelling (ties prefer normal capitalization); a
  value equal to a starting category ("groceries") joins that category. Nothing else is
  merged or renamed. Expenses and budgets share the expense scope, so a budget and the
  spending it limits reference the same row. Empty task/grocery categories become NULL.
- Creates ``income``.

Downgrade
- Restores the text columns from the referenced category names, so records keep their
  category text. Permanently deletes income records, categories not used by any record,
  archive flags and renames' history; merged spelling variants come back as the single
  merged name.

Both directions read and rewrite rows, so they must run against a live database. Offline
(``--sql``) generation is refused rather than emitting a script that would drop data.
"""

from collections import Counter, defaultdict
from uuid import uuid4

import sqlalchemy as sa
from alembic import context, op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

DEFAULTS = {
    "task": ("Personal", "Study", "Work", "Home", "Health", "Errands"),
    "expense": (
        "Housing",
        "Groceries",
        "Dining",
        "Transport",
        "Utilities",
        "Education",
        "Health",
        "Shopping",
        "Subscriptions",
        "Other",
    ),
    "income": ("Salary", "Part-time Work", "Scholarship", "Freelance", "Gift", "Other"),
    "grocery": (
        "Produce",
        "Dairy & Eggs",
        "Pantry",
        "Frozen",
        "Snacks",
        "Beverages",
        "Household",
        "Other",
    ),
}
# (table, scope, has category_key column, indexed category_id)
SOURCES = [
    ("tasks", "task", False, True),
    ("task_series", "task", False, False),
    ("groceries", "grocery", False, True),
    ("recipe_ingredients", "grocery", False, False),
    ("expenses", "expense", True, True),
    ("budgets", "expense", True, False),
]
REQUIRED = {"expenses", "budgets"}


def clean(name):
    return " ".join((name or "").split())


def key_of(name):
    return clean(name).casefold()


def spelling_rank(item):
    """Commonest spelling first; on a tie prefer "Coffee" over "COFFEE" or "coffee"."""
    name, count = item
    return (-count, name.isupper(), name.islower(), name)


def require_online(direction):
    if context.is_offline_mode():
        raise RuntimeError(
            f"Migration 0005 {direction} rewrites category data and must run against a live "
            "database. Run it without --sql (back up first)."
        )


def categories_table():
    return sa.table(
        "categories",
        sa.column("id", sa.Uuid()),
        sa.column("user_id", sa.Uuid()),
        sa.column("scope", sa.String()),
        sa.column("name", sa.String()),
        sa.column("key", sa.String()),
        sa.column("position", sa.Integer()),
        sa.column("archived", sa.Boolean()),
    )


def record_table(table, has_key=False):
    columns = [
        sa.column("user_id", sa.Uuid()),
        sa.column("category", sa.String()),
        sa.column("category_id", sa.Uuid()),
    ]
    if has_key:
        columns.append(sa.column("category_key", sa.String()))
    return sa.table(table, *columns)


def owner_key(table):
    return dict(
        constraint_name=f"fk_{table}_category_owner",
        referent_table="categories",
        local_cols=["category_id", "user_id"],
        remote_cols=["id", "user_id"],
    )


def upgrade():
    require_online("upgrade")
    op.create_table(
        "categories",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("scope", sa.String(10), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("key", sa.String(80), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("archived", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("user_id", "scope", "key", name="uq_categories_scope_key"),
        sa.UniqueConstraint("id", "user_id", name="uq_categories_id_user"),
        sa.CheckConstraint(
            "scope IN ('task', 'expense', 'income', 'grocery')", name="category_scope"
        ),
    )
    op.create_index("ix_categories_user_id", "categories", ["user_id"])
    for table, _, _, _ in SOURCES:
        op.add_column(table, sa.Column("category_id", sa.Uuid(), nullable=True))

    migrate_values()

    for table, _, has_key, indexed in SOURCES:
        with op.batch_alter_table(table) as batch:
            if table == "budgets":
                batch.drop_constraint("uq_budgets_category", type_="unique")
            if table in REQUIRED:
                batch.alter_column("category_id", existing_type=sa.Uuid(), nullable=False)
            batch.drop_column("category")
            if has_key:
                batch.drop_column("category_key")
            batch.create_foreign_key(**owner_key(table))
            if indexed:
                batch.create_index(f"ix_{table}_category_id", ["category_id"])
            if table == "budgets":
                batch.create_unique_constraint(
                    "uq_budgets_category", ["user_id", "category_id", "currency"]
                )

    op.create_table(
        "income",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("category_id", sa.Uuid(), nullable=False),
        sa.Column("received_on", sa.Date(), nullable=False),
        sa.Column("note", sa.String(500), nullable=False),
        sa.CheckConstraint("amount > 0", name="income_amount_positive"),
        sa.ForeignKeyConstraint(
            ["category_id", "user_id"],
            ["categories.id", "categories.user_id"],
            name="fk_income_category_owner",
        ),
    )
    for field in ["user_id", "category_id", "received_on"]:
        op.create_index(f"ix_income_{field}", "income", [field])


def migrate_values():
    """Create starting lists and one category per distinct existing value; link the rows."""
    connection = op.get_bind()
    categories = categories_table()
    users = connection.scalars(sa.select(sa.table("users", sa.column("id", sa.Uuid())).c.id)).all()
    # (user, scope) -> {key: category id}, and the next free position in that list.
    known: dict = defaultdict(dict)
    positions: dict = {}
    rows = []
    for user in users:
        for scope, names in DEFAULTS.items():
            for position, name in enumerate(names):
                category_id = uuid4()
                known[(user, scope)][key_of(name)] = category_id
                rows.append(
                    dict(
                        id=category_id,
                        user_id=user,
                        scope=scope,
                        name=name,
                        key=key_of(name),
                        position=position,
                        archived=False,
                    )
                )
            positions[(user, scope)] = len(names)

    # Count spellings per (user, scope, key) to name merged categories by the commonest one.
    spellings: dict = defaultdict(Counter)
    values = []
    for table, scope, _, _ in SOURCES:
        records = record_table(table)
        result = connection.execute(
            sa.select(records.c.user_id, records.c.category, sa.func.count()).group_by(
                records.c.user_id, records.c.category
            )
        )
        for user, raw, count in result:
            key = key_of(raw)
            if not key:
                if table not in REQUIRED:
                    continue
                key = "other"  # required categories were never blank; be safe anyway
            spellings[(user, scope, key)][clean(raw) or "Other"] += count
            values.append((table, scope, user, raw, key))

    for (user, scope, key), counter in sorted(spellings.items(), key=lambda item: str(item[0])):
        if key in known[(user, scope)]:
            continue
        name = min(counter.items(), key=spelling_rank)[0][:80]
        category_id = uuid4()
        known[(user, scope)][key] = category_id
        position = positions.get((user, scope), 0)
        positions[(user, scope)] = position + 1
        rows.append(
            dict(
                id=category_id,
                user_id=user,
                scope=scope,
                name=name,
                key=key,
                position=position,
                archived=False,
            )
        )
    if rows:
        op.bulk_insert(categories, rows)

    for table, scope, user, raw, key in values:
        records = record_table(table)
        connection.execute(
            records.update()
            .where(records.c.user_id == user, records.c.category == raw)
            .values(category_id=known[(user, scope)][key])
        )


def downgrade():
    require_online("downgrade")
    for field in ["received_on", "category_id", "user_id"]:
        op.drop_index(f"ix_income_{field}", "income")
    op.drop_table("income")

    for table, _, has_key, _ in SOURCES:
        with op.batch_alter_table(table) as batch:
            batch.add_column(sa.Column("category", sa.String(80), nullable=True))
            if has_key:
                batch.add_column(sa.Column("category_key", sa.String(80), nullable=True))

    connection = op.get_bind()
    categories = categories_table()
    names = connection.execute(sa.select(categories.c.id, categories.c.name)).all()
    for table, _, has_key, _ in SOURCES:
        records = record_table(table, has_key)
        for category_id, name in names:
            values = dict(category=name, category_key=key_of(name)) if has_key else {}
            values.setdefault("category", name)
            connection.execute(
                records.update().where(records.c.category_id == category_id).values(**values)
            )
        connection.execute(records.update().where(records.c.category.is_(None)).values(category=""))

    for table, _, has_key, indexed in reversed(SOURCES):
        with op.batch_alter_table(table) as batch:
            if table == "budgets":
                batch.drop_constraint("uq_budgets_category", type_="unique")
            if indexed:
                batch.drop_index(f"ix_{table}_category_id")
            batch.drop_constraint(f"fk_{table}_category_owner", type_="foreignkey")
            batch.drop_column("category_id")
            batch.alter_column("category", existing_type=sa.String(80), nullable=False)
            if has_key:
                batch.alter_column("category_key", existing_type=sa.String(80), nullable=False)
            if table == "budgets":
                batch.create_unique_constraint(
                    "uq_budgets_category", ["user_id", "category_key", "currency"]
                )
    op.drop_index("ix_categories_user_id", "categories")
    op.drop_table("categories")
