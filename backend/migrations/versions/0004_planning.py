"""Phase 2 planning: recurring tasks/bills, recipes, meal plans, expenses and budgets.

Upgrade preserves every existing record. Existing tasks and bills become standalone records
with no series. Accounts with saved preferences get the new Meals and Budget modules enabled.

Downgrade removes the Phase 2 tables and therefore permanently deletes recipes, meal plans,
grocery-addition receipts, expenses, budgets and recurrence definitions. Generated task and
bill occurrences are kept as ordinary standalone tasks and bills. Back up before downgrading.
"""

import sqlalchemy as sa
from alembic import context, op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

NEW_MODULES = ["meals", "budget"]


def owner():
    return sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False)


def series_columns(prefix):
    return [
        sa.Column("frequency", sa.String(10), nullable=False),
        sa.Column("repeat_interval", sa.Integer(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("until_date", sa.Date(), nullable=True),
        sa.Column("generated_through", sa.Date(), nullable=False),
        sa.UniqueConstraint("id", "user_id", name=f"uq_{prefix}_series_id_user"),
        sa.CheckConstraint(
            "frequency IN ('daily', 'weekly', 'monthly')", name=f"{prefix}_series_frequency"
        ),
        sa.CheckConstraint("repeat_interval >= 1", name=f"{prefix}_series_interval"),
        sa.CheckConstraint(
            "until_date IS NULL OR until_date >= start_date", name=f"{prefix}_series_until"
        ),
    ]


def link_occurrences(table, prefix):
    with op.batch_alter_table(table) as batch:
        batch.add_column(sa.Column("series_id", sa.Uuid(), nullable=True))
        batch.add_column(sa.Column("occurrence_date", sa.Date(), nullable=True))
        batch.create_index(f"ix_{table}_series_id", ["series_id"])
        batch.create_unique_constraint(
            f"uq_{table}_series_occurrence", ["series_id", "occurrence_date"]
        )
        batch.create_foreign_key(
            f"fk_{table}_series_owner",
            f"{prefix}_series",
            ["series_id", "user_id"],
            ["id", "user_id"],
        )
        batch.create_check_constraint(
            f"{prefix}_occurrence_date", "series_id IS NULL OR occurrence_date IS NOT NULL"
        )
        if table == "bills":
            batch.create_unique_constraint("uq_bills_id_user", ["id", "user_id"])


def unlink_occurrences(table, prefix):
    with op.batch_alter_table(table) as batch:
        if table == "bills":
            batch.drop_constraint("uq_bills_id_user", type_="unique")
        batch.drop_constraint(f"{prefix}_occurrence_date", type_="check")
        batch.drop_constraint(f"fk_{table}_series_owner", type_="foreignkey")
        batch.drop_constraint(f"uq_{table}_series_occurrence", type_="unique")
        batch.drop_index(f"ix_{table}_series_id")
        batch.drop_column("occurrence_date")
        batch.drop_column("series_id")


def set_modules(change):
    if context.is_offline_mode():
        # Offline SQL scripts cannot read rows; preferences are left unchanged there.
        print("-- Offline mode: enabled_modules preferences were not updated.")
        return
    settings = sa.table(
        "settings", sa.column("id", sa.Integer()), sa.column("enabled_modules", sa.JSON())
    )
    connection = op.get_bind()
    for row_id, modules in connection.execute(sa.select(settings.c.id, settings.c.enabled_modules)):
        updated = change(list(modules or []))
        if updated != modules:
            connection.execute(
                settings.update().where(settings.c.id == row_id).values(enabled_modules=updated)
            )


def upgrade():
    op.create_table(
        "task_series",
        sa.Column("id", sa.Uuid(), primary_key=True),
        owner(),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("priority", sa.String(10), nullable=False),
        sa.Column("category", sa.String(80), nullable=False),
        *series_columns("task"),
        sa.CheckConstraint("priority IN ('low', 'normal', 'high')", name="task_series_priority"),
    )
    op.create_index("ix_task_series_user_id", "task_series", ["user_id"])
    op.create_table(
        "bill_series",
        sa.Column("id", sa.Uuid(), primary_key=True),
        owner(),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        *series_columns("bill"),
        sa.CheckConstraint("amount >= 0", name="bill_series_amount_nonnegative"),
    )
    op.create_index("ix_bill_series_user_id", "bill_series", ["user_id"])
    link_occurrences("tasks", "task")
    link_occurrences("bills", "bill")

    op.create_table(
        "recipes",
        sa.Column("id", sa.Uuid(), primary_key=True),
        owner(),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("servings", sa.Integer(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.UniqueConstraint("id", "user_id", name="uq_recipes_id_user"),
        sa.CheckConstraint("servings > 0", name="recipe_servings_positive"),
    )
    op.create_index("ix_recipes_user_id", "recipes", ["user_id"])
    op.create_table(
        "recipe_ingredients",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("recipe_id", sa.Uuid(), nullable=False),
        owner(),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 3), nullable=False),
        sa.Column("unit", sa.String(40), nullable=False),
        sa.Column("category", sa.String(80), nullable=False),
        sa.CheckConstraint("quantity > 0", name="ingredient_quantity_positive"),
        sa.ForeignKeyConstraint(
            ["recipe_id", "user_id"],
            ["recipes.id", "recipes.user_id"],
            ondelete="CASCADE",
            name="fk_ingredients_recipe_owner",
        ),
    )
    op.create_index("ix_recipe_ingredients_recipe_id", "recipe_ingredients", ["recipe_id"])
    op.create_table(
        "grocery_imports",
        sa.Column("id", sa.Uuid(), primary_key=True),
        owner(),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("item_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "request_id", name="uq_grocery_imports_request"),
        sa.UniqueConstraint("id", "user_id", name="uq_grocery_imports_id_user"),
    )
    op.create_index("ix_grocery_imports_user_id", "grocery_imports", ["user_id"])
    op.create_table(
        "meal_plan_entries",
        sa.Column("id", sa.Uuid(), primary_key=True),
        owner(),
        sa.Column("plan_date", sa.Date(), nullable=False),
        sa.Column("meal", sa.String(10), nullable=False),
        sa.Column("recipe_id", sa.Uuid(), nullable=False),
        sa.Column("servings", sa.Integer(), nullable=False),
        sa.Column("grocery_import_id", sa.Uuid(), nullable=True),
        sa.CheckConstraint("servings > 0", name="meal_servings_positive"),
        sa.CheckConstraint(
            "meal IN ('breakfast', 'lunch', 'dinner', 'snack')", name="meal_plan_meal"
        ),
        sa.ForeignKeyConstraint(
            ["recipe_id", "user_id"],
            ["recipes.id", "recipes.user_id"],
            ondelete="CASCADE",
            name="fk_meal_plan_recipe_owner",
        ),
        sa.ForeignKeyConstraint(
            ["grocery_import_id", "user_id"],
            ["grocery_imports.id", "grocery_imports.user_id"],
            name="fk_meal_plan_import_owner",
        ),
    )
    for field in ["user_id", "plan_date", "recipe_id"]:
        op.create_index(f"ix_meal_plan_entries_{field}", "meal_plan_entries", [field])

    op.create_table(
        "expenses",
        sa.Column("id", sa.Uuid(), primary_key=True),
        owner(),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("category", sa.String(80), nullable=False),
        sa.Column("category_key", sa.String(80), nullable=False),
        sa.Column("spent_on", sa.Date(), nullable=False),
        sa.Column("note", sa.String(500), nullable=False),
        sa.Column("bill_id", sa.Uuid(), nullable=True),
        sa.CheckConstraint("amount > 0", name="expense_amount_positive"),
        sa.UniqueConstraint("bill_id", name="uq_expenses_bill_id"),
        sa.ForeignKeyConstraint(
            ["bill_id", "user_id"], ["bills.id", "bills.user_id"], name="fk_expenses_bill_owner"
        ),
    )
    for field in ["user_id", "spent_on"]:
        op.create_index(f"ix_expenses_{field}", "expenses", [field])
    op.create_table(
        "budgets",
        sa.Column("id", sa.Uuid(), primary_key=True),
        owner(),
        sa.Column("category", sa.String(80), nullable=False),
        sa.Column("category_key", sa.String(80), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.CheckConstraint("amount >= 0", name="budget_amount_nonnegative"),
        sa.UniqueConstraint("user_id", "category_key", "currency", name="uq_budgets_category"),
    )
    op.create_index("ix_budgets_user_id", "budgets", ["user_id"])
    set_modules(lambda modules: modules + [m for m in NEW_MODULES if m not in modules])


def downgrade():
    set_modules(lambda modules: [m for m in modules if m not in NEW_MODULES])
    for table in [
        "budgets",
        "expenses",
        "meal_plan_entries",
        "grocery_imports",
        "recipe_ingredients",
        "recipes",
    ]:
        op.drop_table(table)
    unlink_occurrences("bills", "bill")
    unlink_occurrences("tasks", "task")
    op.drop_table("bill_series")
    op.drop_table("task_series")
