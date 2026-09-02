from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.csrf import CSRF_COOKIE_NAME
from app.core.dependencies import get_auth_service, get_current_admin_user, get_container, get_session
from app.core.rate_limiter import rate_limit_login_dependency
from db.models.entities import AdminUser
from db.schemas.auth import AuthResponse, LoginRequest
from services.auth_service import AuthenticationError, AuthService, admin_user_read

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=AuthResponse)
async def login(
    request: LoginRequest,
    http_request: Request,
    response: Response,
    service: AuthService = Depends(get_auth_service),
    session: AsyncSession = Depends(get_session),
    _: None = Depends(rate_limit_login_dependency),
) -> AuthResponse:
    try:
        user = await service.authenticate(request.username, request.password)
    except AuthenticationError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    token = service.create_token(user)
    container = get_container(http_request)
    # Secure has to follow the actual request scheme, not APP_ENV: the documented
    # way to demo this app is a public Cloudflare HTTPS tunnel while APP_ENV is
    # still "development", and keying off the env alone shipped the session
    # cookie over that tunnel without the Secure flag.
    forwarded_proto = (http_request.headers.get("x-forwarded-proto") or "").split(",")[0].strip().lower()
    is_https = forwarded_proto == "https" or http_request.url.scheme == "https"
    secure_cookie = is_https or service.settings.app_env == "production"
    response.set_cookie(
        "admin_session",
        token,
        httponly=True,
        samesite="lax",
        secure=secure_cookie,
        max_age=service.settings.admin_session_ttl_seconds,
        path="/",
    )
    if container.csrf_protection:
        csrf_token = await container.csrf_protection.generate_token()
        response.set_cookie(
            CSRF_COOKIE_NAME,
            csrf_token,
            httponly=False,
            samesite="lax",
            secure=secure_cookie,
            max_age=service.settings.admin_session_ttl_seconds,
            path="/",
        )
    await session.commit()
    return AuthResponse(user=admin_user_read(user))


@router.post("/logout")
async def logout(request: Request, response: Response) -> dict[str, str]:
    response.delete_cookie("admin_session", path="/")
    response.delete_cookie(CSRF_COOKIE_NAME, path="/")
    container = getattr(request.app.state, "container", None)
    if container and container.csrf_protection:
        csrf_cookie = request.cookies.get(CSRF_COOKIE_NAME, "")
        if csrf_cookie:
            await container.csrf_protection.invalidate_token(csrf_cookie)
    return {"status": "ok"}


@router.get("/me", response_model=AuthResponse)
async def me(user: AdminUser = Depends(get_current_admin_user)) -> AuthResponse:
    return AuthResponse(user=admin_user_read(user))
