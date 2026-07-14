"""SoftDent Excel-temp reliability helpers (hal-10576).

Retry/backoff when SoftDent or Excel holds a transient share lock on
%TEMP%\\SDWIN* workbooks or exports under SoftDentReportExports.

Read-only regarding SoftDent write-back. Never invents dollars.
Does NOT re-export Register hoping Ins Plan > 0.
"""

from __future__ import annotations

import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, TypeVar

T = TypeVar("T")

# Moonshot 10576 — 3 attempts, 100ms / 500ms / 1000ms between tries
EXCEL_TEMP_RETRY_DELAYS_SEC: tuple[float, ...] = (0.1, 0.5, 1.0)
EXPORT_ROOT = Path(r"C:\SoftDentReportExports")
ERROR_TEMP_FILE_LOCKED = "temp_file_locked"
ERROR_TRUNCATED_WORKBOOK = "truncated_workbook"
ERROR_NO_EXPORTS = "no_exports"
ERROR_UNREADABLE = "unreadable"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def is_excel_temp_lock_error(exc: BaseException) -> bool:
    """True for Windows share/lock style failures during Excel/export IO."""
    if isinstance(exc, PermissionError):
        return True
    if isinstance(exc, OSError):
        winerr = getattr(exc, "winerror", None)
        errno = getattr(exc, "errno", None)
        # 13=EACCES, 32=sharing violation (Windows), 11=EAGAIN
        if errno in (13, 11, 16) or winerr in (32, 33, 5):
            return True
        msg = str(exc).lower()
        if any(
            token in msg
            for token in (
                "being used by another process",
                "sharing violation",
                "permission denied",
                "access is denied",
                "locked",
                "errno 13",
            )
        ):
            return True
    name = type(exc).__name__
    if name in {"BadZipFile", "XLRDError", "InvalidFileException"}:
        # Truncated / half-written workbook often appears mid-SaveCopyAs
        msg = str(exc).lower()
        if "zip" in msg or "workbook" in msg or "bof" in msg or "compdoc" in msg:
            return True
    return False


def is_truncated_workbook_error(exc: BaseException) -> bool:
    name = type(exc).__name__
    if name in {"BadZipFile", "InvalidFileException"}:
        return True
    msg = str(exc).lower()
    return "badzipfile" in msg or "file is not a zip" in msg or "truncated" in msg


def call_with_excel_temp_retry(
    fn: Callable[[], T],
    *,
    delays_sec: tuple[float, ...] | list[float] | None = None,
) -> T:
    """Run ``fn`` with exponential-ish backoff on transient Excel/export locks."""
    delays = tuple(delays_sec) if delays_sec is not None else EXCEL_TEMP_RETRY_DELAYS_SEC
    attempts = max(1, len(delays) + 1)
    last_exc: BaseException | None = None
    for attempt in range(attempts):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if not is_excel_temp_lock_error(exc) and not is_truncated_workbook_error(exc):
                raise
            if attempt >= attempts - 1:
                break
            time.sleep(float(delays[min(attempt, len(delays) - 1)]))
    assert last_exc is not None
    raise last_exc


def open_path_probe(path: Path) -> None:
    """Raise if path cannot be opened for shared read (export still locked)."""
    with path.open("rb") as fh:
        fh.read(1)


def copy_file_with_retry(src: Path, dest: Path, *, delays_sec: tuple[float, ...] | None = None) -> Path:
    """Atomic copy with lock retry (SoftDent may still hold the source briefly)."""

    def _copy() -> Path:
        from softdent_practice_exports import atomic_copy_export

        meta = atomic_copy_export(src, dest)
        if not dest.is_file() or int(meta.get("bytes") or 0) < 1:
            raise OSError(f"atomic copy produced no file: {dest}")
        return dest

    return call_with_excel_temp_retry(_copy, delays_sec=delays_sec)


