"""
Phase U1 — ERA 835 ingestion (Moonshot REAUDIT3 SHOULD).

Parse X12 835 EDI or print-image CSV into payer/procedure aggregates only.
Never store patient names, account numbers, DOB, or SSN in nr2_unified.
Gap: ERA835_PENDING when unreadable/missing. No SoftDent write-back.
Flag: NR2_ERA835 (default ON; set 0/false/off to disable).
"""

from __future__ import annotations

import csv
import io
import json
import os
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

GAP_ERA835_PENDING = "ERA835_PENDING"
FIX_HINT_ERA835 = (
    "Drop an ERA 835 EDI (.835) or remittance CSV into the inbox / Claims ERA ingest, "
    "then Sync. Aggregates only — Apex never write-backs SoftDent. Empty ≠ $0."
)

PHI_SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
PHI_DOB_RE = re.compile(
    r"\b(?:0?[1-9]|1[0-2])[/-](?:0?[1-9]|[12]\d|3[01])[/-](?:19|20)\d{2}\b"
)
ACCOUNT_RE = re.compile(r"\b(?:acct|account|member\s*id)[#:\s]*[A-Z0-9-]{6,}\b", re.I)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def era835_enabled() -> bool:
    raw = str(os.getenv("NR2_ERA835") or "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def _parse_money(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    raw = str(value).replace("$", "").replace(",", "").strip()
    try:
        return float(raw) if raw else None
    except ValueError:
        return None


def _period_from_date(raw: str | None) -> str:
    s = str(raw or "").strip()
    digits = re.sub(r"\D", "", s)
    if len(digits) >= 8:
        return f"{digits[:4]}-{digits[4:6]}"
    if re.fullmatch(r"\d{4}-\d{2}", s):
        return s
    return datetime.now(timezone.utc).strftime("%Y-%m")


def _sanitize_payer(name: str) -> str:
    """Strip accidental PHI tokens from payer label; keep carrier name only."""
    text = str(name or "").strip()
    text = PHI_SSN_RE.sub("[REDACTED]", text)
    text = PHI_DOB_RE.sub("[REDACTED]", text)
    text = ACCOUNT_RE.sub("[REDACTED]", text)
    # Drop QC-style person name patterns (Last, First)
    if re.match(r"^[A-Za-z' -]+,\s*[A-Za-z' -]+$", text) and len(text) < 60:
        return "UNKNOWN_PAYER"
    return (text or "UNKNOWN_PAYER")[:120]


def _split_x12(raw: str) -> list[str]:
    text = str(raw or "")
    if "~" in text:
        return [p.strip() for p in text.split("~") if p.strip()]
    return [p.strip() for p in re.split(r"[\n\r]+", text) if p.strip()]


def _parse_x12_835(raw: str) -> dict[str, Any]:
    """
    Aggregate-only X12 835 parse.
    Keeps: payer (N1*PR), check date (BPR/DTM), CLP paid totals, CAS codes, SVC proc codes.
    Discards: NM1*QC patient names, claim account numbers beyond count.
    """
    parts = _split_x12(raw)
    if not any(p.startswith("ISA") or p.startswith("ST*835") or p.startswith("CLP*") for p in parts):
        return {"ok": False, "pending": True, "format": "X12", "gap": GAP_ERA835_PENDING}

    payer = "UNKNOWN_PAYER"
    check_date = ""
    claim_count = 0
    total_paid = 0.0
    adj: dict[str, int] = defaultdict(int)
    # key: (payer, period, proc) -> paid/count
    by_proc: dict[tuple[str, str, str | None], dict[str, float]] = defaultdict(
        lambda: {"paid": 0.0, "claims": 0.0}
    )
    current_proc: str | None = None
    current_paid = 0.0

    for part in parts:
        fields = part.split("*")
        tag = fields[0] if fields else ""
        if tag == "N1" and len(fields) > 2 and fields[1] == "PR":
            payer = _sanitize_payer(fields[2] if len(fields) > 2 else "")
        elif tag == "BPR" and len(fields) > 2:
            for f in reversed(fields):
                if re.fullmatch(r"\d{8}", str(f or "")):
                    check_date = str(f)
                    break
        elif tag == "DTM" and len(fields) > 2 and fields[1] in {"405", "472", "050"}:
            if not check_date:
                check_date = fields[2]
        elif tag == "CLP":
            claim_count += 1
            current_proc = None
            current_paid = _parse_money(fields[4] if len(fields) > 4 else None) or 0.0
            total_paid += current_paid
        elif tag == "CAS" and len(fields) > 2:
            # CAS*GROUP*REASON*AMOUNT... → CO-45 style (REC-005 depth)
            group = str(fields[1] or "").strip().upper()
            i = 2
            while i < len(fields):
                reason = str(fields[i] or "").strip()
                if group and reason and (reason.isdigit() or re.fullmatch(r"[A-Z0-9]+", reason)):
                    code = f"{group}-{reason}"
                    adj[str(code)[:16]] += 1
                i += 2
        elif tag == "SVC" and len(fields) > 1:
            # SVC*AD:D1110*charge*paid  or HC:D1110
            proc_raw = fields[1]
            m = re.search(r"([A-Z]?\d{4,5})", proc_raw)
            current_proc = (m.group(1) if m else proc_raw.replace("AD:", "").replace("HC:", ""))[:12]
            svc_paid = _parse_money(fields[3] if len(fields) > 3 else None)
            if svc_paid is None:
                svc_paid = current_paid
            period = _period_from_date(check_date)
            key = (payer, period, current_proc)
            by_proc[key]["paid"] += float(svc_paid or 0)
            by_proc[key]["claims"] += 1.0
        elif tag == "NM1" and len(fields) > 1 and fields[1] == "QC":
            # Explicitly ignore patient name segments
            continue

    period = _period_from_date(check_date)
    if claim_count == 0 and total_paid <= 0 and not by_proc:
        return {
            "ok": False,
            "pending": True,
            "format": "X12",
            "gap": GAP_ERA835_PENDING,
            "fixHint": FIX_HINT_ERA835,
        }

    # If no SVC rows, store payer-level rollup
    rows: list[dict[str, Any]] = []
    if by_proc:
        for (p_name, p_period, proc), vals in by_proc.items():
            rows.append(
                {
                    "period": p_period,
                    "payer_name": p_name,
                    "procedure_code": proc,
                    "total_paid": vals["paid"] if vals["paid"] else None,
                    "claim_count": int(vals["claims"]),
                    "adjustment_reasons": dict(adj),
                }
            )
    else:
        rows.append(
            {
                "period": period,
                "payer_name": payer,
                "procedure_code": None,
                "total_paid": total_paid if total_paid else None,
                "claim_count": claim_count,
                "adjustment_reasons": dict(adj),
            }
        )

    return {
        "ok": True,
        "pending": False,
        "format": "X12",
        "period": period,
        "payer_name": payer,
        "total_paid": total_paid if total_paid else None,
        "claim_count": claim_count,
        "adjustment_reasons": dict(adj),
        "rows": rows,
        "phiNote": "Patient NM1*QC discarded; aggregates only.",
    }


def _parse_csv_835(raw: str) -> dict[str, Any]:
    """Print-image / remittance CSV → payer/proc aggregates. Drops name/account columns."""
    text = str(raw or "").strip()
    if not text:
        return {"ok": False, "pending": True, "format": "CSV", "gap": GAP_ERA835_PENDING}

    # Skip PHI-looking header columns by name
    skip_cols = {
        "patient",
        "patientname",
        "patient_name",
        "member",
        "membername",
        "dob",
        "ssn",
        "account",
        "accountnumber",
        "acct",
        "subscriber",
    }
    try:
        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames:
            return {"ok": False, "pending": True, "format": "CSV", "gap": GAP_ERA835_PENDING}
    except Exception:
        return {"ok": False, "pending": True, "format": "CSV", "gap": GAP_ERA835_PENDING}

    buckets: dict[tuple[str, str, str | None], dict[str, Any]] = {}
    adj: dict[str, int] = defaultdict(int)
    total_paid = 0.0
    claim_count = 0

    for row in reader:
        if not isinstance(row, dict):
            continue
        norm = {str(k or "").strip().lower().replace(" ", ""): v for k, v in row.items()}
        # Refuse to keep PHI column values
        for sk in skip_cols:
            if sk in norm:
                norm[sk] = None
        payer = _sanitize_payer(
            str(
                norm.get("payer")
                or norm.get("payername")
                or norm.get("carrier")
                or norm.get("insurance")
                or "UNKNOWN_PAYER"
            )
        )
        period = _period_from_date(
            str(norm.get("checkdate") or norm.get("period") or norm.get("date") or norm.get("paymentdate") or "")
        )
        paid = _parse_money(
            norm.get("paid")
            or norm.get("payment")
            or norm.get("amount")
            or norm.get("paidamount")
            or norm.get("totalpaid")
        )
        proc = str(norm.get("proccode") or norm.get("procedure") or norm.get("cdt") or norm.get("code") or "").strip()
        proc = proc[:12] if proc else None
        adj_code = str(norm.get("adjcode") or norm.get("adjustment") or norm.get("cas") or "").strip()
        if adj_code:
            adj[adj_code[:16]] += 1
        if paid is None and not proc and payer == "UNKNOWN_PAYER":
            continue
        claim_count += 1
        if paid is not None:
            total_paid += paid
        key = (payer, period, proc)
        slot = buckets.setdefault(
            key,
            {
                "period": period,
                "payer_name": payer,
                "procedure_code": proc,
                "total_paid": 0.0,
                "claim_count": 0,
                "adjustment_reasons": {},
            },
        )
        slot["claim_count"] += 1
        if paid is not None:
            slot["total_paid"] = float(slot["total_paid"] or 0) + paid

    if not buckets:
        return {
            "ok": False,
            "pending": True,
            "format": "CSV",
            "gap": GAP_ERA835_PENDING,
            "fixHint": FIX_HINT_ERA835,
        }

    rows = []
    for slot in buckets.values():
        reasons = dict(adj)
        slot["adjustment_reasons"] = reasons
        if not slot["total_paid"]:
            slot["total_paid"] = None
        rows.append(slot)

    period = rows[0]["period"] if rows else datetime.now(timezone.utc).strftime("%Y-%m")
    return {
        "ok": True,
        "pending": False,
        "format": "CSV",
        "period": period,
        "payer_name": rows[0]["payer_name"] if rows else "UNKNOWN_PAYER",
        "total_paid": total_paid if total_paid else None,
        "claim_count": claim_count,
        "adjustment_reasons": dict(adj),
        "rows": rows,
        "phiNote": "Patient/account columns discarded; aggregates only.",
    }


def parse_era835_text(content: str) -> dict[str, Any]:
    raw = str(content or "")
    stripped = raw.lstrip()
    if stripped.startswith("ISA") or "*835*" in stripped[:200] or "ST*835" in stripped:
        return _parse_x12_835(raw)
    # Heuristic: CSV header
    first = stripped.splitlines()[0] if stripped else ""
    if "," in first and re.search(r"payer|paid|payment|proc|carrier", first, re.I):
        return _parse_csv_835(raw)
    if stripped.startswith("ISA*") or "~" in raw:
        return _parse_x12_835(raw)
    # Try CSV then X12 fallback
    csv_try = _parse_csv_835(raw)
    if csv_try.get("ok"):
        return csv_try
    return _parse_x12_835(raw)


def parse_era835_file(path: Path | str) -> dict[str, Any]:
    p = Path(path)
    if not p.is_file():
        return {
            "ok": False,
            "pending": True,
            "gap": GAP_ERA835_PENDING,
            "fixHint": FIX_HINT_ERA835,
            "error": f"missing:{p}",
        }
    try:
        raw = p.read_text(encoding="utf-8", errors="ignore")
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "pending": True,
            "gap": GAP_ERA835_PENDING,
            "error": str(exc),
            "fixHint": FIX_HINT_ERA835,
        }
    out = parse_era835_text(raw)
    out["source_file"] = p.name
    return out


