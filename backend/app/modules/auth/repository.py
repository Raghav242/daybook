from datetime import timedelta

from sqlalchemy import case, delete, select
from sqlalchemy.orm import Session

from app.modules.auth.models import AuthRateLimit, AuthSession, User
from app.modules.settings.models import Settings


class AuthRepository:
    def __init__(self, session: Session):
        self.session = session

    def user_by_name(self, normalized):
        return self.session.scalar(select(User).where(User.normalized_username == normalized))

    def user_by_id(self, user_id):
        return self.session.get(User, user_id)

    def add_user(self, user):
        self.session.add(user)
        self.session.flush()

    def initialize_settings(self, user_id):
        self.session.add(Settings(user_id=user_id))

    def session_by_hash(self, token_hash, now):
        return self.session.scalar(
            select(AuthSession).where(
                AuthSession.token_hash == token_hash, AuthSession.expires_at > now
            )
        )

    def revoke(self, token_hash):
        self.session.execute(delete(AuthSession).where(AuthSession.token_hash == token_hash))

    def add_session(self, record):
        self.session.add(record)

    def commit(self):
        self.session.commit()

    def rollback(self):
        self.session.rollback()

    def consume_limit(self, key, now, seconds):
        # Atomic increments across API workers; no in-process counter or raw IP storage.
        if self.session.bind.dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import insert
        else:
            from sqlalchemy.dialects.sqlite import insert
        expired = AuthRateLimit.expires_at <= now
        statement = insert(AuthRateLimit).values(
            key=key, attempts=1, expires_at=now + timedelta(seconds=seconds)
        )
        statement = statement.on_conflict_do_update(
            index_elements=[AuthRateLimit.key],
            set_={
                "attempts": case((expired, 1), else_=AuthRateLimit.attempts + 1),
                "expires_at": case(
                    (expired, now + timedelta(seconds=seconds)), else_=AuthRateLimit.expires_at
                ),
            },
        ).returning(AuthRateLimit.attempts)
        attempts = self.session.scalar(statement)
        self.session.commit()
        return attempts

    def prune(self, now):
        self.session.execute(delete(AuthSession).where(AuthSession.expires_at <= now))
        self.session.execute(delete(AuthRateLimit).where(AuthRateLimit.expires_at <= now))
        self.session.commit()