def list_sdwin_temp_candidates(*, temp_dir: Path | None = None, limit: int = 20) -> list[Path]:
    """List SoftDent Excel temp workbooks under %TEMP% (read-only)."""
    root = Path(temp_dir) if temp_dir is not None else Path(tempfile.gettempdir())
    if not root.is_dir():
        return []
    found: list[Path] = []
    try:
        children = sorted(root.iterdir(), key=lambda p: p.stat().st_mtime if p.is_file() else 0, reverse=True)
    except OSError:
        return []
    for child in children:
        if not child.is_file():
            continue
        name = child.name.upper()
        if not name.startswith("SDWIN"):
            continue
        if child.suffix.lower() not in {".csv", ".xls", ".xlsx", ".xlsm", ".tmp", ""}:
            # SoftDent often uses SDWIN123.CSV without worrying about blank suffix
            if "." in child.name and child.suffix.lower() not in {".csv", ".xls", ".xlsx", ".xlsm"}:
                continue
        found.append(child)
        if len(found) >= max(1, min(int(limit), 100)):
            break
    return found


def collections_export_health(
    *,
    dest_root: Path | None = None,
    temp_dir: Path | None = None,
) -> dict[str, Any]:
    """HAL/API health for Collections/Register Excel-temp readability (hal-10576).

    Does not invent Ins Plan dollars or recommend Register re-export for Ins Plan > 0.
    """
    root = Path(dest_root) if dest_root is not None else EXPORT_ROOT
    checked: list[dict[str, Any]] = []
    error_code: str | None = None
    ready = True
    detail = ""

    patterns = (
        "COL*.XLS",
        "COL*.xls",
        "collections*.xls",
        "collections*.xlsx",
        "Collection*.xls",
        "REG*.XLS",
        "REG*.xls",
        "register*.xls",
        "register*.xlsx",
    )
    candidates: list[Path] = []
    if root.is_dir():
        seen: set[str] = set()
        for pat in patterns:
            for hit in root.glob(pat):
                key = str(hit).lower()
                if key in seen:
                    continue
                seen.add(key)
                candidates.append(hit)
        candidates.sort(key=lambda p: p.stat().st_mtime if p.is_file() else 0, reverse=True)

    temps = list_sdwin_temp_candidates(temp_dir=temp_dir, limit=8)
    probe_targets = (candidates[:5] + temps)[:8]

    if not probe_targets:
        ready = False
        error_code = ERROR_NO_EXPORTS
        detail = (
            f"No Collections/Register Excel exports under {root} and no SDWIN* temps. "
            "Export via SoftDent → Excel (never Printer). Empty ≠ $0; "
            "do not re-export Register hoping Ins Plan > 0 — use ERA-835 for insurance."
        )
    else:
        for path in probe_targets:
            row: dict[str, Any] = {"path": str(path), "ok": False}
            try:
                call_with_excel_temp_retry(lambda p=path: open_path_probe(p))
                row["ok"] = True
                row["sizeBytes"] = int(path.stat().st_size)
            except Exception as exc:  # noqa: BLE001
                row["error"] = f"{type(exc).__name__}:{exc}"
                if is_truncated_workbook_error(exc):
                    error_code = ERROR_TRUNCATED_WORKBOOK
                elif is_excel_temp_lock_error(exc):
                    error_code = ERROR_TEMP_FILE_LOCKED
                else:
                    error_code = ERROR_UNREADABLE
                ready = False
                detail = (
                    f"Excel/export IO failed on {path.name}: {type(exc).__name__}. "
                    "SoftDent/Excel may still hold the temp — retry after SoftDent finishes SaveCopyAs. "
                    "Do not invent dollars; Ins Plan $0 still requires ERA-835."
                )
            checked.append(row)
            if not ready:
                break

    if ready and not detail:
        detail = (
            "Collections/Register export paths are readable (Excel-temp lock clear). "
            "Reliability only — does not invent Ins Plan dollars; ERA-835 still required when Register Ins Plan is $0."
        )

    return {
        "ok": True,
        "phase": "hal-10576",
        "collectionsExportReady": bool(ready),
        "errorCode": None if ready else error_code,
        "checkedPaths": checked,
        "exportRoot": str(root),
        "tempDir": str(temp_dir or Path(tempfile.gettempdir())),
        "sdwinTempCount": len(temps),
        "retryDelaysSec": list(EXCEL_TEMP_RETRY_DELAYS_SEC),
        "writeBack": False,
        "softDentWriteBack": False,
        "honesty": "empty_not_zero",
        "hint": detail,
        "refreshedAt": _utc_now(),
    }