def ingest_era835_to_unified(
    path: Path | str | None = None,
    *,
    content: str | None = None,
    filename: str | None = None,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Parse + insert era_835_payments (aggregates) + mirror softdent_era_aggregates."""
    if not era835_enabled():
        return {
            "ok": False,
            "reason": "era835_disabled",
            "hint": "Set NR2_ERA835=1 (default on).",
            "phase": "U1",
            "refreshedAt": _utc_now(),
        }

    if content is not None:
        parsed = parse_era835_text(content)
        parsed["source_file"] = filename or parsed.get("source_file")
    elif path is not None:
        parsed = parse_era835_file(path)
    else:
        return {
            "ok": False,
            "gap": GAP_ERA835_PENDING,
            "fixHint": FIX_HINT_ERA835,
            "phase": "U1",
        }

    if parsed.get("pending") or not parsed.get("ok"):
        return {
            "ok": False,
            "gap": GAP_ERA835_PENDING,
            "fixHint": parsed.get("fixHint") or FIX_HINT_ERA835,
            "phase": "U1",
            "parsed": parsed,
            "refreshedAt": _utc_now(),
        }

    from apex_unified_db_pack import open_unified, unified_db_path

    now = _utc_now()
    src_file = str(parsed.get("source_file") or filename or "")[:200] or None
    rows = parsed.get("rows") if isinstance(parsed.get("rows"), list) else []
    inserted = 0
    with open_unified(path=db_path) as conn:
        for row in rows:
            if not isinstance(row, dict):
                continue
            conn.execute(
                """
                INSERT INTO era_835_payments (
                    period, payer_name, procedure_code, total_paid, claim_count,
                    adjustment_reasons, source_file, source, ingested_at
                ) VALUES (?,?,?,?,?,?,?,?,?)
                """,
                (
                    str(row.get("period") or parsed.get("period") or "")[:32],
                    _sanitize_payer(str(row.get("payer_name") or "")),
                    (str(row.get("procedure_code") or "")[:12] or None),
                    row.get("total_paid"),
                    int(row.get("claim_count") or 0),
                    json.dumps(row.get("adjustment_reasons") or {}),
                    src_file,
                    "era835_u1",
                    now,
                ),
            )
            inserted += 1
        # Mirror period rollup for S1 collections proposal path
        period = str(parsed.get("period") or "")[:32]
        conn.execute(
            """
            INSERT INTO softdent_era_aggregates (
                period, payment_total, claim_count, source_file, source, imported_at
            ) VALUES (?,?,?,?,?,?)
            """,
            (
                period,
                parsed.get("total_paid"),
                int(parsed.get("claim_count") or 0),
                src_file,
                "era835_u1",
                now,
            ),
        )
        conn.commit()

    return {
        "ok": True,
        "phase": "U1",
        "period": parsed.get("period"),
        "payerName": parsed.get("payer_name"),
        "totalPaid": parsed.get("total_paid"),
        "claimCount": parsed.get("claim_count"),
        "rowsInserted": inserted,
        "format": parsed.get("format"),
        "adjustmentReasons": parsed.get("adjustment_reasons"),
        "carcBriefs": _enrich_adjustment_reasons_for_hal(
            parsed.get("adjustment_reasons") if isinstance(parsed.get("adjustment_reasons"), dict) else {}
        ),
        "phiNote": parsed.get("phiNote"),
        "localOnly": True,
        "softDentWriteBack": False,
        "dbPath": str(db_path or unified_db_path()),
        "refreshedAt": now,
    }


def attach_u1_to_era_ingest(
    result: dict[str, Any],
    *,
    content: str,
    filename: str | None = None,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Hook after existing ingest_era_835 — additive U1 payer aggregates."""
    out = dict(result) if isinstance(result, dict) else {"ok": False}
    if not era835_enabled():
        out["era835U1"] = {"ok": False, "reason": "era835_disabled"}
        return out
    try:
        out["era835U1"] = ingest_era835_to_unified(
            content=content,
            filename=filename,
            db_path=db_path,
        )
    except Exception as exc:  # noqa: BLE001
        out["era835U1"] = {"ok": False, "error": str(exc)}
    return out


def _enrich_adjustment_reasons_for_hal(reasons: dict[str, Any] | None) -> dict[str, Any]:
    """Inject whitelist CARC briefs into ERA pack context; absent codes hard-refuse."""
    from era835_parser import enrich_codes_with_briefs

    counts: dict[str, Any] = {}
    if isinstance(reasons, dict):
        counts = {str(k): v for k, v in reasons.items() if k}
    pack = enrich_codes_with_briefs(list(counts.keys()))
    return {
        "counts": counts,
        "briefs": pack.get("briefs") or {},
        "refused": pack.get("refused") or [],
        "refuseNote": pack.get("refuseNote"),
        "knownOnly": True,
        "emptyNotZero": True,
    }


def list_era835_payments(*, limit: int = 24, db_path: Path | None = None) -> list[dict[str, Any]]:
    from apex_unified_db_pack import open_unified

    with open_unified(path=db_path) as conn:
        rows = conn.execute(
            """
            SELECT period, payer_name, procedure_code, total_paid, claim_count,
                   adjustment_reasons, source_file, ingested_at
            FROM era_835_payments
            ORDER BY ingested_at DESC
            LIMIT ?
            """,
            (max(1, min(int(limit), 100)),),
        ).fetchall()
        out = []
        for r in rows:
            reasons = {}
            try:
                reasons = json.loads(r["adjustment_reasons"] or "{}")
            except Exception:
                reasons = {}
            enriched = _enrich_adjustment_reasons_for_hal(reasons if isinstance(reasons, dict) else {})
            out.append(
                {
                    "period": r["period"],
                    "payerName": r["payer_name"],
                    "procedureCode": r["procedure_code"],
                    "totalPaid": r["total_paid"],
                    "claimCount": r["claim_count"],
                    "adjustmentReasons": reasons,
                    "carcBriefs": enriched,
                    "sourceFile": r["source_file"],
                    "ingestedAt": r["ingested_at"],
                }
            )
        return out


def assess_era835_gap(bundle: dict[str, Any] | None = None, *, db_path: Path | None = None) -> dict[str, Any]:
    del bundle
    rows = list_era835_payments(limit=5, db_path=db_path)
    if not rows:
        return {
            "ok": True,
            "gapCode": GAP_ERA835_PENDING,
            "pending": True,
            "fixHint": FIX_HINT_ERA835,
            "honesty": "empty_not_zero",
            "rowCount": 0,
        }
    return {
        "ok": True,
        "gapCode": None,
        "pending": False,
        "rowCount": len(rows),
        "latest": rows[0],
        "honesty": "empty_not_zero",
    }


def era835_widget(bundle: dict[str, Any] | None = None) -> dict[str, Any]:
    gap = assess_era835_gap(bundle)
    if gap.get("pending"):
        return {
            "id": "era835-ingest-gap",
            "type": "status",
            "label": "ERA 835 (U1)",
            "size": "full",
            "status": "empty",
            "message": GAP_ERA835_PENDING,
            "emptyMessage": "No ERA 835 aggregates yet — empty ≠ $0.",
            "hint": FIX_HINT_ERA835,
            "gapCode": GAP_ERA835_PENDING,
        }
    latest = gap.get("latest") or {}
    return {
        "id": "era835-ingest-gap",
        "type": "status",
        "label": "ERA 835 (U1)",
        "size": "full",
        "status": "ok",
        "message": (
            f"{latest.get('period')}: {latest.get('payerName')} "
            f"paid={latest.get('totalPaid')} claims={latest.get('claimCount')}"
        ),
        "hint": "Payer/proc aggregates only — no patient PHI; no SoftDent write-back.",
        "rows": list_era835_payments(limit=5),
    }


def era835_status() -> dict[str, Any]:
    inbox = scan_era_inbox(ensure_dirs=True)
    gap = assess_era835_gap()
    return {
        "ok": True,
        "phase": "U1",
        "buildHint": "hal-10576",
        "enabled": era835_enabled(),
        "flag": "NR2_ERA835",
        "gapCode": gap.get("gapCode") or GAP_ERA835_PENDING,
        "inbox": inbox,
        "chipStatus": inbox.get("chipStatus"),
        "chipLabel": inbox.get("chipLabel"),
        "endpoints": {
            "ingest": "POST /api/apex/hal/era835-ingest",
            "inboxIngest": "POST /api/apex/hal/era-inbox/ingest",
            "status": "GET /api/apex/hal/era835-status",
            "inbox": "GET /api/apex/hal/era-inbox/status",
            "list": "GET /api/apex/hal/era835-payments",
        },
        "note": "Aggregates only (payer/proc/CAS codes). Patient NM1*QC discarded. Empty inbox ≠ $0.",
        "honesty": "empty_not_zero",
        "writeBack": False,
        "refreshedAt": _utc_now(),
    }


_ERA_INBOX_SUFFIXES = {".835", ".edi", ".x12", ".txt", ".csv"}
_ERA_INBOX_NAME_HINTS = ("835", "era", "remit", "eob", "payment")


def era_inbox_candidate_roots() -> list[Path]:
    """Canonical ERA-835 drop-box roots (plus optional NR2_ERA835_INBOX)."""
    candidates = [
        Path(r"C:\SoftDentFinancialExports\era"),
        Path(r"C:\SoftDentReportExports\era"),
    ]
    env_inbox = str(os.environ.get("NR2_ERA835_INBOX") or "").strip()
    if env_inbox:
        candidates.append(Path(env_inbox).expanduser())
    # de-dupe while preserving order
    out: list[Path] = []
    seen: set[str] = set()
    for p in candidates:
        key = str(p).lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out


def ensure_era_inbox_dirs(roots: list[Path] | None = None) -> list[dict[str, Any]]:
    """Create ERA inbox directories when missing (scaffold only — no invented dollars)."""
    created: list[dict[str, Any]] = []
    for root in roots or era_inbox_candidate_roots():
        existed = root.is_dir()
        try:
            root.mkdir(parents=True, exist_ok=True)
            created.append(
                {
                    "path": str(root),
                    "existed": existed,
                    "ok": root.is_dir(),
                }
            )
        except OSError as exc:
            created.append(
                {
                    "path": str(root),
                    "existed": existed,
                    "ok": False,
                    "error": str(exc),
                }
            )
    return created


def _looks_like_era_file(path: Path) -> bool:
    name = path.name.lower()
    suf = path.suffix.lower()
    if suf in _ERA_INBOX_SUFFIXES:
        return True
    return any(h in name for h in _ERA_INBOX_NAME_HINTS)


def scan_era_inbox(
    roots: list[Path] | None = None,
    *,
    ensure_dirs: bool = True,
    limit: int = 50,
) -> dict[str, Any]:
    """List ERA-835 drop-box files without inventing payment dollars.

    Empty inbox → empty=true, honesty=empty_not_zero (never treat as $0).
    """
    candidate_roots = list(roots) if roots is not None else era_inbox_candidate_roots()
    dir_meta: list[dict[str, Any]] = []
    if ensure_dirs:
        dir_meta = ensure_era_inbox_dirs(candidate_roots)

    files: list[dict[str, Any]] = []
    existing_roots: list[str] = []
    for root in candidate_roots:
        if not root.is_dir():
            continue
        existing_roots.append(str(root))
        try:
            children = sorted(root.iterdir(), key=lambda p: p.stat().st_mtime if p.is_file() else 0, reverse=True)
        except OSError:
            continue
        for child in children:
            if not child.is_file():
                continue
            if not _looks_like_era_file(child):
                continue
            try:
                st = child.stat()
                files.append(
                    {
                        "name": child.name,
                        "path": str(child),
                        "sizeBytes": int(st.st_size),
                        "mtime": datetime.fromtimestamp(st.st_mtime, tz=timezone.utc)
                        .replace(microsecond=0)
                        .isoformat()
                        .replace("+00:00", "Z"),
                    }
                )
            except OSError:
                continue
            if len(files) >= max(1, min(int(limit), 200)):
                break
        if len(files) >= max(1, min(int(limit), 200)):
            break

    empty = len(files) == 0
    if empty:
        chip_status = "awaiting"
        chip_label = "Awaiting first 835 drop"
    else:
        chip_status = "ready"
        chip_label = "Ready to ingest"

    return {
        "ok": True,
        "mode": "scaffold",
        "readOnly": True,
        "localOnly": True,
        "writeBack": False,
        "empty": empty,
        "honesty": "empty_not_zero",
        "fileCount": len(files),
        "files": files,
        "readyToIngest": not empty,
        "chipStatus": chip_status,
        "chipLabel": chip_label,
        "candidateRoots": [str(p) for p in candidate_roots],
        "existingRoots": existing_roots,
        "dirs": dir_meta,
        "hint": (
            "Drop ERA 835 EDI/CSV into the ERA inbox. "
            "Empty inbox ≠ $0 insurance; Apex never invents dollars or posts SoftDent."
        ),
        "refreshedAt": _utc_now(),
    }


def era_inbox_status(*, ensure_dirs: bool = True) -> dict[str, Any]:
    """Read-only ERA inbox status for HAL chips / API (hal-10576)."""
    inbox = scan_era_inbox(ensure_dirs=ensure_dirs)
    out: dict[str, Any] = {
        "ok": True,
        "phase": "hal-10576",
        "inbox": inbox,
        "chipStatus": inbox.get("chipStatus"),
        "chipLabel": inbox.get("chipLabel"),
        "empty": inbox.get("empty"),
        "fileCount": inbox.get("fileCount") or 0,
        "honesty": "empty_not_zero",
        "writeBack": False,
        "refreshedAt": _utc_now(),
    }
    try:
        from nr2_browser_security import era_inbox_mutation_contract

        out.update(era_inbox_mutation_contract())
    except Exception:
        out.update(
            {
                "mutationAuthRequired": True,
                "mutationHeader": "X-NR2-Session-Token",
                "mutationAcquireVia": "/api/app-info",
                "ingestUrl": "/api/apex/hal/era-inbox/ingest",
                "ingestMethod": "POST",
                "cliFallback": "scripts/run_era_inbox_ingest_ops.py",
            }
        )
    return out


def ingest_era_inbox(
    roots: list[Path] | None = None,
    *,
    db_path: Path | None = None,
    limit: int = 20,
    ensure_dirs: bool = True,
) -> dict[str, Any]:
    """Scan ERA drop-box and ingest files into unified aggregates (read-only SoftDent).

    Empty inbox → awaiting chip, honesty=empty_not_zero, no invented dollars.
    Never posts SoftDent / never invents Ins Plan > 0 from Register.
    """
    scanned = scan_era_inbox(roots=roots, ensure_dirs=ensure_dirs, limit=limit)
    if scanned.get("empty"):
        return {
            "ok": True,
            "empty": True,
            "honesty": "empty_not_zero",
            "chipStatus": "awaiting",
            "chipLabel": "Awaiting first 835 drop",
            "readyToIngest": False,
            "ingested": [],
            "fileCount": 0,
            "writeBack": False,
            "softDentWriteBack": False,
            "localOnly": True,
            "inbox": scanned,
            "hint": scanned.get("hint"),
            "refreshedAt": _utc_now(),
        }

    ingested: list[dict[str, Any]] = []
    for meta in list(scanned.get("files") or [])[: max(1, min(int(limit), 50))]:
        path = Path(str(meta.get("path") or ""))
        if not path.is_file():
            ingested.append(
                {
                    "name": meta.get("name"),
                    "ok": False,
                    "error": "missing_file",
                    "chipStatus": "processing",
                }
            )
            continue
        result = ingest_era835_to_unified(path=path, db_path=db_path)
        # Legacy attach hook (aggregate proposal only — no SoftDent write-back).
        # Skip when U1 already mirrored softdent_era_aggregates (no matches shape).
        if result.get("ok") and isinstance(result.get("matches"), list):
            try:
                from apex_softdent_era_pack import attach_era_to_ingest

                result = attach_era_to_ingest(result, filename=path.name)
            except Exception as exc:  # noqa: BLE001
                result = dict(result)
                result["attachError"] = f"{type(exc).__name__}:{exc}"
        ingested.append(
            {
                "name": path.name,
                "path": str(path),
                "ok": bool(result.get("ok")),
                "period": result.get("period"),
                "totalPaid": result.get("totalPaid"),
                "claimCount": result.get("claimCount"),
                "rowsInserted": result.get("rowsInserted"),
                "gap": result.get("gap"),
                "softDentWriteBack": False,
                "chipStatus": "ready" if result.get("ok") else "processing",
            }
        )

    any_ok = any(bool(row.get("ok")) for row in ingested)
    return {
        "ok": True,
        "empty": False,
        "honesty": "empty_not_zero",
        "chipStatus": "ready" if any_ok else "processing",
        "chipLabel": (
            "ERA inbox ingested (proposal only)"
            if any_ok
            else "Processing ERA inbox — parse pending"
        ),
        "readyToIngest": True,
        "ingested": ingested,
        "fileCount": len(ingested),
        "writeBack": False,
        "softDentWriteBack": False,
        "localOnly": True,
        "inbox": scanned,
        "hint": (
            "ERA 835 ingested to unified aggregates only — staff post in SoftDent. "
            "Empty ≠ $0; no SoftDent write-back; do not re-export Register hoping Ins Plan > 0."
        ),
        "refreshedAt": _utc_now(),
    }


# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# 10575 — read-only remittance discovery (locate misplaced 835/EDI; never invent $)
# ---------------------------------------------------------------------------

_ERA_DISCOVERY_SKIP_DIR_NAMES = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "node_modules",
        "__pycache__",
        "dashboard_logs",
        "run_logs",
        "_derived_archive",
        "quarantine",
        "fixtures",
        "test",
        "tests",
        "retired_vite_dashboard_2026-07-09",
    }
)
_ERA_DISCOVERY_SNIFF_MARKERS = (
    "ST*835",
    "GS*HP*",
    "ELECTRONIC REMITTANCE",
    "HEALTH CARE CLAIM PAYMENT",
    "835 TRANSACTION",
)
_ERA_DISCOVERY_EXCLUDE_NAMES = frozenset(
    {
        "daysheet.csv",
        "daysheet.xls",
        "daysheet.xlsx",
        "register.csv",
        "register.xls",
        "register.xlsx",
        "collections.csv",
        "collections.xls",
        "operatory_schedule.json",
    }
)
_ERA_DISCOVERY_FALSE_EXTS = frozenset(
    {
        ".json",
        ".tsx",
        ".ts",
        ".jsx",
        ".js",
        ".py",
        ".md",
        ".log",
        ".html",
        ".htm",
        ".css",
        ".map",
        ".lock",
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".webp",
        ".sqlite",
        ".db",
        ".pyc",
        ".xls",
        ".xlsx",
        ".doc",
        ".docx",
        ".pdf",
    }
)


