"""Shippable 32B program-fix helpers (2026-07-13).

Honest import-cache / bridge-error / scrub surfaces. Does not invent dollars
or Carestream Gold payment lines.
"""

from __future__ import annotations

import hashlib
import os
import time
from datetime import datetime, timezone
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def import_cache_telemetry(
    *,
    widgets_cache: dict[str, Any],
    fill_progress: dict[str, Any],
    fill_failures: int,
    ttl_sec: float,
    now: float | None = None,
) -> dict[str, Any]:
    """Summarize widget cache residency for operator KPIs (no invented $)."""
    ts = time.monotonic() if now is None else float(now)
    live = 0
    stale = 0
    warming = 0
    fill_failed = False
    last_error = ""
    for key, hit in (widgets_cache or {}).items():
        if not isinstance(hit, dict):
            continue
        if str(key).endswith(":warming"):
            warming += 1
            continue
        age = ts - float(hit.get("at") or 0.0)
        payload = hit.get("payload") if isinstance(hit.get("payload"), dict) else {}
        if payload.get("fillFailed"):
            fill_failed = True
            errs = payload.get("errors") or []
            if errs:
                last_error = str(errs[0])[:160]
        if age < float(ttl_sec):
            live += 1
        else:
            stale += 1
    pages_filling = [
        str(k)
        for k, v in (fill_progress or {}).items()
        if isinstance(v, dict) and 0 < int(v.get("pct") or 0) < 100
    ]
    return {
        "liveKeys": live,
        "staleKeys": stale,
        "warmingKeys": warming,
        "fillFailures": int(fill_failures or 0),
        "fillFailed": bool(fill_failed),
        "lastError": last_error,
        "pagesFilling": pages_filling[:8],
        "ttlSec": float(ttl_sec),
        "at": _utc_now(),
    }


def import_cache_kpi_widget(telemetry: dict[str, Any] | None = None) -> dict[str, Any]:
    t = telemetry if isinstance(telemetry, dict) else {}
    live = int(t.get("liveKeys") or 0)
    stale = int(t.get("staleKeys") or 0)
    warming = int(t.get("warmingKeys") or 0)
    fails = int(t.get("fillFailures") or 0)
    filling = t.get("pagesFilling") or []
    if t.get("fillFailed") or fails > 0:
        status = "warn"
        msg = f"Cache fills failed={fails} · live={live} · stale={stale}"
        hint = str(t.get("lastError") or "Retry Sync — empty ≠ $0.")
    elif warming or filling:
        status = "empty"
        msg = f"Warming {warming} · filling {', '.join(filling) or '…'} · live={live}"
        hint = "Per-page fillProgress; stale served while refill runs."
    else:
        status = "ok"
        msg = f"Live={live} · stale={stale} · TTL {int(t.get('ttlSec') or 15)}s"
        hint = "Import-cache KPIs from widget cache residency (not inventing $)."
    return {
        "id": "import-cache-kpi",
        "type": "status",
        "label": "Import cache KPIs",
        "size": "strip",
        "compact": True,
        "status": status,
        "message": msg[:140],
        "hint": hint[:180],
        "telemetry": t,
    }


