from __future__ import annotations

from base64 import urlsafe_b64decode, urlsafe_b64encode
import binascii
from dataclasses import dataclass
from functools import lru_cache
import hashlib
import hmac
import json
import secrets
import time

from fastapi import Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from .config_runtime import get_env_setting, is_production_like_app_environment


security = HTTPBasic(auto_error=False)
PASSWORD_HASH_SCHEME = "pbkdf2_sha256"
DEFAULT_PASSWORD_HASH_ITERATIONS = 100_000
DEFAULT_AUTH_SESSION_TTL_SECONDS = 12 * 60 * 60
AUTH_SESSION_TOKEN_VERSION = 1
APP_SESSION_COOKIE_NAME = "nrf_session"


@dataclass(frozen=True, slots=True)
class AuthenticatedUser:
    username: str
    display_name: str
    password_hash: str
    roles: frozenset[str]


def _authentication_unconfigured_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Authentication is not configured. Set APP_AUTH_USERS_JSON in deployment configuration.",
    )


def _authentication_failed_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect username or password",
        headers={"WWW-Authenticate": "Basic"},
    )


def hash_password(password: str, *, iterations: int = DEFAULT_PASSWORD_HASH_ITERATIONS) -> str:
    normalized = str(password or "")
    if not normalized:
        raise ValueError("Auth password must not be empty")
    if iterations < 1:
        raise ValueError("Auth password hash iterations must be positive")

    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", normalized.encode("utf-8"), salt, iterations)
    return f"{PASSWORD_HASH_SCHEME}${iterations}${salt.hex()}${digest.hex()}"


def _parse_password_hash(password_hash: str) -> tuple[int, bytes, bytes]:
    parts = str(password_hash or "").split("$")
    if len(parts) != 4 or parts[0] != PASSWORD_HASH_SCHEME:
        raise ValueError(
            f"Auth password_hash must use {PASSWORD_HASH_SCHEME}$<iterations>$<salt_hex>$<digest_hex> format"
        )

    try:
        iterations = int(parts[1])
        salt = bytes.fromhex(parts[2])
        digest = bytes.fromhex(parts[3])
    except ValueError as exc:
        raise ValueError("Auth password_hash must contain valid numeric and hex values") from exc

    if iterations < 1:
        raise ValueError("Auth password_hash iterations must be positive")
    if not salt or not digest:
        raise ValueError("Auth password_hash must include non-empty salt and digest values")

    return iterations, salt, digest


def verify_password(password: str, password_hash: str) -> bool:
    iterations, salt, expected_digest = _parse_password_hash(password_hash)
    candidate_digest = hashlib.pbkdf2_hmac("sha256", str(password or "").encode("utf-8"), salt, iterations)
    return secrets.compare_digest(candidate_digest, expected_digest)


def _get_auth_session_ttl_seconds() -> int:
    raw_value = get_env_setting("APP_AUTH_SESSION_TTL_SECONDS", str(DEFAULT_AUTH_SESSION_TTL_SECONDS)).strip()
    try:
        ttl_seconds = int(raw_value)
    except ValueError as exc:
        raise RuntimeError("APP_AUTH_SESSION_TTL_SECONDS must be a positive integer") from exc
    if ttl_seconds < 1:
        raise RuntimeError("APP_AUTH_SESSION_TTL_SECONDS must be a positive integer")
    return ttl_seconds


def _get_auth_session_secret() -> bytes:
    configured_secret = get_env_setting("APP_AUTH_SESSION_SECRET", "")
    if configured_secret:
        return configured_secret.encode("utf-8")

    if is_production_like_app_environment():
        raise RuntimeError(
            "APP_AUTH_SESSION_SECRET is required when APP_ENV is unset, production, staging, "
            "or any non-development value. Set a dedicated random secret for deployment."
        )

    raw_users = get_env_setting("APP_AUTH_USERS_JSON", "")
    if not raw_users:
        raise RuntimeError("APP_AUTH_USERS_JSON is required for session authentication")
    return hashlib.sha256(f"nrf-auth-session:{raw_users}".encode("utf-8")).digest()


def _password_hash_fingerprint(password_hash: str) -> str:
    return hashlib.sha256(str(password_hash).encode("utf-8")).hexdigest()[:24]