def era_discovery_roots() -> list[Path]:
    """Broad SoftDent/export roots for remittance discovery (read-only)."""
    candidates = [
        Path(r"C:\SoftDentFinancialExports"),
        Path(r"C:\SoftDentReportExports"),
        Path(r"C:\SoftDent"),
        Path(r"C:\SoftDent Data"),
        Path(r"C:\CS SoftDent Software"),
    ]
    env_extra = str(os.environ.get("NR2_ERA_DISCOVERY_ROOTS") or "").strip()
    if env_extra:
        for part in re.split(r"[;|]", env_extra):
            part = part.strip()
            if part:
                candidates.append(Path(part).expanduser())
    out: list[Path] = []
    seen: set[str] = set()
    for p in candidates:
        key = str(p).lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out


def _inbox_root_keys() -> set[str]:
    return {str(p).lower() for p in era_inbox_candidate_roots()}


def _path_under_inbox(path: Path) -> bool:
    try:
        resolved = str(path.resolve()).lower()
    except OSError:
        resolved = str(path).lower()
    for inbox in _inbox_root_keys():
        if resolved == inbox or resolved.startswith(inbox + os.sep) or resolved.startswith(inbox + "/"):
            return True
    return False


def _name_has_era_token(name: str) -> bool:
    """True when remittance tokens appear as path tokens, not UUID/word substrings."""
    return bool(
        re.search(
            r"(?i)(^|[^a-z0-9])(835|era|remit|remittance|eob|x12)([^a-z0-9]|$)",
            name,
        )
    )


