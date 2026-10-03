from fastapi import APIRouter, Depends, Request, Response

from app.core import config
from app.modules.auth.dependencies import current_user, get_auth_service, require_csrf
from app.modules.auth.schemas import AuthOutput, Credentials
from app.modules.auth.service import AuthService, csrf_for

router = APIRouter(prefix="/auth", tags=["auth"])


def set_cookie(response, token, seconds=None):
    response.set_cookie(
        config.SESSION_COOKIE_NAME,
        token,
        httponly=True,
        secure=config.SESSION_COOKIE_SECURE,
        samesite="lax",
        max_age=seconds or config.SESSION_TTL_SECONDS,
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"


@router.get("/csrf")
def csrf(request: Request, response: Response, service: AuthService = Depends(get_auth_service)):
    old_token = request.cookies.get(config.SESSION_COOKIE_NAME)
    token = service.bootstrap(old_token, request.client.host)
    if token != old_token:
        set_cookie(response, token, 1800)
    response.headers["Cache-Control"] = "no-store"
    return {"csrf_token": csrf_for(token)}


@router.post(
    "/register", response_model=AuthOutput, status_code=201, dependencies=[Depends(require_csrf)]
)
def register(
    data: Credentials,
    request: Request,
    response: Response,
    service: AuthService = Depends(get_auth_service),
):
    user, token = service.register(
        data, request.cookies.get(config.SESSION_COOKIE_NAME), request.client.host
    )
    set_cookie(response, token)
    return {"user": user, "csrf_token": csrf_for(token)}


@router.post("/login", response_model=AuthOutput, dependencies=[Depends(require_csrf)])
def login(
    data: Credentials,
    request: Request,
    response: Response,
    service: AuthService = Depends(get_auth_service),
):
    user, token = service.login(
        data, request.cookies.get(config.SESSION_COOKIE_NAME), request.client.host
    )
    set_cookie(response, token)
    return {"user": user, "csrf_token": csrf_for(token)}


@router.get("/me", response_model=AuthOutput)
def me(request: Request, response: Response, user=Depends(current_user)):
    response.headers["Cache-Control"] = "no-store"
    return {"user": user, "csrf_token": csrf_for(request.cookies[config.SESSION_COOKIE_NAME])}


@router.post("/logout", status_code=204)
def logout(
    request: Request,
    response: Response,
    user=Depends(current_user),
    service: AuthService = Depends(get_auth_service),
):
    service.logout(request.cookies[config.SESSION_COOKIE_NAME])
    response.delete_cookie(
        config.SESSION_COOKIE_NAME,
        path="/",
        httponly=True,
        secure=config.SESSION_COOKIE_SECURE,
        samesite="lax",
    )
    response.headers["Cache-Control"] = "no-store"
