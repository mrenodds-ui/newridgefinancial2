from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
from datetime import datetime, timezone
from pathlib import Path


_AI_WORKSPACE_HANDLE_SECRET = os.getenv("HAL_PATH_HANDLE_SECRET", "").strip().encode("utf-8") or secrets.token_bytes(32)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def get_hal_allowed_base_path() -> Path:
    configured = os.getenv("HAL_ALLOWED_BASE_PATH", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return _repo_root().resolve()


def resolve_within_hal_allowed_base(candidate: str | Path, *, label: str) -> Path:
    allowed_base = get_hal_allowed_base_path()
    candidate_path = Path(candidate).expanduser()
    resolved = candidate_path.resolve() if candidate_path.is_absolute() else (allowed_base / candidate_path).resolve()
    if resolved != allowed_base and allowed_base not in resolved.parents:
        raise ValueError(f"{label} is outside HAL allowed base path: {resolved}")
    return resolved


def resolve_dedicated_hal_directory(candidate: str | Path, *, label: str, directory_name: str) -> Path:
    allowed_base = get_hal_allowed_base_path()
    resolved = resolve_within_hal_allowed_base(candidate, label=label)
    if resolved.parent != allowed_base or resolved.name != directory_name:
        raise ValueError(
            f"{label} must resolve to the dedicated '{directory_name}' directory directly under HAL allowed base path: {resolved}"
        )
    return resolved


def get_ai_workspace_path() -> Path:
    configured = os.getenv("HAL_AI_WORKSPACE_PATH", "").strip()
    candidate = Path(configured) if configured else Path("AI_Workspace")
    workspace = resolve_dedicated_hal_directory(candidate, label="HAL AI workspace path", directory_name="AI_Workspace")
    workspace.mkdir(parents=True, exist_ok=True)
    return workspace


def workspace_relative_path(candidate: str | Path) -> str:
    workspace = get_ai_workspace_path()
    resolved = ensure_within_ai_workspace(candidate)
    try:
        return resolved.relative_to(workspace).as_posix()
    except ValueError:
        return str(resolved)


def _sign_ai_workspace_relative_path(relative_path: str) -> str:
    return hmac.new(_AI_WORKSPACE_HANDLE_SECRET, relative_path.encode("utf-8"), hashlib.sha256).hexdigest()[:32]


def create_ai_workspace_handle(candidate: str | Path) -> str:
    relative_path = workspace_relative_path(candidate)
    encoded_path = base64.urlsafe_b64encode(relative_path.encode("utf-8")).decode("ascii").rstrip("=")
    signature = _sign_ai_workspace_relative_path(relative_path)
    return f"{encoded_path}.{signature}"


def resolve_ai_workspace_handle(handle: str, *, label: str) -> Path:
    normalized_handle = str(handle or "").strip()
    encoded_path, separator, signature = normalized_handle.rpartition(".")
    if not encoded_path or not separator or not signature:
      raise ValueError(f"{label} is invalid.")
    padding = "=" * (-len(encoded_path) % 4)
    try:
        relative_path = base64.urlsafe_b64decode(f"{encoded_path}{padding}".encode("ascii")).decode("utf-8")
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError(f"{label} is invalid.") from exc
    expected_signature = _sign_ai_workspace_relative_path(relative_path)
    if not hmac.compare_digest(signature, expected_signature):
        raise ValueError(f"{label} is invalid.")
    return ensure_within_ai_workspace(relative_path)


def ensure_within_ai_workspace(candidate: str | Path) -> Path:
    workspace = get_ai_workspace_path()
    candidate_path = Path(candidate).expanduser()
    if candidate_path.is_absolute():
        resolved = candidate_path.resolve()
    else:
        normalized = Path(str(candidate).replace("\\", "/"))
        if normalized.parts and normalized.parts[0] == workspace.name:
            normalized = Path(*normalized.parts[1:])
        resolved = (workspace / normalized).resolve()
    if resolved != workspace and workspace not in resolved.parents:
        raise ValueError(f"Path is outside HAL AI workspace: {resolved}")
    return resolved


def get_ai_activity_log_path() -> Path:
    log_path = ensure_within_ai_workspace(get_ai_workspace_path() / "ai_activity.log")
    log_path.touch(exist_ok=True)
    return log_path


def get_ai_review_plan_directory() -> Path:
    review_dir = ensure_within_ai_workspace(get_ai_workspace_path() / "review_plans")
    review_dir.mkdir(parents=True, exist_ok=True)
    return review_dir


def append_ai_activity_log(*, tier: str, actor: str, action: str, detail: str) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    line = f"[{timestamp}] {tier.upper()} {actor} {action}: {' '.join(str(detail).split())}\n"
    log_path = get_ai_activity_log_path()
    with log_path.open("a", encoding="utf-8", newline="") as handle:
        handle.write(line)
    return str(log_path)


def _slugify(value: str, *, fallback: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return slug[:48] or fallback


def write_review_step_file(
    *,
    tier: str,
    actor: str,
    action: str,
    summary: str,
    payload: dict[str, object],
) -> str:
    created_at_utc = datetime.now(timezone.utc).isoformat()
    file_name = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{_slugify(action, fallback='review-step')}.json"
    file_path = ensure_within_ai_workspace(get_ai_review_plan_directory() / file_name)
    document = {
        "created_at_utc": created_at_utc,
        "tier": tier,
        "actor": actor,
        "action": action,
        "summary": summary,
        "approval_required": True,
        "status": "pending_human_approval",
        "payload": payload,
    }
    file_path.write_text(json.dumps(document, indent=2), encoding="utf-8", newline="\n")
    return str(file_path)


def read_review_step_file(review_plan_path: str | Path) -> tuple[Path, dict[str, object]]:
    file_path = ensure_within_ai_workspace(review_plan_path)
    if not file_path.exists():
        raise FileNotFoundError(f"Review plan file does not exist: {file_path}")
    document = json.loads(file_path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError("Review plan file must contain a JSON object.")
    return file_path, document


def update_review_step_file(
    *,
    review_plan_path: str | Path,
    status: str,
    actor: str,
    extra_fields: dict[str, object] | None = None,
) -> str:
    file_path, document = read_review_step_file(review_plan_path)
    document["status"] = status
    document["reviewed_at_utc"] = datetime.now(timezone.utc).isoformat()
    document["reviewer_actor"] = actor
    if extra_fields:
        document.update(extra_fields)
    file_path.write_text(json.dumps(document, indent=2), encoding="utf-8", newline="\n")
    return str(file_path)