def _sniff_era_content(path: Path, *, max_bytes: int = 4096) -> str | None:
    """Return match reason if file head looks like X12 835 / remittance text."""
    try:
        if path.stat().st_size <= 0:
            return None
        raw = path.read_bytes()[: max(256, min(int(max_bytes), 16384))]
    except OSError:
        return None
    try:
        text = raw.decode("utf-8", errors="ignore")
    except Exception:
        text = raw.decode("latin-1", errors="ignore")
    upper = text.upper()
    # Prefer ST*835 / remittance phrases — bare ISA alone is too common in SoftDent CSVs.
    for marker in _ERA_DISCOVERY_SNIFF_MARKERS:
        needle = marker.upper().rstrip("*")
        if needle in upper:
            return f"sniff:{marker}"
    if "ISA" in upper and ("ST*835" in upper or "ST835" in upper.replace("*", "") or "GS*HP" in upper):
        return "sniff:ISA+835"
    return None


def _candidate_match_reason(path: Path) -> str | None:
    name = path.name.lower()
    if "synthetic" in name or name.startswith("sample"):
        return None
    if "fixture" in str(path).lower():
        return None
    if name in _ERA_DISCOVERY_EXCLUDE_NAMES or name.startswith("daysheet") or name.startswith("register_for"):
        return None
    if name.startswith("manifest_"):
        return None
    suf = path.suffix.lower()
    if suf in _ERA_DISCOVERY_FALSE_EXTS:
        return None
    if suf in {".835", ".edi", ".x12"}:
        return f"suffix:{suf}"
    if suf in {".txt", ".csv"}:
        if _name_has_era_token(name):
            sniffed = _sniff_era_content(path)
            return sniffed or f"name+suffix:{suf}"
        sniffed = _sniff_era_content(path)
        if sniffed:
            return sniffed
        return None
    if _name_has_era_token(name):
        sniffed = _sniff_era_content(path)
        if sniffed:
            return sniffed
    return None