def create_auth_session_token(user: AuthenticatedUser, *, issued_at: int | None = None) -> str:
    current_time = int(time.time() if issued_at is None else issued_at)
    payload = {
        "v": AUTH_SESSION_TOKEN_VERSION,
        "sub": user.username,
        "iat": current_time,
        "exp": current_time + _get_auth_session_ttl_seconds(),
        "pwd": _password_hash_fingerprint(user.password_hash),
    }
    payload_bytes = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    signature = hmac.new(_get_auth_session_secret(), payload_bytes, hashlib.sha256).hexdigest()
    encoded_payload = urlsafe_b64encode(payload_bytes).rstrip(b"=").decode("ascii")
    return f"{encoded_payload}.{signature}"


def _decode_auth_session_token(token: str) -> dict[str, object] | None:
    encoded_payload, separator, signature = str(token or "").partition(".")
    if not separator or not encoded_payload or not signature:
        return None

    try:
        padding = "=" * (-len(encoded_payload) % 4)
        payload_bytes = urlsafe_b64decode(f"{encoded_payload}{padding}".encode("ascii"))
    except (ValueError, binascii.Error):
        return None

    expected_signature = hmac.new(_get_auth_session_secret(), payload_bytes, hashlib.sha256).hexdigest()
    if not secrets.compare_digest(signature, expected_signature):
        return None

    try:
        payload = json.loads(payload_bytes)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def resolve_authenticated_user_from_session(request: Request) -> AuthenticatedUser | None:
    session_token = request.cookies.get(APP_SESSION_COOKIE_NAME)
    if not session_token:
        return None

    payload = _decode_auth_session_token(session_token)
    if payload is None:
        return None

    try:
        version = int(payload.get("v"))
        expires_at = int(payload.get("exp"))
    except (TypeError, ValueError):
        return None
    if version != AUTH_SESSION_TOKEN_VERSION or expires_at <= int(time.time()):
        return None

    username = str(payload.get("sub") or "").strip()
    if not username:
        return None

    user = get_user_registry().get(username)
    if user is None:
        return None

    if payload.get("pwd") != _password_hash_fingerprint(user.password_hash):
        return None

    return user


def build_auth_session_cookie_options(request: Request) -> dict[str, object]:
    forwarded_proto = str(request.headers.get("x-forwarded-proto") or "").split(",", 1)[0].strip().lower()
    return {
        "httponly": True,
        "samesite": "lax",
        "secure": request.url.scheme == "https" or forwarded_proto == "https",
        "path": "/",
        "max_age": _get_auth_session_ttl_seconds(),
    }


def clear_auth_session_cookie(response: Response) -> None:
    response.delete_cookie(APP_SESSION_COOKIE_NAME, path="/")


def _coerce_password_hash(item: dict[str, object]) -> str:
    configured_hash = str(item.get("password_hash") or "").strip()
    if configured_hash:
        _parse_password_hash(configured_hash)
        return configured_hash

    legacy_password = str(item.get("password") or "")
    if not legacy_password:
        raise ValueError("Each auth user must include password_hash or legacy password")
    return hash_password(legacy_password)


def _load_users_from_env() -> list[AuthenticatedUser]:
    raw_value = get_env_setting("APP_AUTH_USERS_JSON", "").strip()
    if not raw_value:
        return []

    parsed = json.loads(raw_value)
    if not isinstance(parsed, list):
        raise ValueError("APP_AUTH_USERS_JSON must be a JSON array")

    users: list[AuthenticatedUser] = []
    for item in parsed:
        if not isinstance(item, dict):
            raise ValueError("Each auth user entry must be a JSON object")
        roles = frozenset(str(role) for role in item.get("roles", []))
        users.append(
            AuthenticatedUser(
                username=str(item["username"]),
                display_name=str(item.get("display_name") or item["username"]),
                password_hash=_coerce_password_hash(item),
                roles=roles,
            )
        )
    return users


@lru_cache(maxsize=1)
def get_user_registry() -> dict[str, AuthenticatedUser]:
    return {user.username: user for user in _load_users_from_env()}


def clear_user_registry_cache() -> None:
    get_user_registry.cache_clear()


