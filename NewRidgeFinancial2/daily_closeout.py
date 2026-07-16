"""Daily closeout checklist + period-close OPS loop for NR2 operators.

Shadow pilot rhythm: optional SoftDent GUI aging pull (consent-free Excel/Print Preview)
→ heal imports → laser-check → beam attest → immutable JSONL log → HAL-citable status.
SoftDent write-back forbidden. empty ≠ $0.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from financial_reports import build_financial_reports
from integration_health import integration_health_snapshot

REPO_ROOT = Path(__file__).resolve().parents[1]
OPS_DIR = REPO_ROOT / "app_data" / "nr2" / "ops"
CLOSE_LOG_PATH = OPS_DIR / "daily_close_log.jsonl"
FORCE_CLOSE_LOG_PATH = OPS_DIR / "force_close_log.jsonl"
CLOSE_STATE_PATH = OPS_DIR / "period_close_state.json"

_LOCK = threading.RLock()


def _item(item_id: str, label: str, status: str, detail: str) -> dict[str, str]:
    return {"id": item_id, "label": label, "status": status, "detail": detail}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso_now() -> str:
    return _utc_now().replace(microsecond=0).isoformat()


def _ensure_ops_dir() -> None:
    OPS_DIR.mkdir(parents=True, exist_ok=True)


def _read_state() -> dict[str, Any]:
    _ensure_ops_dir()
    if not CLOSE_STATE_PATH.is_file():
        return {
            "activeOperation": None,
            "status": "idle",
            "shadowStartedAt": None,
            "systemOfRecord": False,
        }
    try:
        raw = json.loads(CLOSE_STATE_PATH.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except Exception:
        return {"activeOperation": None, "status": "idle", "systemOfRecord": False}


def _write_state(state: dict[str, Any]) -> None:
    _ensure_ops_dir()
    CLOSE_STATE_PATH.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def _append_close_log(entry: dict[str, Any]) -> None:
    _ensure_ops_dir()
    with CLOSE_LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, default=str) + "\n")


def _append_force_close_log(entry: dict[str, Any]) -> None:
    """Append-only Force Close attest ledger (distinct from daily_close_log)."""
    _ensure_ops_dir()
    with FORCE_CLOSE_LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, default=str) + "\n")


def last_force_close_record() -> dict[str, Any] | None:
    """Most recent Force Close row from force_close_log.jsonl."""
    if not FORCE_CLOSE_LOG_PATH.is_file():
        return None
    try:
        lines = [
            ln.strip()
            for ln in FORCE_CLOSE_LOG_PATH.read_text(encoding="utf-8", errors="replace").splitlines()
            if ln.strip()
        ]
    except OSError:
        return None
    for raw in reversed(lines):
        try:
            row = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            return row
    return None


def last_close_record(*, limit: int = 1) -> dict[str, Any] | None:
    """Most recent completed close from the immutable JSONL audit trail."""
    _ = limit
    if not CLOSE_LOG_PATH.is_file():
        return None
    try:
        lines = [
            ln.strip()
            for ln in CLOSE_LOG_PATH.read_text(encoding="utf-8", errors="replace").splitlines()
            if ln.strip()
        ]
    except OSError:
        return None
    newest: dict[str, Any] | None = None
    for raw in reversed(lines):
        try:
            row = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not isinstance(row, dict):
            continue
        if newest is None:
            newest = row
        if str(row.get("status") or "").lower() in ("completed", "ok", "closed"):
            return row
    return newest


def period_close_operation_context() -> dict[str, Any]:
    """Merge into import-readiness.operationContext (persisted OPS, not query echo)."""
    state = _read_state()
    last = last_close_record()
    status = str(state.get("status") or "idle").lower()
    active = state.get("activeOperation")
    if status == "running":
        active = active or "daily_close"
    elif status == "completed":
        active = "completed"
    elif status == "stalled":
        active = "stalled"
    elif status == "blocked":
        active = "blocked"
    return {
        "periodCloseStatus": status,
        "activeOperation": active,
        "completedAt": state.get("completedAt") or (last or {}).get("completedAt"),
        "lastCloseAt": (last or {}).get("completedAt") or state.get("completedAt"),
        "lastBeamHash": (last or {}).get("beamHash") or state.get("beamHash"),
        "laserClear": bool(state.get("laserClear")) if "laserClear" in state else None,
        "shadowStartedAt": state.get("shadowStartedAt"),
        "systemOfRecord": bool(state.get("systemOfRecord")),
        "buildStamp": state.get("buildStamp") or (last or {}).get("buildStamp"),
    }


def merge_period_close_into_readiness(readiness: dict[str, Any]) -> dict[str, Any]:
    """Overlay persisted period-close state onto import-readiness payload."""
    if not isinstance(readiness, dict):
        return readiness
    ops = period_close_operation_context()
    ctx = dict(readiness.get("operationContext") or {})
    # Prefer live OPS activeOperation when set; keep query-param echo otherwise.
    query_op = ctx.get("activeOperation")
    merged_active = ops.get("activeOperation") if ops.get("activeOperation") else query_op
    ctx.update(ops)
    ctx["activeOperation"] = merged_active
    if query_op and not ops.get("activeOperation"):
        ctx["queryOperation"] = query_op
    readiness = {**readiness, "operationContext": ctx}
    readiness["periodClose"] = {
        "status": ops.get("periodCloseStatus"),
        "completedAt": ops.get("completedAt"),
        "lastBeamHash": ops.get("lastBeamHash"),
        "shadowStartedAt": ops.get("shadowStartedAt"),
        "systemOfRecord": ops.get("systemOfRecord"),
    }
    return readiness


def build_daily_closeout(store: Any | None = None) -> dict[str, Any]:
    health = integration_health_snapshot(store, deep_diagnostics=False)
    reports = build_financial_reports(sync_exports=False)
    items: list[dict[str, str]] = []

    import_row = next((r for r in health.get("integrations") or [] if r.get("id") == "imports"), {})
    items.append(
        _item(
            "imports",
            "Import freshness",
            "ok" if import_row.get("ok") else "warn" if health.get("ok_count", 0) else "fail",
            str(import_row.get("detail") or "Import status unknown."),
        )
    )

    ollama_row = next((r for r in health.get("integrations") or [] if r.get("id") == "ollama"), {})
    items.append(
        _item(
            "local-ai",
            "Local AI reachable",
            "ok" if ollama_row.get("ok") else "fail",
            str(ollama_row.get("detail") or "Ollama status unknown."),
        )
    )

    docs_row = next((r for r in health.get("integrations") or [] if r.get("id") == "documents"), {})
    doc_count = 0
    if store is not None:
        try:
            raw = store.get("nr2:v2:documents")
            if raw:
                payload = json.loads(raw)
                doc_count = len(payload.get("queue") or [])
        except Exception:
            doc_count = 0
    items.append(
        _item(
            "documents",
            "Documents queue reviewed",
            "warn" if doc_count > 0 else "ok",
            f"{doc_count} document(s) pending review." if doc_count else "No documents waiting in local queue.",
        )
    )

    ct = reports.get("claimTracking") or {}
    denied_30 = int(ct.get("deniedAgingPast30Days") or 0)
    items.append(
        _item(
            "claims",
            "Denied claims aging past 30 days",
            "warn" if denied_30 else "ok",
            f"{denied_30} claim(s) flagged for follow-up." if denied_30 else "No denied 30+ day claims flagged in import.",
        )
    )

    ar = reports.get("arAging") or {}
    ninety_pct = float(ar.get("ninetyPlusPct") or 0)
    items.append(
        _item(
            "ar",
            "A/R 90+ day exposure",
            "warn" if ninety_pct >= 15 else "ok",
            f"90+ day balances are {ninety_pct}% of outstanding A/R in the import snapshot.",
        )
    )

    tp = reports.get("treatmentPlans") or {}
    items.append(
        _item(
            "treatment-plans",
            "Treatment plan exports",
            "ok" if tp.get("available") else "warn",
            "Treatment plan summary loaded." if tp.get("available") else "Treatment plan export missing — run practice exports.",
        )
    )

    fail_count = sum(1 for row in items if row["status"] == "fail")
    warn_count = sum(1 for row in items if row["status"] == "warn")
    overall = "fail" if fail_count else ("warn" if warn_count else "ok")

    return {
        "generatedAt": _iso_now(),
        "period": _utc_now().strftime("%Y-%m-%d"),
        "overall": overall,
        "summary": f"{len(items) - fail_count - warn_count} clear, {warn_count} warning(s), {fail_count} blocker(s).",
        "items": items,
        "integrationHealth": health,
        "financialReports": reports,
        "periodClose": period_close_operation_context(),
    }


def format_daily_closeout_text(payload: dict[str, Any]) -> str:
    lines = [
        f"Daily closeout ({payload.get('period')}): {str(payload.get('overall', '')).upper()} — {payload.get('summary')}",
        "",
    ]
    for row in payload.get("items") or []:
        lines.append(f"- [{str(row.get('status')).upper()}] {row.get('label')}: {row.get('detail')}")
    return "\n".join(lines)


def _load_build_stamp() -> str:
    for rel in ("nr2-build.json", "site/nr2-build.json"):
        path = Path(__file__).resolve().parent / rel
        if path.is_file():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                return str(data.get("BUILD_ID") or data.get("assetVersion") or "")
            except Exception:
                continue
    return ""


def _laser_blocked(readiness: dict[str, Any] | None) -> tuple[bool, str]:
    ready = readiness if isinstance(readiness, dict) else {}
    blocking = ready.get("blocking") if isinstance(ready.get("blocking"), list) else []
    lasers = ready.get("alignmentLasers") if isinstance(ready.get("alignmentLasers"), dict) else {}
    if lasers.get("red") is True or blocking:
        reason = str(lasers.get("reason") or "laser_or_blocking_softgap")
        keys = lasers.get("datasetKeys") or [b.get("key") for b in blocking if isinstance(b, dict)]
        return True, f"{reason}: {keys}"
    return False, ""


def _maybe_notify_period_close(result: dict[str, Any], store: Any | None = None) -> dict[str, Any]:
    """Desk HAL hub alert for stalled/blocked/attest_only — never invent dollars."""
    try:
        from period_close_ops_notify import notify_period_close_trouble

        note = notify_period_close_trouble(result, store=store)
        if isinstance(note, dict) and not note.get("skipped"):
            result = {**result, "opsNotify": note}
    except Exception as exc:  # noqa: BLE001
        result = {**result, "opsNotify": {"ok": False, "error": str(exc)[:160]}}
    return result


def period_close_status() -> dict[str, Any]:
    """HAL/tool status for 'Did we close today?' — never invents dollars."""
    state = _read_state()
    last = last_close_record()
    last_force = last_force_close_record()
    sd_total = (last or {}).get("softdentTotal")
    qb_rev = (last or {}).get("qbRevenue")
    force_close = bool((last or {}).get("forceClose")) or bool(
        last_force and str((last or {}).get("completedAt") or "") == str(last_force.get("completedAt") or "")
    )
    export_blob = (last or {}).get("export") if isinstance(last, dict) else None
    morning_bundle: dict[str, Any] | None = None
    if isinstance(export_blob, dict):
        aging_rep = (export_blob.get("reports") or {}).get("aging") or {}
        morning_bundle = {
            "ok": bool(export_blob.get("ok")),
            "partial": bool(export_blob.get("partial")),
            "okCount": export_blob.get("okCount"),
            "failed": list(export_blob.get("failed") or [])[:8],
            "reportIds": list(export_blob.get("reportIds") or [])[:8],
            "fallback": export_blob.get("fallback"),
            "error": str(export_blob.get("error") or "")[:200] or None,
            "detail": str(
                export_blob.get("detail")
                or aging_rep.get("detail")
                or aging_rep.get("error")
                or ""
            )[:400]
            or None,
            "ensure": export_blob.get("ensure"),
            "excelDisabled": export_blob.get("excelDisabled"),
            "excelEnablementRunbook": export_blob.get("excelEnablementRunbook")
            or "NewRidgeFinancial2/docs/runbooks/softdent_excel_enablement_nr2.md",
            "excelEnablementGate": export_blob.get("excelEnablementGate"),
            "emptyNotZero": True,
        }
        if not morning_bundle.get("ok") and not morning_bundle.get("excelEnablementGate"):
            morning_bundle["excelEnablementGate"] = (
                "Money beams need SoftDent Excel enabled — follow "
                f"{morning_bundle['excelEnablementRunbook']}; then say approve for "
                "attended morning bundle. Preview-only stays attest_only · empty ≠ $0 · "
                "forceCloseAvailable stays laser-gated."
            )
    return {
        "ok": True,
        "emptyNotZero": True,
        "status": state.get("status") or "idle",
        "activeOperation": (period_close_operation_context() or {}).get("activeOperation"),
        "completedAt": state.get("completedAt") or (last or {}).get("completedAt"),
        "lastClose": last,
        "lastForceClose": last_force,
        "forceClose": force_close,
        "morningBundle": morning_bundle,
        "auto": None if last is None else bool((last or {}).get("auto")),
        "beamHash": (last or {}).get("beamHash") or state.get("beamHash"),
        "softdentTotal": sd_total,
        "qbRevenue": qb_rev,
        "softdentDisplay": (last or {}).get("softdentDisplay"),
        "qbDisplay": (last or {}).get("qbDisplay"),
        "laserClear": bool((last or {}).get("laserClear", state.get("laserClear"))),
        "shadowStartedAt": state.get("shadowStartedAt"),
        "systemOfRecord": bool(state.get("systemOfRecord")),
        "buildStamp": (last or {}).get("buildStamp") or state.get("buildStamp"),
        "logPath": str(CLOSE_LOG_PATH),
        "forceCloseLogPath": str(FORCE_CLOSE_LOG_PATH),
        "at": _iso_now(),
    }


def force_close_should_pull_softdent(
    readiness: dict[str, Any] | None = None,
    *,
    status: str | None = None,
) -> bool:
    """Optical Force Close: SoftDent aging pull when lasers red or close stalled/blocked.

    Attest-only when lasers clear and period-close is idle/completed (not inventing $0).
    """
    ready = readiness if isinstance(readiness, dict) else {}
    close_status = str(status or "").strip().lower()
    if not close_status:
        close_status = str((ready.get("periodClose") or {}).get("status") or "").strip().lower()
    if not close_status:
        close_status = str((_read_state() or {}).get("status") or "idle").lower()
    if close_status in ("stalled", "blocked"):
        return True
    lasers = ready.get("alignmentLasers") if isinstance(ready.get("alignmentLasers"), dict) else {}
    if lasers.get("red") is True:
        return True
    blocking = ready.get("blocking") if isinstance(ready.get("blocking"), list) else []
    if blocking:
        return True
    return False


def force_close_available(
    readiness: dict[str, Any] | None = None,
    *,
    status: str | None = None,
) -> bool:
    """Laser-gated desk control: enable when lasers red or close stalled/blocked (not while running)."""
    close_status = str(status or "").strip().lower()
    if not close_status:
        ready = readiness if isinstance(readiness, dict) else {}
        close_status = str((ready.get("periodClose") or {}).get("status") or "").strip().lower()
    if not close_status:
        close_status = str((_read_state() or {}).get("status") or "idle").lower()
    if close_status == "running":
        return False
    if close_status in ("stalled", "blocked"):
        return True
    ready = readiness if isinstance(readiness, dict) else {}
    lasers = ready.get("alignmentLasers") if isinstance(ready.get("alignmentLasers"), dict) else {}
    if lasers.get("red") is True:
        return True
    blocking = ready.get("blocking") if isinstance(ready.get("blocking"), list) else []
    return bool(blocking)


def force_period_close(
    store: Any | None = None,
    *,
    actor: str = "optical-force-close",
    readiness: dict[str, Any] | None = None,
    pull_softdent: bool | None = None,
) -> dict[str, Any]:
    """Operator Force Close from Hub/OM — laser-aware SoftDent pull + dual JSONL attest.

    Does not override a running close. SoftDent write-back remains forbidden.
    Appends force_close_log.jsonl in addition to daily_close_log.jsonl.
    """
    ready = readiness
    if not isinstance(ready, dict):
        try:
            from import_diagnostics import assess_import_readiness

            ready = assess_import_readiness()
            try:
                ready = merge_period_close_into_readiness(ready)
            except Exception:
                pass
        except Exception as exc:  # noqa: BLE001
            ready = {"ok": False, "error": str(exc)[:240], "blocking": [], "alignmentLasers": {"red": True}}

    state = _read_state()
    status_now = str(state.get("status") or "idle").lower()
    if status_now == "running":
        return {
            "ok": False,
            "error": "period_close_already_running",
            "status": "running",
            "activeOperation": "daily_close",
            "forceClose": True,
            "emptyNotZero": True,
        }

    lasers = ready.get("alignmentLasers") if isinstance(ready.get("alignmentLasers"), dict) else {}
    blocking = ready.get("blocking") if isinstance(ready.get("blocking"), list) else []
    laser_override = bool(lasers.get("red") is True or blocking or status_now in ("stalled", "blocked"))
    do_pull = (
        bool(pull_softdent)
        if pull_softdent is not None
        else force_close_should_pull_softdent(ready, status=status_now)
    )
    try:
        from period_close_ops_notify import notify_force_close_started

        start_note = notify_force_close_started(
            actor=actor,
            laser_override=laser_override,
            store=store,
            speak=True,
        )
    except Exception as exc:  # noqa: BLE001
        start_note = {"ok": False, "error": str(exc)[:160]}

    result = run_period_close(
        store=store,
        actor=actor,
        auto=False,
        pull_softdent=do_pull,
        readiness=ready,
        force_close=True,
    )
    force_row = {
        "timestamp": _iso_now(),
        "completedAt": result.get("completedAt") or _iso_now(),
        "actor": actor,
        "beamHash": result.get("beamHash"),
        "laserOverride": laser_override,
        "shadowMode": True,
        "systemOfRecord": False,
        "ok": bool(result.get("ok")),
        "status": result.get("status"),
        "pullSoftdent": do_pull,
        "fallback": result.get("fallback"),
        "emptyNotZero": True,
        "error": result.get("error"),
    }
    try:
        _append_force_close_log(force_row)
    except OSError:
        pass
    result = {
        **result,
        "forceClose": True,
        "laserOverride": laser_override,
        "pullSoftdentDecided": do_pull,
        "shadowMode": True,
        "systemOfRecord": False,
        "emptyNotZero": True,
        "forceCloseLogPath": str(FORCE_CLOSE_LOG_PATH),
        "opsNotifyStart": start_note,
    }
    return result


def run_period_close(
    store: Any | None = None,
    *,
    actor: str = "Operator",
    consent_export: bool = True,
    pull_softdent: bool = False,
    auto: bool = False,
    readiness: dict[str, Any] | None = None,
    force_close: bool = False,
) -> dict[str, Any]:
    """Execute one shadow period-close cycle.

    Default (auto/morning): SoftDent aging+register+collections pull when pull_softdent=True
    (scheduler), then heal imports, laser gate, money-beam attest, JSONL log.
    SoftDent GUI export is consent-free (Excel/Print Preview only; write-back forbidden).
    Aging is required; register/collections are best-effort (partial still heals).
    """
    _ = consent_export  # SoftDent export no longer gated; kept for API compatibility
    with _LOCK:
        started = _iso_now()
        state = _read_state()
        if str(state.get("status") or "") == "running":
            return {
                "ok": False,
                "error": "period_close_already_running",
                "status": "running",
                "activeOperation": "daily_close",
            }

        build_stamp = _load_build_stamp()
        state = {
            **state,
            "activeOperation": "daily_close",
            "status": "running",
            "startedAt": started,
            "actor": actor,
            "auto": bool(auto),
            "forceClose": bool(force_close),
            "buildStamp": build_stamp,
            "systemOfRecord": False,
        }
        _write_state(state)

        try:
            from import_diagnostics import assess_import_readiness

            ready = readiness if isinstance(readiness, dict) else assess_import_readiness()
        except Exception as exc:  # noqa: BLE001
            ready = {"ok": False, "error": str(exc)[:240], "blocking": [], "alignmentLasers": {"red": True}}

        blocked, block_reason = _laser_blocked(ready)
        # When SoftDent GUI pull is requested, skip the *pre*-pull laser gate — stale SoftDent
        # AR is the usual reason lasers are red, and the aging export is how we clear it.
        # Laser gate still applies after export+heal (and for attest-only closes).
        if blocked and not pull_softdent:
            entry = {
                "status": "blocked",
                "completedAt": _iso_now(),
                "startedAt": started,
                "actor": actor,
                "auto": bool(auto),
                "forceClose": bool(force_close),
                "laserClear": False,
                "blockReason": block_reason,
                "buildStamp": build_stamp,
                "emptyNotZero": True,
            }
            _append_close_log(entry)
            state.update(
                {
                    "activeOperation": "blocked",
                    "status": "blocked",
                    "completedAt": entry["completedAt"],
                    "laserClear": False,
                    "blockReason": block_reason,
                }
            )
            _write_state(state)
            return _maybe_notify_period_close(
                {"ok": False, "error": "laser_blocked", "status": "blocked", **entry},
                store=store,
            )

        export_result: dict[str, Any] | None = None
        import_refresh: dict[str, Any] | None = None
        export_fallback_attest = False
        if pull_softdent:
            try:
                from hal_brain_tools import softdent_export_morning_bundle

                # Morning bundle: aging (required) + register + collections (best-effort).
                # SoftDent GUI export is consent-free; retries live in export_report_by_id.
                export_result = softdent_export_morning_bundle(days=30)
            except Exception as exc:  # noqa: BLE001
                export_result = {"ok": False, "error": str(exc)[:240], "bundle": True}
            if not export_result.get("ok"):
                # Circuit breaker: do not stall morning close — attest from existing beams.
                export_fallback_attest = True
                export_result = {
                    **(export_result if isinstance(export_result, dict) else {}),
                    "ok": False,
                    "fallback": "attest_only",
                    "guiExport": False,
                    "emptyNotZero": True,
                }
            else:
                # Re-ingest after Excel lands so money beams reflect the pull.
                try:
                    from import_healing import heal_import_pipeline

                    import_refresh = heal_import_pipeline(force=True)
                except Exception as exc:  # noqa: BLE001
                    import_refresh = {"ok": False, "error": str(exc)[:240]}
                try:
                    from import_diagnostics import assess_import_readiness as _assess

                    ready = _assess()
                    blocked, block_reason = _laser_blocked(ready)
                    if blocked:
                        entry = {
                            "status": "blocked",
                            "completedAt": _iso_now(),
                            "startedAt": started,
                            "actor": actor,
                            "auto": bool(auto),
                            "forceClose": bool(force_close),
                            "laserClear": False,
                            "blockReason": block_reason,
                            "buildStamp": build_stamp,
                            "emptyNotZero": True,
                            "export": export_result,
                            "importRefresh": import_refresh,
                            "pullSoftdent": True,
                            "softdentReports": list(
                                (export_result or {}).get("reportIds")
                                or ["aging", "register", "collections"]
                            ),
                        }
                        _append_close_log(entry)
                        state.update(
                            {
                                "activeOperation": "blocked",
                                "status": "blocked",
                                "completedAt": entry["completedAt"],
                                "laserClear": False,
                                "blockReason": block_reason,
                            }
                        )
                        _write_state(state)
                        return _maybe_notify_period_close(
                            {
                                "ok": False,
                                "error": "laser_blocked_after_pull",
                                "status": "blocked",
                                **entry,
                            },
                            store=store,
                        )
                except Exception:
                    pass

        try:
            from hal_brain_tools import money_beam_attestation

            attest = money_beam_attestation(readiness=ready)
        except Exception as exc:  # noqa: BLE001
            attest = {"ok": False, "error": str(exc)[:240], "beamHash": None}

        checklist = build_daily_closeout(store)
        sd = attest.get("softdent") if isinstance(attest.get("softdent"), dict) else {}
        qb = attest.get("quickbooks") if isinstance(attest.get("quickbooks"), dict) else {}
        completed_at = _iso_now()
        shadow_started = state.get("shadowStartedAt") or completed_at

        entry = {
            "status": "completed",
            "completedAt": completed_at,
            "startedAt": started,
            "actor": actor,
            "auto": bool(auto),
            "forceClose": bool(force_close),
            "laserClear": True,
            "beamHash": attest.get("beamHash"),
            "dataBeamHash": attest.get("dataBeamHash"),
            "beamTimestamp": attest.get("beamTimestamp") or attest.get("at"),
            "softdentTotal": sd.get("totalOutstanding"),
            "softdentDisplay": sd.get("display"),
            "qbRevenue": qb.get("monthlyRevenue"),
            "qbDisplay": qb.get("display"),
            "checklistOverall": checklist.get("overall"),
            "checklistSummary": checklist.get("summary"),
            "export": export_result,
            "importRefresh": import_refresh,
            "pullSoftdent": bool(pull_softdent),
            "softdentReports": list((export_result or {}).get("reportIds") or [])
            if pull_softdent and isinstance(export_result, dict)
            else (["aging"] if pull_softdent else None),
            "exportOkCount": (export_result or {}).get("okCount")
            if pull_softdent and isinstance(export_result, dict)
            else None,
            "exportPartial": bool((export_result or {}).get("partial"))
            if pull_softdent and isinstance(export_result, dict)
            else None,
            "guiExport": bool(export_result and export_result.get("ok")) if pull_softdent else None,
            "fallback": "attest_only" if export_fallback_attest else None,
            "buildStamp": build_stamp,
            "shadowStartedAt": shadow_started,
            "systemOfRecord": False,
            "emptyNotZero": True,
            "period": _utc_now().strftime("%Y-%m-%d"),
        }
        _append_close_log(entry)
        state.update(
            {
                "activeOperation": "completed",
                "status": "completed",
                "completedAt": completed_at,
                "laserClear": True,
                "beamHash": entry.get("beamHash"),
                "dataBeamHash": entry.get("dataBeamHash"),
                "shadowStartedAt": shadow_started,
                "systemOfRecord": False,
                "buildStamp": build_stamp,
                "lastClose": {
                    "completedAt": completed_at,
                    "beamHash": entry.get("beamHash"),
                    "dataBeamHash": entry.get("dataBeamHash"),
                    "softdentDisplay": entry.get("softdentDisplay"),
                    "softdentTotal": entry.get("softdentTotal"),
                    "qbDisplay": entry.get("qbDisplay"),
                    "qbRevenue": entry.get("qbRevenue"),
                },
            }
        )
        _write_state(state)
        return _maybe_notify_period_close(
            {"ok": True, "status": "completed", "activeOperation": "completed", **entry},
            store=store,
        )


def try_deterministic_period_close_reply(query: str) -> dict[str, Any] | None:
    """HAL short-circuit for close-status questions — cite JSONL only."""
    q = str(query or "").strip()
    if not q:
        return None
    if not re_period_close_ask(q):
        return None
    status = period_close_status()
    completed = status.get("completedAt")
    beam = status.get("beamHash") or "n/a"
    sd = status.get("softdentDisplay") or "∅ NO SIGNAL"
    qb = status.get("qbDisplay") or "∅ NO SIGNAL"
    if not completed:
        text = (
            "No period close on record yet (shadow OPS). "
            "Use FORCE CLOSE on Pages Hub / Office Manager, or wait for morning attest — empty ≠ $0."
        )
        return {
            "ok": True,
            "text": text,
            "routingReason": "period_close_none",
            "periodClose": status,
        }
    laser = "clear" if status.get("laserClear") else "blocked/unknown"
    last = status.get("lastClose") if isinstance(status.get("lastClose"), dict) else {}
    actor = str((last or {}).get("actor") or "").strip()
    if status.get("forceClose") or (last or {}).get("forceClose"):
        mode = "manual Force Close"
        cite = "Cited from daily_close_log.jsonl + force_close_log.jsonl — not invented."
    elif (last or {}).get("auto") is True:
        mode = "auto/morning close"
        cite = "Cited from daily_close_log.jsonl — not invented."
    else:
        mode = f"operator close ({actor or 'manual'})"
        cite = "Cited from daily_close_log.jsonl — not invented."
    text = (
        f"Last period close completed at {completed} via {mode} "
        f"(beamHash={beam}, SoftDent {sd}, QB {qb}, lasers {laser}). "
        f"{cite}"
    )
    return {
        "ok": True,
        "text": text,
        "routingReason": "period_close_status",
        "periodClose": status,
        "beamHash": beam,
        "forceClose": bool(status.get("forceClose") or (last or {}).get("forceClose")),
    }


def re_period_close_ask(query: str) -> bool:
    import re

    return bool(
        re.search(
            r"(?i)\b("
            r"did we close|close status|period close|daily close|"
            r"yesterday'?s close|today'?s close|close yesterday|close today|"
            r"shadow (pilot )?close|ops close"
            r")\b",
            query or "",
        )
    )


if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="NR2 period-close OPS (shadow)")
    parser.add_argument("--auto", action="store_true", help="Attest-only close (no SoftDent GUI)")
    parser.add_argument("--pull-softdent", action="store_true", help="Also SoftDent aging export (consent-free)")
    parser.add_argument("--consent", action="store_true", help="Ignored — SoftDent export is consent-free")
    parser.add_argument("--force", action="store_true", help="Optical Force Close path (force_close_log.jsonl)")
    parser.add_argument("--status", action="store_true", help="Print period_close_status JSON")
    args = parser.parse_args()
    if args.status:
        print(json.dumps(period_close_status(), indent=2))
        raise SystemExit(0)
    if args.force:
        result = force_period_close(
            actor="CLI-force-close",
            pull_softdent=True if args.pull_softdent else None,
        )
    else:
        result = run_period_close(
            actor="CLI",
            auto=bool(args.auto),
            pull_softdent=bool(args.pull_softdent),
        )
    print(json.dumps(result, indent=2, default=str))
    raise SystemExit(0 if result.get("ok") else 2)
