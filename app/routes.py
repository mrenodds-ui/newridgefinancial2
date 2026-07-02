from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel

from .auth import (
    APP_SESSION_COOKIE_NAME,
    AuthenticatedUser,
    authenticate,
    authenticate_credentials,
    create_auth_session_token,
    require_hal_chat_access,
)
from .hal_chat import HalChatRequest, HalChatResponse, generate_hal_chat_response

router = APIRouter(tags=["HAL"])


class AuthSessionResponse(BaseModel):
    username: str
    display_name: str
    roles: list[str]


class AuthLoginRequest(BaseModel):
    username: str
    password: str


class AuthLogoutResponse(BaseModel):
    message: str


def _session_response(user: AuthenticatedUser) -> AuthSessionResponse:
    return AuthSessionResponse(
        username=user.username,
        display_name=user.display_name,
        roles=sorted(user.roles),
    )


@router.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "hal-browser-api"}


@router.get("/auth/session", response_model=AuthSessionResponse)
@router.get("/api/auth/session", response_model=AuthSessionResponse)
def get_auth_session(user: AuthenticatedUser = Depends(authenticate)) -> AuthSessionResponse:
    return _session_response(user)


@router.post("/auth/login", response_model=AuthSessionResponse)
@router.post("/api/auth/login", response_model=AuthSessionResponse)
def login_auth_session(payload: AuthLoginRequest, response: Response) -> AuthSessionResponse:
    user = authenticate_credentials(payload.username.strip(), payload.password)
    response.set_cookie(
        APP_SESSION_COOKIE_NAME,
        create_auth_session_token(user),
        httponly=True,
        samesite="lax",
        max_age=12 * 60 * 60,
    )
    return _session_response(user)


@router.post("/auth/logout", response_model=AuthLogoutResponse)
@router.post("/api/auth/logout", response_model=AuthLogoutResponse)
def logout_auth_session(response: Response) -> AuthLogoutResponse:
    response.delete_cookie(APP_SESSION_COOKIE_NAME)
    return AuthLogoutResponse(message="Signed out")


@router.post("/api/hal/chat", response_model=HalChatResponse)
def post_hal_chat(
    payload: HalChatRequest,
    _user: AuthenticatedUser = Depends(require_hal_chat_access),
) -> HalChatResponse:
    return generate_hal_chat_response(payload)
