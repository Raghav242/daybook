"""Explicit account creation, legacy ownership assignment, and auth cleanup."""

import argparse
from getpass import getpass

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.infrastructure.database import engine
from app.modules.auth.models import User
from app.modules.auth.repository import AuthRepository
from app.modules.auth.schemas import Credentials
from app.modules.auth.service import hasher, normalize_username, now_utc
from app.modules.bills.models import Bill
from app.modules.calendar.models import CalendarEntry
from app.modules.groceries.models import Grocery
from app.modules.settings.models import Settings
from app.modules.tasks.models import Task

MODELS = (Task, CalendarEntry, Grocery, Bill, Settings)


def claim_legacy(session, owner, apply=False):
    user = session.scalar(select(User).where(User.normalized_username == normalize_username(owner)))
    if not user:
        raise ValueError("Selected owner does not exist. Create the account first.")
    counts = {
        m.__tablename__: session.scalar(
            select(func.count()).select_from(m).where(m.user_id.is_(None))
        )
        for m in MODELS
    }
    print(f"Unowned records: {counts}; selected owner: {user.username} ({user.id})")
    if not apply:
        print("Preview only. Use --apply to explicitly assign these unowned records.")
        return counts
    if counts["settings"] and session.scalar(select(Settings).where(Settings.user_id == user.id)):
        raise ValueError(
            "Owner already has settings. Resolve the conflicting settings explicitly first."
        )
    for model in MODELS:
        session.execute(update(model).where(model.user_id.is_(None)).values(user_id=user.id))
    session.commit()
    return counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create-user")
    create.add_argument("--username", required=True)
    claim = commands.add_parser("claim-legacy")
    claim.add_argument("--owner", required=True)
    claim.add_argument("--apply", action="store_true")
    commands.add_parser("prune-auth")
    args = parser.parse_args()
    with Session(engine) as session:
        if args.command == "create-user":
            password = getpass("Password (5–128 characters): ")
            if password != getpass("Confirm password: "):
                raise ValueError("Passwords do not match.")
            credentials = Credentials(username=args.username, password=password)
            if len(password) < 5:
                raise ValueError("Use at least 5 characters.")
            if AuthRepository(session).user_by_name(normalize_username(credentials.username)):
                raise ValueError("Username is unavailable.")
            session.add(
                User(
                    username=credentials.username,
                    normalized_username=normalize_username(credentials.username),
                    password_hash=hasher.hash(password),
                    created_at=now_utc(),
                )
            )
            session.commit()
            print("Account created. No personal records were assigned.")
        elif args.command == "claim-legacy":
            claim_legacy(session, args.owner, args.apply)
        else:
            AuthRepository(session).prune(now_utc())


if __name__ == "__main__":
    main()