def bridge_errors_widget(
    *,
    bundle: dict[str, Any] | None = None,
    fill_failures: int = 0,
    last_sync_error: str | None = None,
) -> dict[str, Any]:
    """Roll up import diagnostics, quarantine, fill failures, sync error."""
    issues: list[str] = []
    b = bundle if isinstance(bundle, dict) else {}
    try:
        from import_diagnostics import blocking_import_issues, evaluate_bundle

        diag = b.get("diagnostics") if isinstance(b.get("diagnostics"), dict) else evaluate_bundle(b, deep=False)
        for item in blocking_import_issues(diag)[:5]:
            label = str(item.get("label") or item.get("id") or item.get("message") or "import gap")
            issues.append(f"import: {label}")
    except Exception as exc:  # noqa: BLE001
        issues.append(f"diagnostics: {exc}")
    try:
        from apex_import_quarantine_pack import quarantine_status

        qs = quarantine_status()
        count = int((qs or {}).get("quarantineCount") or 0)
        if count:
            issues.append(f"quarantine: {count} file(s)")
    except Exception:
        try:
            q = b.get("quarantine") if isinstance(b.get("quarantine"), dict) else {}
            count = int(q.get("count") or len(q.get("items") or []) or 0)
            if count:
                issues.append(f"quarantine: {count}")
        except Exception:
            pass
    if fill_failures:
        issues.append(f"widget fill failures: {fill_failures}")
    if last_sync_error:
        issues.append(f"sync: {last_sync_error[:100]}")
    if not issues:
        return {
            "id": "bridge-errors",
            "type": "status",
            "label": "Bridge errors",
            "size": "strip",
            "compact": True,
            "status": "ok",
            "message": "No blocking bridge errors",
            "hint": "Rollup of import diagnostics, quarantine, fillFailed, last Sync error.",
            "issues": [],
        }
    return {
        "id": "bridge-errors",
        "type": "status",
        "label": "Bridge errors",
        "size": "strip",
        "compact": True,
        "status": "warn",
        "message": " · ".join(issues)[:140],
        "hint": "Honest empty ≠ $0. Fix imports / Sync; do not invent amounts.",
        "alert": True,
        "alertReason": " · ".join(issues)[:200],
        "issues": issues,
    }


VOID_CODE_MARKERS = frozenset(
    {
        "void",
        "voided",
        "void transaction",
        "reversed",
        "adjustment void",
        "nsf void",
    }
)


def row_fingerprint(row: dict[str, Any]) -> str:
    prefer = {
        "date",
        "txn",
        "transaction",
        "id",
        "code",
        "amount",
        "patient",
        "patientname",
        "claimid",
        "account",
    }
    parts: list[str] = []
    for orig_key, value in row.items():
        k = str(orig_key).lower()
        if k in prefer or any(x in k for x in ("date", "amount", "code", "id", "name", "claim", "txn")):
            parts.append(f"{k}={value}")
    parts.sort()
    if not parts:
        parts = [f"{str(k).lower()}={v}" for k, v in list(row.items())[:12]]
        parts.sort()
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode("utf-8", errors="ignore")).hexdigest()[:24]


def is_void_ledger_row(row: dict[str, Any]) -> bool:
    blob = " ".join(str(v or "") for v in row.values()).lower()
    if any(m in blob for m in VOID_CODE_MARKERS):
        return True
    code = str(row.get("Code") or row.get("code") or row.get("TxCode") or "").strip().lower()
    desc = str(row.get("Description") or row.get("description") or row.get("Type") or "").strip().lower()
    return code in {"void", "vd"} or desc in VOID_CODE_MARKERS


