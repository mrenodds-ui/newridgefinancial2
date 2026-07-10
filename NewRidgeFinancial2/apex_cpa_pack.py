"""
NR2 Apex CPA pack — scenarios, filing workflow, workpapers, audit, variance.
Never invents financial dollars; planning inputs stay local to NR2 store.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STORE_KEY_SCENARIOS = "nr2:v2:cpa:scenarios"
STORE_KEY_FILING = "nr2:v2:cpa:filing"
STORE_KEY_AUDIT = "nr2:v2:cpa:audit"

FILING_STATES = ("DRAFT", "CPA_REVIEW", "CLIENT_APPROVED", "FILED", "LOCKED")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _store():
    from document_sync import NR2_DATA_DIR
    from local_store import LocalStore

    return LocalStore(NR2_DATA_DIR)


def _load_json(key: str) -> dict[str, Any]:
    try:
        store = _store()
        raw = store.get(key)
        if not raw:
            return {}
        if isinstance(raw, dict):
            return raw
        if isinstance(raw, str):
            return json.loads(raw) if raw.strip() else {}
    except Exception:
        return {}
    return {}


def _save_json(key: str, payload: dict[str, Any]) -> None:
    store = _store()
    store.set(key, json.dumps(payload))


def append_audit(event: str, detail: dict[str, Any] | None = None) -> None:
    data = _load_json(STORE_KEY_AUDIT)
    entries = data.get("entries") if isinstance(data.get("entries"), list) else []
    entries.append(
        {
            "id": str(uuid.uuid4())[:8],
            "at": _utc_now(),
            "event": str(event or ""),
            "detail": detail if isinstance(detail, dict) else {},
        }
    )
    data["entries"] = entries[-200:]
    _save_json(STORE_KEY_AUDIT, data)


def list_audit(limit: int = 40) -> list[dict[str, Any]]:
    data = _load_json(STORE_KEY_AUDIT)
    entries = data.get("entries") if isinstance(data.get("entries"), list) else []
    return list(reversed(entries[-max(1, min(limit, 200)) :]))


def list_scenarios() -> list[dict[str, Any]]:
    data = _load_json(STORE_KEY_SCENARIOS)
    items = data.get("items") if isinstance(data.get("items"), dict) else {}
    out = []
    for sid, row in items.items():
        if not isinstance(row, dict):
            continue
        out.append(
            {
                "id": sid,
                "name": row.get("name") or sid,
                "savedAt": row.get("savedAt"),
                "inputs": row.get("inputs") or {},
                "bookNetIncome": row.get("bookNetIncome"),
                "planningEbitda": row.get("planningEbitda"),
                "locked": bool(row.get("locked")),
            }
        )
    out.sort(key=lambda r: str(r.get("savedAt") or ""), reverse=True)
    return out


def save_scenario(
    *,
    name: str,
    inputs: dict[str, Any],
    book_net_income: float | None = None,
    planning_ebitda: float | None = None,
    scenario_id: str | None = None,
) -> dict[str, Any]:
    data = _load_json(STORE_KEY_SCENARIOS)
    items = data.get("items") if isinstance(data.get("items"), dict) else {}
    sid = scenario_id or str(uuid.uuid4())
    clean_inputs: dict[str, float] = {}
    for k, v in (inputs or {}).items():
        try:
            clean_inputs[str(k)] = float(v)
        except (TypeError, ValueError):
            continue
    row = {
        "name": str(name or "Scenario").strip()[:64] or "Scenario",
        "savedAt": _utc_now(),
        "inputs": clean_inputs,
        "bookNetIncome": book_net_income,
        "planningEbitda": planning_ebitda,
        "locked": False,
    }
    items[sid] = row
    data["items"] = items
    _save_json(STORE_KEY_SCENARIOS, data)
    append_audit("scenario_save", {"id": sid, "name": row["name"], "inputs": clean_inputs})
    return {"ok": True, "id": sid, **row}


def delete_scenario(scenario_id: str) -> dict[str, Any]:
    data = _load_json(STORE_KEY_SCENARIOS)
    items = data.get("items") if isinstance(data.get("items"), dict) else {}
    sid = str(scenario_id or "")
    if sid not in items:
        return {"ok": False, "error": "scenario not found"}
    name = (items[sid] or {}).get("name") if isinstance(items[sid], dict) else sid
    del items[sid]
    data["items"] = items
    _save_json(STORE_KEY_SCENARIOS, data)
    append_audit("scenario_delete", {"id": sid, "name": name})
    return {"ok": True, "id": sid}


def compare_scenarios(ids: list[str]) -> dict[str, Any]:
    data = _load_json(STORE_KEY_SCENARIOS)
    items = data.get("items") if isinstance(data.get("items"), dict) else {}
    cols = []
    for sid in ids[:3]:
        row = items.get(str(sid))
        if isinstance(row, dict):
            cols.append({"id": sid, **row})
    diffs: list[dict[str, Any]] = []
    if len(cols) >= 2:
        keys = set()
        for c in cols:
            keys.update((c.get("inputs") or {}).keys())
        for key in sorted(keys):
            vals = []
            for c in cols:
                try:
                    vals.append(float((c.get("inputs") or {}).get(key) or 0))
                except (TypeError, ValueError):
                    vals.append(0.0)
            spread = max(vals) - min(vals) if vals else 0.0
            diffs.append({"key": key, "values": vals, "spread": spread, "flag": spread >= 1000})
    return {"ok": True, "scenarios": cols, "diffs": diffs}


def get_filing_state() -> dict[str, Any]:
    data = _load_json(STORE_KEY_FILING)
    state = str(data.get("state") or "DRAFT").upper()
    if state not in FILING_STATES:
        state = "DRAFT"
    return {
        "state": state,
        "updatedAt": data.get("updatedAt"),
        "note": data.get("note") or "",
        "filedRelPath": data.get("filedRelPath") or "",
        "history": data.get("history") if isinstance(data.get("history"), list) else [],
        "states": list(FILING_STATES),
        "locked": state in {"FILED", "LOCKED"},
    }


def set_filing_state(*, state: str, note: str = "", filed_rel_path: str = "") -> dict[str, Any]:
    cur = get_filing_state()
    nxt = str(state or "").upper()
    if nxt not in FILING_STATES:
        return {"ok": False, "error": f"invalid state {state}"}
    if cur["state"] == "LOCKED" and nxt != "DRAFT":
        return {"ok": False, "error": "LOCKED — admin reset to DRAFT only"}
    path = str(filed_rel_path or cur.get("filedRelPath") or "").strip()
    if nxt == "FILED":
        if not path:
            return {"ok": False, "error": "FILED requires a tax return PDF in the library (filedRelPath)"}
        # Verify file exists under tax_returns library (avoid circular import with apex_backend)
        try:
            from document_sync import NR2_DATA_DIR

            root = Path(NR2_DATA_DIR) / "document_library" / "tax_returns"
        except Exception:
            root = Path(__file__).resolve().parents[1] / "app_data" / "nr2" / "document_library" / "tax_returns"
        candidate = (root / path).resolve()
        try:
            candidate.relative_to(root.resolve())
        except ValueError:
            return {"ok": False, "error": "filedRelPath escapes tax returns library"}
        if not candidate.is_file():
            return {"ok": False, "error": f"filedRelPath not found in tax returns library: {path}"}
    data = _load_json(STORE_KEY_FILING)
    history = data.get("history") if isinstance(data.get("history"), list) else []
    history.append({"at": _utc_now(), "from": cur["state"], "to": nxt, "note": note})
    data.update(
        {
            "state": nxt,
            "updatedAt": _utc_now(),
            "note": str(note or "")[:240],
            "filedRelPath": path if nxt in {"FILED", "LOCKED", "CLIENT_APPROVED"} else (filed_rel_path or data.get("filedRelPath") or ""),
            "history": history[-50:],
        }
    )
    # Always persist path when provided
    if filed_rel_path:
        data["filedRelPath"] = str(filed_rel_path).strip()
    _save_json(STORE_KEY_FILING, data)
    append_audit("filing_state", {"from": cur["state"], "to": nxt, "note": note, "filedRelPath": data.get("filedRelPath")})
    return {"ok": True, **get_filing_state()}


def build_workpaper_html(
    *,
    plan: dict[str, Any],
    ebitda_walk: dict[str, Any],
    scenario: dict[str, Any] | None = None,
    build_id: str = "",
) -> str:
    """CPA-style workpaper HTML (print/PDF via browser). No invented dollars."""
    bridge = plan.get("bridgeLines") if isinstance(plan.get("bridgeLines"), list) else []
    steps = ebitda_walk.get("steps") if isinstance(ebitda_walk.get("steps"), list) else []
    disclaimer = str(
        plan.get("disclaimer")
        or "PLANNING ONLY — REQUIRES CPA REVIEW BEFORE FILING. Not a filed return."
    )

    def money(v: Any) -> str:
        try:
            return f"${float(v):,.0f}"
        except (TypeError, ValueError):
            return "—"

    bridge_rows = "".join(
        f"<tr><td>{_esc(b.get('line'))}</td><td class='num'>{money(b.get('amount'))}</td>"
        f"<td class='cite'>{_esc(_cite_for_line(str(b.get('line') or '')))}</td></tr>"
        for b in bridge
        if isinstance(b, dict)
    )
    ebitda_rows = "".join(
        f"<tr><td>{_esc(s.get('label'))}</td><td class='num'>{money(s.get('value'))}</td>"
        f"<td class='cite'>{_esc(_cite_for_line(str(s.get('label') or '')))}</td></tr>"
        for s in steps
        if isinstance(s, dict)
    )
    sc_block = ""
    if scenario:
        sc_block = (
            f"<h2>Scenario</h2><p>{_esc(scenario.get('name'))} · saved {_esc(scenario.get('savedAt'))}</p>"
            f"<pre>{_esc(json.dumps(scenario.get('inputs') or {}, indent=2))}</pre>"
        )
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>NR2 CPA Workpaper</title>
<style>
body{{font-family:Segoe UI,Arial,sans-serif;margin:24px;color:#111}}
h1{{font-size:18px}} h2{{font-size:14px;margin-top:24px}}
table{{border-collapse:collapse;width:100%;font-size:12px}}
th,td{{border:1px solid #ccc;padding:6px 8px;text-align:left}}
.num{{text-align:right;font-variant-numeric:tabular-nums}}
.cite{{font-size:10px;color:#555}}
.banner{{background:#fff3cd;border:1px solid #ffc107;padding:10px;margin:12px 0}}
.meta{{color:#666;font-size:11px}}
@media print{{.noprint{{display:none}}}}
</style></head><body>
<h1>NewRidge Financial 2.0 — CPA Workpaper</h1>
<p class="meta">Build {_esc(build_id)} · Generated {_esc(_utc_now())} · Entity {_esc(plan.get('entity'))} · {_esc(plan.get('state'))}</p>
<div class="banner"><strong>DISCLAIMER:</strong> {_esc(disclaimer)}</div>
{sc_block}
<h2>Book-to-Tax Bridge (planning)</h2>
<table><thead><tr><th>Line</th><th>Amount</th><th>Citation</th></tr></thead>
<tbody>{bridge_rows or '<tr><td colspan="3">No bridge lines</td></tr>'}</tbody></table>
<h2>EBITDA Reconciliation (book)</h2>
<table><thead><tr><th>Line</th><th>Amount</th><th>Citation</th></tr></thead>
<tbody>{ebitda_rows or '<tr><td colspan="3">No EBITDA steps</td></tr>'}</tbody></table>
<h2>Sign-off</h2>
<p>Prepared by: ______________________ Date: __________</p>
<p>CPA review: ______________________ Date: __________</p>
<p class="noprint"><button onclick="window.print()">Print / Save PDF</button></p>
</body></html>"""


