from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core import config
from app.infrastructure.database import get_session
from app.modules.auth.repository import AuthRepository
from app.modules.auth.service import AuthError, AuthService


def get_auth_service(session: Session = Depends(get_session)):
    return AuthService(AuthRepository(session))


def require_csrf(request: Request, service: AuthService = Depends(get_auth_service)):
    origin = request.headers.get("origin")
    if origin and origin not in config.CORS_ORIGINS:
        raise AuthError(403, "csrf", "Security check failed. Refresh and try again.")
    service.check_csrf(
        request.cookies.get(config.SESSION_COOKIE_NAME), request.headers.get("x-csrf-token")
    )


def current_user(request: Request, service: AuthService = Depends(get_auth_service)):
    user = service.current_user(request.cookies.get(config.SESSION_COOKIE_NAME))
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        require_csrf(request, service)
    return user
