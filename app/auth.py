from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time
from base64 import urlsafe_b64decode, urlsafe_b64encode
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from .config import AppSettings, load_settings

security = HTTPBasic(auto_error=False)
APP_SESSION_COOKIE_NAME = "nrf_session"
AUTH_SESSION_TOKEN_VERSION = 1
DEFAULT_AUTH_SESSION_TTL_SECONDS = 12 * 60 * 60
PASSWORD_HASH_SCHEME = "pbkdf2_sha256"
DEFAULT_PASSWORD_HASH_ITERATIONS = 100_000
HAL_CHAT_ROLES = frozenset({"dashboard:read", "hal:operator"})


@dataclass(frozen=True, slots=True)
class AuthenticatedUser:
    username: str
    display_name: str
    password_hash: str
    roles: frozenset[str]


def hash_password(password: str, *, iterations: int = DEFAULT_PASSWORD_HASH_ITERATIONS) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"{PASSWORD_HASH_SCHEME}${iterations}${salt.hex()}${digest.hex()}"


def _verify_password(password: str, password_hash: str) -> bool:
    parts = password_hash.split("$")
    if len(parts) != 4 or parts[0] != PASSWORD_HASH_SCHEME:
        return False
    iterations = int(parts[1])
    salt = bytes.fromhex(parts[2])
    expected = bytes.fromhex(parts[3])
    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(actual, expected)


def _session_secret() -> bytes:
    secret = load_settings().auth_users_json.encode("utf-8")
    return hashlib.sha256(secret).digest()


def create_auth_session_token(user: AuthenticatedUser, *, ttl_seconds: int = DEFAULT_AUTH_SESSION_TTL_SECONDS) -> str:
    payload = {
        "v": AUTH_SESSION_TOKEN_VERSION,
        "u": user.username,
        "exp": int(time.time()) + ttl_seconds,
    }
    body = urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8")).decode("ascii")
    sig = hmac.new(_session_secret(), body.encode("ascii"), hashlib.sha256).hexdigest()
    return f"{body}.{sig}"


def _parse_auth_session_token(token: str) -> AuthenticatedUser | None:
    try:
        body, sig = token.rsplit(".", 1)
    except ValueError:
        return None
    expected = hmac.new(_session_secret(), body.encode("ascii"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig):
        return None
    try:
        payload = json.loads(urlsafe_b64decode(body.encode("ascii")).decode("utf-8"))
    except (ValueError, json.JSONDecodeError):
        return None
    if payload.get("v") != AUTH_SESSION_TOKEN_VERSION:
        return None
    if int(payload.get("exp") or 0) < int(time.time()):
        return None
    username = str(payload.get("u") or "")
    return load_user(username)


def load_users(settings: AppSettings | None = None) -> dict[str, AuthenticatedUser]:
    settings = settings or load_settings()
    try:
        rows = json.loads(settings.auth_users_json)
    except json.JSONDecodeError as exc:
        raise RuntimeError("APP_AUTH_USERS_JSON is invalid JSON") from exc
    users: dict[str, AuthenticatedUser] = {}
    for row in rows:
        username = str(row.get("username") or "").strip()
        if not username:
            continue
        password = str(row.get("password") or "")
        password_hash = str(row.get("password_hash") or "")
        if password and not password_hash:
            password_hash = hash_password(password)
        users[username] = AuthenticatedUser(
            username=username,
            display_name=str(row.get("display_name") or username),
            password_hash=password_hash,
            roles=frozenset(str(role) for role in (row.get("roles") or [])),
        )
    return users


def load_user(username: str) -> AuthenticatedUser | None:
    return load_users().get(username.strip())


def authenticate_credentials(username: str, password: str) -> AuthenticatedUser:
    user = load_user(username)
    if user is None or not _verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return user


def _dev_auth_user(settings: AppSettings) -> AuthenticatedUser | None:
    if not settings.hal_browser_dev_auth:
        return None
    users = load_users(settings)
    for user in users.values():
        if HAL_CHAT_ROLES.intersection(user.roles):
            return user
    return None


def authenticate(
    request: Request,
    credentials: Annotated[HTTPBasicCredentials | None, Depends(security)],
) -> AuthenticatedUser:
    settings = load_settings()
    token = request.cookies.get(APP_SESSION_COOKIE_NAME)
    if token:
        user = _parse_auth_session_token(token)
        if user is not None:
            return user

    if credentials is not None and credentials.username:
        return authenticate_credentials(credentials.username, credentials.password)

    dev_user = _dev_auth_user(settings)
    if dev_user is not None:
        return dev_user

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")


def require_hal_chat_access(user: Annotated[AuthenticatedUser, Depends(authenticate)]) -> AuthenticatedUser:
    if not HAL_CHAT_ROLES.intersection(user.roles):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="HAL chat access denied")
    return user