def _esc(value: Any) -> str:
    return (
        str(value if value is not None else "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _cite_for_line(label: str) -> str:
    t = label.lower()
    if "net income" in t or "books" in t:
        return "QB P&L · NetIncome (import)"
    if "depreci" in t or "amort" in t or "§179" in t:
        return "QB expenseCategories · Depreciation/Amort"
    if "interest" in t:
        return "QB expenseCategories · Interest"
    if "meals" in t:
        return "tax_engine planning adj (est.)"
    if "health" in t:
        return "tax_engine planning adj (review)"
    if "k-1" in t or "ordinary" in t:
        return "tax_engine bridge result"
    if "w-2" in t or "officer" in t:
        return "Planning scenario (not payroll import)"
    if "ebitda" in t:
        return "Computed from QB import lines"
    return "Import-backed / planning note"


def cite_key_for_line(label: str) -> str:
    t = str(label or "").lower()
    if "depreci" in t or "amort" in t or "§179" in t:
        return "depreciation"
    if "interest" in t:
        return "interest"
    if "net income" in t or "books" in t:
        return "net_income"
    if "meals" in t:
        return "meals"
    if "health" in t:
        return "health"
    if "w-2" in t or "officer" in t:
        return "officer_w2"
    if "ebitda" in t:
        return "ebitda"
    if "k-1" in t or "ordinary" in t:
        return "ordinary"
    return "other"


def list_qb_citation_rows(bundle: dict[str, Any], cite_key: str) -> dict[str, Any]:
    """QB-backed citation drill-down rows — never invents JE lines."""
    key = str(cite_key or "").strip().lower() or "other"
    qb = bundle.get("quickbooks") if isinstance(bundle.get("quickbooks"), dict) else {}

    def _section_rows(name: str) -> list[dict[str, Any]]:
        sec = qb.get(name) if isinstance(qb.get(name), dict) else {}
        rows = sec.get("rows") if isinstance(sec.get("rows"), list) else None
        if rows is None:
            rows = sec.get("data") if isinstance(sec.get("data"), list) else []
        return [r for r in rows if isinstance(r, dict)]

    def _money(row: dict[str, Any]) -> float | None:
        for k in ("Amount", "amount", "Total", "Balance", "NetIncome", "value"):
            raw = row.get(k)
            if raw is None or raw == "":
                continue
            try:
                return float(str(raw).replace("$", "").replace(",", ""))
            except ValueError:
                continue
        return None

    def _label(row: dict[str, Any]) -> str:
        return str(
            row.get("Category")
            or row.get("Account")
            or row.get("Name")
            or row.get("Memo")
            or row.get("Description")
            or row.get("Payee")
            or row.get("Period")
            or ""
        ).strip()

    cat_rows = _section_rows("expenseCategories")
    exp_rows = _section_rows("expenses")
    pnl_rows = _section_rows("profitAndLoss")

    matched: list[dict[str, Any]] = []
    source = "quickbooks.expenseCategories"
    empty_reason = None

    if key == "depreciation":
        tokens = ("depreci", "amort", "§179", "section 179")
        for row in cat_rows:
            lab = _label(row).lower()
            if any(t in lab for t in tokens):
                amt = _money(row)
                matched.append(
                    {
                        "label": _label(row),
                        "amount": amt,
                        "scope": row.get("Scope") or row.get("Period"),
                        "memo": row.get("Memo") or row.get("Description"),
                    }
                )
        if not matched:
            for row in exp_rows:
                lab = _label(row).lower()
                blob = " ".join(str(row.get(k) or "") for k in ("Memo", "Description", "Category", "Account")).lower()
                if any(t in lab or t in blob for t in tokens):
                    matched.append(
                        {
                            "label": _label(row),
                            "amount": _money(row),
                            "scope": row.get("Period"),
                            "memo": row.get("Memo") or row.get("Description"),
                        }
                    )
            source = "quickbooks.expenses" if matched else source
    elif key == "interest":
        tokens = ("interest", "loan interest", "mortgage interest")
        for row in cat_rows:
            lab = _label(row).lower()
            if any(t in lab for t in tokens):
                matched.append(
                    {
                        "label": _label(row),
                        "amount": _money(row),
                        "scope": row.get("Scope") or row.get("Period"),
                        "memo": row.get("Memo") or row.get("Description"),
                    }
                )
    elif key == "net_income":
        source = "quickbooks.profitAndLoss"
        for row in pnl_rows[-3:]:
            matched.append(
                {
                    "label": f"P&L {row.get('Period') or ''}".strip(),
                    "amount": _money(row) if row.get("NetIncome") is not None else _money({"Amount": row.get("NetIncome")}),
                    "scope": row.get("Period"),
                    "memo": f"Income {row.get('TotalIncome')} · Expense {row.get('TotalExpense')}",
                }
            )
            # Prefer explicit NetIncome
            try:
                matched[-1]["amount"] = float(str(row.get("NetIncome")).replace(",", "")) if row.get("NetIncome") is not None else matched[-1]["amount"]
            except (TypeError, ValueError):
                pass
    elif key in {"meals", "health", "officer_w2", "ordinary", "ebitda"}:
        source = "tax_engine / planning"
        empty_reason = "Planning or computed line — no QB JE drill-down. See workpaper citations."
    else:
        empty_reason = "No QB citation mapping for this line."

    if not matched and empty_reason is None:
        if not cat_rows and not exp_rows and key in {"depreciation", "interest"}:
            empty_reason = "Import has no expenseCategories / expense detail lines — period totals only."
        else:
            empty_reason = "No matching QB category/memo rows for this citation."

    total = 0.0
    any_amt = False
    for row in matched:
        if isinstance(row.get("amount"), (int, float)):
            total += float(row["amount"])
            any_amt = True

    return {
        "ok": True,
        "citeKey": key,
        "citation": _cite_for_line(key if key != "net_income" else "net income"),
        "source": source,
        "rows": matched,
        "total": total if any_amt else None,
        "empty": len(matched) == 0,
        "emptyReason": empty_reason if not matched else None,
        "honesty": "Import-backed rows only — never invents JE detail.",
    }


def detect_import_variances(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    """Period-over-period variance alerts from SoftDent dashboard — no invented $."""
    softdent = bundle.get("softdent") if isinstance(bundle.get("softdent"), dict) else {}
    dash = softdent.get("dashboard") if isinstance(softdent.get("dashboard"), dict) else {}
    rows = dash.get("rows") if isinstance(dash.get("rows"), list) else []
    if len(rows) < 2:
        return []
    alerts: list[dict[str, Any]] = []

    def _money(row: dict, key: str) -> float | None:
        raw = row.get(key)
        if raw is None or raw == "":
            return None
        try:
            return float(str(raw).replace("$", "").replace(",", ""))
        except ValueError:
            return None

    a, b = rows[-2], rows[-1]
    if not isinstance(a, dict) or not isinstance(b, dict):
        return []
    for key, label in (("production", "Production"), ("collections", "Collections")):
        va, vb = _money(a, key), _money(b, key)
        if va is None or vb is None or va == 0:
            continue
        pct = abs(vb - va) / abs(va) * 100.0
        if pct >= 10.0:
            alerts.append(
                {
                    "metric": key,
                    "label": label,
                    "prior": va,
                    "latest": vb,
                    "pct": round(pct, 1),
                    "priorPeriod": str(a.get("period") or a.get("year_month") or ""),
                    "latestPeriod": str(b.get("period") or b.get("year_month") or ""),
                    "message": f"{label} changed {pct:.0f}% ({a.get('period') or 'prior'} -> {b.get('period') or 'latest'})",
                }
            )
    return alerts


def parse_voice_slider_command(query: str) -> dict[str, Any] | None:
    """Parse 'model owner salary at $220k' style commands into scrubber set_inputs."""
    q = str(query or "").strip().lower()
    if not q:
        return None
    # salary
    m = re.search(
        r"(?:model|set|adjust|move)?\s*(?:owner|officer)?\s*(?:salary|compensation|w-?2)\s*(?:at|to|=)?\s*\$?\s*([\d,]+)\s*k?\b",
        q,
    )
    if m and ("salary" in q or "compensation" in q or "w-2" in q or "w2" in q):
        raw = m.group(1).replace(",", "")
        try:
            n = float(raw)
            if "k" in q[m.end() - 2 : m.end() + 1] or n < 1000:
                # "220k" or bare 220 meaning thousands when salary context
                if n < 1000:
                    n *= 1000
            return {"officerSalary": int(n)}
        except ValueError:
            pass
    m = re.search(r"depreciat\w*\s*(?:add[- ]?back|to|=)?\s*\$?\s*([\d,]+)", q)
    if m:
        try:
            return {"depreciation": float(m.group(1).replace(",", ""))}
        except ValueError:
            pass
    m = re.search(r"interest\s*(?:add[- ]?back|to|=)?\s*\$?\s*([\d,]+)", q)
    if m:
        try:
            return {"interest": float(m.group(1).replace(",", ""))}
        except ValueError:
            pass
    m = re.search(r"(?:one[- ]?time|discretionary)\s*(?:adj|adjustment|to|=)?\s*\$?\s*(-?[\d,]+)", q)
    if m:
        try:
            return {"oneTime": float(m.group(1).replace(",", ""))}
        except ValueError:
            pass
    return None


def build_c0_import_guidance(bundle: dict[str, Any]) -> dict[str, Any]:
    """Honest C0 checklist — what is missing upstream (no invented dollars)."""
    softdent = bundle.get("softdent") if isinstance(bundle.get("softdent"), dict) else {}
    dash = softdent.get("dashboard") if isinstance(softdent.get("dashboard"), dict) else {}
    rows = dash.get("rows") if isinstance(dash.get("rows"), list) else []
    latest = rows[-1] if rows and isinstance(rows[-1], dict) else {}
    period = str(latest.get("period") or latest.get("year_month") or "")
    op = softdent.get("operatory") if isinstance(softdent.get("operatory"), dict) else {}
    chairs = op.get("operatoryChairs") if isinstance(op.get("operatoryChairs"), list) else []
    checks = []
    pending = bool(latest.get("collectionsPending"))
    checks.append(
        {
            "id": "collections",
            "ok": (not pending) and ("collections" in latest) and latest.get("collections") is not None,
            "label": "SoftDent collections reported",
            "detail": (
                f"{period or 'Latest'} collectionsPending — SoftDent Reports > Accounting > Register for a Period "
                f"(MTD) to C:\\SoftDentReportExports, then Refresh SoftDent period imports. Do not invent $0."
                if pending
                else "Collections field present on latest dashboard period."
            ),
        }
    )
    ins = latest.get("insurance")
    pat = latest.get("patient")
    split_ok = False
    try:
        split_ok = float(ins or 0) > 0 and float(pat or 0) > 0
    except (TypeError, ValueError):
        split_ok = False
    checks.append(
        {
            "id": "ar_split",
            "ok": split_ok and not pending,
            "label": "Insurance vs patient split",
            "detail": "Both insurance and patient > 0 on dashboard."
            if split_ok and not pending
            else "Need Register Ins Plan Collections > 0 and patient > 0 (Ins Plan $0 / all-patient dumps stay empty).",
        }
    )
    checks.append(
        {
            "id": "operatory",
            "ok": len(chairs) > 0,
            "label": "Operatory chairs",
            "detail": f"{len(chairs)} chair(s) loaded."
            if chairs
            else "Need operatory_schedule.json with operatoryChairs[] (Sensei/practice export).",
        }
    )
    actions = [
        {
            "id": "export_register",
            "label": "1. SoftDent → Register for a Period (MTD) → C:\\SoftDentReportExports",
        },
        {
            "id": "export_daysheet",
            "label": "2. SoftDent → Daysheet (final) → same folder",
        },
        {
            "id": "refresh_period",
            "label": "3. Click Refresh SoftDent period imports (or ask HAL)",
            "api": "/api/apex/softdent/refresh-period",
        },
    ]
    return {
        "id": "c0-import-guidance",
        "type": "status",
        "label": "C0 Import Remediation",
        "size": "xl",
        "message": f"{sum(1 for c in checks if c['ok'])}/{len(checks)} checks OK",
        "status": "ok" if all(c["ok"] for c in checks) else "empty",
        "checks": checks,
        "actions": actions,
        "refreshUrl": "/api/apex/softdent/refresh-period",
        "hint": "Upstream SoftDent Register/Daysheet required for remaining gaps — NR2 will not invent dollars.",
    }