def discover_era_candidates(
    roots: list[Path] | None = None,
    *,
    limit: int = 40,
    max_depth: int = 5,
    max_files_visited: int = 8000,
) -> dict[str, Any]:
    """Read-only walk of SoftDent/export roots for misplaced ERA remittances.

    Does not move/copy/create files, invent dollars, or write SoftDent.
    Empty result → procurement still required (honesty=empty_not_zero).
    """
    candidate_roots = list(roots) if roots is not None else era_discovery_roots()
    limit_n = max(1, min(int(limit), 200))
    depth_n = max(1, min(int(max_depth), 8))
    visit_cap = max(100, min(int(max_files_visited), 50000))

    scanned_roots: list[str] = []
    missing_roots: list[str] = []
    candidates: list[dict[str, Any]] = []
    visited = 0
    errors: list[str] = []

    for root in candidate_roots:
        if not root.exists():
            missing_roots.append(str(root))
            continue
        if not root.is_dir():
            missing_roots.append(str(root))
            continue
        scanned_roots.append(str(root))
        root_depth = len(root.parts)
        try:
            for dirpath, dirnames, filenames in os.walk(root):
                # Prune noisy / huge trees
                dirnames[:] = [
                    d
                    for d in dirnames
                    if d.lower() not in _ERA_DISCOVERY_SKIP_DIR_NAMES and not d.startswith(".")
                ]
                try:
                    rel_depth = len(Path(dirpath).parts) - root_depth
                except Exception:
                    rel_depth = 0
                if rel_depth > depth_n:
                    dirnames[:] = []
                    continue
                for fname in filenames:
                    if len(candidates) >= limit_n or visited >= visit_cap:
                        break
                    visited += 1
                    path = Path(dirpath) / fname
                    if not path.is_file():
                        continue
                    reason = _candidate_match_reason(path)
                    if not reason:
                        continue
                    try:
                        st = path.stat()
                        size = int(st.st_size)
                        mtime = (
                            datetime.fromtimestamp(st.st_mtime, tz=timezone.utc)
                            .replace(microsecond=0)
                            .isoformat()
                            .replace("+00:00", "Z")
                        )
                    except OSError as exc:
                        errors.append(f"{path}: {exc}")
                        continue
                    # Skip empty / huge blobs (likely not staff remittances)
                    if size <= 0 or size > 50 * 1024 * 1024:
                        continue
                    candidates.append(
                        {
                            "name": path.name,
                            "path": str(path),
                            "root": str(root),
                            "sizeBytes": size,
                            "mtime": mtime,
                            "matchReason": reason,
                            "inInbox": _path_under_inbox(path),
                        }
                    )
                if len(candidates) >= limit_n or visited >= visit_cap:
                    break
        except OSError as exc:
            errors.append(f"{root}: {exc}")
        if len(candidates) >= limit_n or visited >= visit_cap:
            break

    # Prefer non-inbox finds first (misplaced), then newest
    candidates.sort(
        key=lambda row: (
            1 if row.get("inInbox") else 0,
            str(row.get("mtime") or ""),
        ),
        reverse=True,
    )
    outside = [c for c in candidates if not c.get("inInbox")]
    in_inbox = [c for c in candidates if c.get("inInbox")]
    count = len(candidates)
    if count == 0:
        chip_status = "none_found"
        chip_label = "No local ERA files detected; procurement required"
        hint = (
            "Scanned SoftDent/export roots — no .835/.edi remittance candidates. "
            "Staff must download real payer ERA files into C:\\SoftDentFinancialExports\\era. "
            "Empty ≠ $0; no SoftDent write-back."
        )
    else:
        chip_status = "candidates"
        chip_label = f"Found {count} candidate remittance{'s' if count != 1 else ''}"
        hint = (
            f"Found {count} candidate ERA file(s) "
            f"({len(outside)} outside inbox, {len(in_inbox)} already in inbox). "
            "Verify paths, then copy into C:\\SoftDentFinancialExports\\era and Refresh Inbox. "
            "Discovery is read-only — Apex does not move files or invent dollars."
        )

    return {
        "ok": True,
        "phase": "hal-10576",
        "mode": "discovery",
        "readOnly": True,
        "writeBack": False,
        "softDentWriteBack": False,
        "honesty": "empty_not_zero",
        "empty": count == 0,
        "candidateCount": count,
        "outsideInboxCount": len(outside),
        "inInboxCount": len(in_inbox),
        "candidates": candidates[:limit_n],
        "chipStatus": chip_status,
        "chipLabel": chip_label,
        "scannedRoots": scanned_roots,
        "missingRoots": missing_roots,
        "filesVisited": visited,
        "errors": errors[:12],
        "hint": hint,
        "refreshedAt": _utc_now(),
    }