def validate_auth_configuration() -> dict[str, object]:
    raw_value = get_env_setting("APP_AUTH_USERS_JSON", "").strip()
    if not raw_value:
        raise RuntimeError("APP_AUTH_USERS_JSON is required for application startup")

    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError as exc:
        raise RuntimeError("APP_AUTH_USERS_JSON is not valid JSON") from exc

    if not isinstance(parsed, list) or not parsed:
        raise RuntimeError("APP_AUTH_USERS_JSON must be a non-empty JSON array")

    try:
        users = _load_users_from_env()
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeError(str(exc)) from exc

    if not users:
        raise RuntimeError("APP_AUTH_USERS_JSON did not produce any valid users")

    role_union = set().union(*(user.roles for user in users))
    required_roles = {"dashboard:read", "hal:operator", "hal:index:refresh", "admin"}
    missing_roles = sorted(required_roles - role_union)
    if missing_roles:
        raise RuntimeError(f"APP_AUTH_USERS_JSON is missing required roles: {', '.join(missing_roles)}")

    session_ttl_seconds = _get_auth_session_ttl_seconds()
    if is_production_like_app_environment() and not get_env_setting("APP_AUTH_SESSION_SECRET", "").strip():
        raise RuntimeError(
            "APP_AUTH_SESSION_SECRET is required when APP_ENV is unset, production, staging, "
            "or any non-development value. Set a dedicated random secret for deployment."
        )

    clear_user_registry_cache()
    return {
        "user_count": len(users),
        "roles": sorted(role_union),
        "session_ttl_seconds": session_ttl_seconds,
    }


def get_service_credentials(required_role: str | None = None) -> tuple[str, str]:
    del required_role
    raise RuntimeError("Raw service credentials are no longer exposed; use get_service_user() for internal calls")


def get_service_user(required_role: str | None = None) -> AuthenticatedUser:
    for user in get_user_registry().values():
        if required_role is None or required_role in user.roles:
            return user
    raise RuntimeError("No configured user satisfies the requested role")


def authenticate_credentials(username: str, password: str) -> AuthenticatedUser:
    if not get_user_registry():
        raise _authentication_unconfigured_exception()

    normalized_username = str(username or "").strip()
    user = get_user_registry().get(normalized_username)
    if user is None or not verify_password(password, user.password_hash):
        raise _authentication_failed_exception()
    return user


def authenticate(request: Request, credentials: HTTPBasicCredentials | None = Depends(security)) -> AuthenticatedUser:
    if not get_user_registry():
        raise _authentication_unconfigured_exception()

    session_user = resolve_authenticated_user_from_session(request)
    if session_user is not None:
        return session_user

    if credentials is None:
        raise _authentication_failed_exception()

    return authenticate_credentials(credentials.username, credentials.password)


def require_roles(*required_roles: str):
    required = frozenset(required_roles)

    def dependency(user: AuthenticatedUser = Depends(authenticate)) -> AuthenticatedUser:
        if not required.issubset(user.roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Authenticated user does not have the required role for this HAL operation",
            )
        return user

    return dependency


# SoftDent Read Broker (Phase 1) read roles. ``hal:operator`` remains necessary
# for HAL chat operations but is not sufficient for patient/clinical/ledger
# facts; those require the corresponding SoftDent read role below.
SOFTDENT_READ_ROLE = "softdent:read"
SOFTDENT_PATIENT_READ_ROLE = "softdent:patient:read"
SOFTDENT_CLINICAL_READ_ROLE = "softdent:clinical:read"
SOFTDENT_LEDGER_READ_ROLE = "softdent:ledger:read"
SOFTDENT_NARRATIVE_DRAFT_ROLE = "softdent:narrative:draft"
SOFTDENT_EXPORT_REFRESH_ROLE = "softdent:export:refresh"

SOFTDENT_READ_ROLES = frozenset(
    {
        SOFTDENT_READ_ROLE,
        SOFTDENT_PATIENT_READ_ROLE,
        SOFTDENT_CLINICAL_READ_ROLE,
        SOFTDENT_LEDGER_READ_ROLE,
        SOFTDENT_NARRATIVE_DRAFT_ROLE,
        SOFTDENT_EXPORT_REFRESH_ROLE,
    }
)


def user_has_roles(user: AuthenticatedUser, *roles: str) -> bool:
    return frozenset(roles).issubset(user.roles)