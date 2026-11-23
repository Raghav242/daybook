from sqlalchemy.orm import Session

CHUNK = 100


def insert_ignoring_duplicates(session: Session, model, rows: list[dict], keys: list[str]):
    """Insert rows, skipping any that violate the unique ``keys`` (concurrency-safe)."""
    if not rows:
        return
    dialect = session.get_bind().dialect.name
    if dialect == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    elif dialect == "sqlite":
        from sqlalchemy.dialects.sqlite import insert
    else:  # pragma: no cover - only PostgreSQL and the SQLite test adapter are supported.
        raise RuntimeError(f"Unsupported database dialect: {dialect}")
    for start in range(0, len(rows), CHUNK):
        statement = insert(model).values(rows[start : start + CHUNK])
        session.execute(statement.on_conflict_do_nothing(index_elements=keys))
