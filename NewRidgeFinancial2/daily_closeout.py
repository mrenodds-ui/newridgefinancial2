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


def period_close_status() -> dict[str, Any]:
    """HAL/tool status for 'Did we close today?' — never invents dollars."""
    state = _read_state()
    last = last_close_record()
    sd_total = (last or {}).get("softdentTotal")
    qb_rev = (last or {}).get("qbRevenue")
    return {
        "ok": True,
        "emptyNotZero": True,
        "status": state.get("status") or "idle",
        "activeOperation": (period_close_operation_context() or {}).get("activeOperation"),
        "completedAt": state.get("completedAt") or (last or {}).get("completedAt"),
        "lastClose": last,
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
        "at": _iso_now(),
    }


def run_period_close(
    store: Any | None = None,
    *,
    actor: str = "Operator",
    consent_export: bool = True,
    pull_softdent: bool = False,
    auto: bool = False,
    readiness: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute one shadow period-close cycle.

    Default (auto/morning): SoftDent aging pull when pull_softdent=True (scheduler),
    then heal imports, laser gate, money-beam attest, JSONL log.
    SoftDent GUI export is consent-free (Excel/Print Preview only; write-back forbidden).
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
            return {"ok": False, "error": "laser_blocked", "status": "blocked", **entry}

        export_result: dict[str, Any] | None = None
        import_refresh: dict[str, Any] | None = None
        export_fallback_attest = False
        if pull_softdent:
            try:
                from hal_brain_tools import softdent_export

                # SoftDent GUI export is consent-free; retries live in export_report_by_id.
                export_result = softdent_export(report_id="aging", days=30)
            except Exception as exc:  # noqa: BLE001
                export_result = {"ok": False, "error": str(exc)[:240]}
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
                            "laserClear": False,
                            "blockReason": block_reason,
                            "buildStamp": build_stamp,
                            "emptyNotZero": True,
                            "export": export_result,
                            "importRefresh": import_refresh,
                            "pullSoftdent": True,
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
                        return {
                            "ok": False,
                            "error": "laser_blocked_after_pull",
                            "status": "blocked",
                            **entry,
                        }
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
            "laserClear": True,
            "beamHash": attest.get("beamHash"),
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
                "shadowStartedAt": shadow_started,
                "systemOfRecord": False,
                "buildStamp": build_stamp,
                "lastClose": {
                    "completedAt": completed_at,
                    "beamHash": entry.get("beamHash"),
                    "softdentDisplay": entry.get("softdentDisplay"),
                    "qbDisplay": entry.get("qbDisplay"),
                },
            }
        )
        _write_state(state)
        return {"ok": True, "status": "completed", "activeOperation": "completed", **entry}


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
            "Run daily close or wait for the morning attest — empty ≠ $0."
        )
        return {
            "ok": True,
            "text": text,
            "routingReason": "period_close_none",
            "periodClose": status,
        }
    laser = "clear" if status.get("laserClear") else "blocked/unknown"
    text = (
        f"Last period close completed at {completed} "
        f"(beamHash={beam}, SoftDent {sd}, QB {qb}, lasers {laser}). "
        "Cited from daily_close_log.jsonl — not invented."
    )
    return {
        "ok": True,
        "text": text,
        "routingReason": "period_close_status",
        "periodClose": status,
        "beamHash": beam,
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
    parser.add_argument("--status", action="store_true", help="Print period_close_status JSON")
    args = parser.parse_args()
    if args.status:
        print(json.dumps(period_close_status(), indent=2))
        raise SystemExit(0)
    result = run_period_close(
        actor="CLI",
        auto=bool(args.auto),
        pull_softdent=bool(args.pull_softdent),
    )
    print(json.dumps(result, indent=2, default=str))
    raise SystemExit(0 if result.get("ok") else 2)