def scrub_import_rows(rows: list[dict[str, Any]] | None) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Drop void-marker rows and exact duplicate fingerprints. Returns (kept, summary)."""
    src = list(rows or [])
    summary = {"input": len(src), "voidDropped": 0, "dupDropped": 0, "kept": 0}
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for row in src:
        if not isinstance(row, dict):
            continue
        if is_void_ledger_row(row):
            summary["voidDropped"] += 1
            continue
        fp = row_fingerprint(row)
        if fp in seen:
            summary["dupDropped"] += 1
            continue
        seen.add(fp)
        out.append(row)
    summary["kept"] = len(out)
    return out, summary


def record_program_mutation(
    kind: str,
    *,
    actor: str = "Staff",
    detail: dict[str, Any] | None = None,
    path: str | None = None,
    hal_involved: bool = False,
) -> None:
    """Unify consent/sync/override mutations into HMAC audit + financial lane when needed."""
    action = str(kind or "unknown").strip() or "unknown"
    try:
        from nr2_audit_log import FINANCIAL_MUTATION_ACTIONS, append_audit_event, append_financial_mutation

        body = dict(detail or {})
        body["kind"] = action
        append_audit_event(action, actor=actor, detail=body, path=path)
        financial_kinds = FINANCIAL_MUTATION_ACTIONS | {
            "financial_override",
            "consent_action",
            "sync",
            "claim_action",
            "hal_outbound_consent",
        }
        if action in financial_kinds or body.get("financial"):
            append_financial_mutation(
                action,
                actor=actor,
                detail=body,
                path=path,
                hal_involved=hal_involved,
            )
    except Exception:
        pass


def gold_csv_ops_staff_reply() -> str:
    """Honest Carestream waiting message — no invented lines."""
    pack = r"C:\SoftDentFinancialExports\CARESTREAM_GOLD_CSV_TICKET_PACK_2026-07-13"
    portal = "https://www.carestreamdental.com/en-us/portal/portal-home/"
    try:
        from softdent_gold_csv_drop_ops import checklist_post_ingest, format_gold_csv_drop_ops_reply

        base = format_gold_csv_drop_ops_reply({"post": checklist_post_ingest()})
    except Exception:
        base = "Gold CSV ingest is wired; SoftDent v19 Excel is missing for Insurance Income reports."
    return (
        f"{base} Staff: submit Carestream ticket (case # pending). Pack: {pack}. "
        f"Portal: {portal}. When CSV arrives, save as insurance_payments_YYYYMMDD.csv under "
        r"C:\SoftDentFinancialExports then Sync — settlement fills; until then gapCode="
        "GOLD_CSV_MISSING and paymentLines=0 (empty ≠ $0)."
    )


def gold_ticket_hint_widget() -> dict[str, Any]:
    return {
        "id": "gold-csv-ticket-ops",
        "type": "status",
        "label": "Carestream Gold CSV ticket",
        "size": "strip",
        "compact": True,
        "status": "empty",
        "message": "Awaiting Carestream case # — pack ready; no line-item file yet",
        "hint": gold_csv_ops_staff_reply()[:220],
    }


def ensure_reconciliation_env() -> None:
    """Default SoftDent×QB recon ON for desktop unless operator set it."""
    if "NR2_RECONCILIATION" not in os.environ:
        os.environ["NR2_RECONCILIATION"] = "1"


def imports_are_fresh(bundle: dict[str, Any] | None) -> bool:
    b = bundle if isinstance(bundle, dict) else {}
    diag = b.get("diagnostics") if isinstance(b.get("diagnostics"), dict) else {}
    summary = diag.get("summary") if isinstance(diag.get("summary"), dict) else {}
    connected = summary.get("connected")
    total = summary.get("total")
    missing = int(summary.get("missing") or 0)
    stale = int(summary.get("stale") or 0)
    return isinstance(connected, int) and isinstance(total, int) and total > 0 and missing == 0 and stale == 0


def reconciliation_surface_widget(bundle: dict[str, Any] | None = None) -> dict[str, Any]:
    """Honest SoftDent×QB recon card — shown when imports fresh or with pending gap."""
    ensure_reconciliation_env()
    try:
        from apex_reconciliation_pack import reconciliation_widget

        w = reconciliation_widget(bundle)
    except Exception as exc:  # noqa: BLE001
        return {
            "id": "reconciliation-status",
            "type": "status",
            "label": "SoftDent × QB Reconciliation",
            "size": "full",
            "status": "empty",
            "message": "Reconciliation unavailable",
            "hint": str(exc)[:160],
        }
    if not isinstance(w, dict):
        w = {}
    w = dict(w)
    w["label"] = "SoftDent × QB Reconciliation"
    if not imports_are_fresh(bundle) and w.get("status") != "warn":
        w["status"] = "empty"
        w["message"] = str(w.get("message") or "Waiting on fresh SoftDent + QB imports")
        hint = str(w.get("hint") or "")
        w["hint"] = (hint + " · Sync until import freshness is OK; empty ≠ $0.").strip(" ·")
    return w
