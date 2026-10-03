import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError
from sqlalchemy.exc import IntegrityError

from app.core import config
from app.modules.auth.models import AuthSession, User
from app.modules.auth.repository import AuthRepository

hasher = PasswordHasher(type=Type.ID)
# Equal-cost password verification for unknown accounts.
dummy_hash = hasher.hash(secrets.token_urlsafe(32))


class AuthError(Exception):
    def __init__(self, status, code, message):
        self.status, self.code, self.message = status, code, message


def now_utc():
    return datetime.now(timezone.utc)


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def csrf_for(token):
    return digest("daybook-csrf:" + token)


def normalize_username(username):
    return username.strip().casefold()


class AuthService:
    def __init__(self, repository: AuthRepository):
        self.repository = repository

    def validate_session(self, token):
        if not token or len(token) > 128:
            return None
        return self.repository.session_by_hash(digest(token), now_utc())

    def current_user(self, token):
        session = self.validate_session(token)
        user = self.repository.user_by_id(session.user_id) if session and session.user_id else None
        if user is None:
            raise AuthError(401, "unauthenticated", "Please sign in to continue.")
        return user

    def check_csrf(self, token, provided):
        if (
            not self.validate_session(token)
            or not provided
            or not secrets.compare_digest(csrf_for(token), provided)
        ):
            raise AuthError(403, "csrf", "Security check failed. Refresh and try again.")

    def bootstrap(self, old_token, ip):
        if self.validate_session(old_token):
            return old_token
        if self.repository.consume_limit(digest("csrf:ip:" + ip), now_utc(), 300) > 60:
            raise AuthError(429, "rate_limited", "Too many attempts. Please try again later.")
        return self.new_session(None, old_token, seconds=1800)

    def new_session(self, user_id, old_token, seconds=None):
        if old_token:
            self.repository.revoke(digest(old_token))
        token = secrets.token_urlsafe(32)
        self.repository.add_session(
            AuthSession(
                token_hash=digest(token),
                user_id=user_id,
                expires_at=now_utc() + timedelta(seconds=seconds or config.SESSION_TTL_SECONDS),
            )
        )
        self.repository.commit()
        return token

    def limit(self, ip, username, operation):
        keys = [f"{operation}:ip:{ip}"]
        if operation == "login":
            keys.append("login:user:" + normalize_username(username))
        for key in keys:
            if (
                self.repository.consume_limit(
                    digest(key), now_utc(), config.AUTH_RATE_WINDOW_SECONDS
                )
                > config.AUTH_RATE_LIMIT
            ):
                raise AuthError(429, "rate_limited", "Too many attempts. Please try again later.")

    def register(self, credentials, old_token, ip):
        self.limit(ip, credentials.username, "register")
        password = credentials.password.get_secret_value()
        if len(password) < 5:
            raise AuthError(422, "validation", "Use a password with at least 5 characters.")
        user = User(
            username=credentials.username,
            normalized_username=normalize_username(credentials.username),
            password_hash=hasher.hash(password),
            created_at=now_utc(),
        )
        try:
            self.repository.add_user(user)
            self.repository.initialize_settings(user.id)
            token = self.new_session(user.id, old_token)
        except IntegrityError:
            self.repository.rollback()
            raise AuthError(409, "username_unavailable", "That username is unavailable.") from None
        return user, token

    def login(self, credentials, old_token, ip):
        self.limit(ip, credentials.username, "login")
        user = self.repository.user_by_name(normalize_username(credentials.username))
        password = credentials.password.get_secret_value()
        try:
            hasher.verify(user.password_hash if user else dummy_hash, password)
        except (VerificationError, InvalidHashError):
            raise AuthError(401, "invalid_credentials", "Invalid username or password.") from None
        if user is None:
            raise AuthError(401, "invalid_credentials", "Invalid username or password.")
        if hasher.check_needs_rehash(user.password_hash):
            user.password_hash = hasher.hash(password)
        return user, self.new_session(user.id, old_token)

    def logout(self, token):
        self.repository.revoke(digest(token))
        self.repository.commit()
