"""NR2 Apex subpages — remaining master-map ADD items (consult §2–3).

Taxes / SoftDent / QB / A/R aging-detail / Claims attachments /
Narratives / Docs tax-docs / Library codes / OM tasks / HAL history+logs.
Blocked reconciliation subpages intentionally omitted.
"""

from __future__ import annotations

from typing import Any

from apex_subpages_pack import _parse_money, _section_rows, build_claim_docs, patient_initials


def _nav(label: str, message: str, hint: str) -> dict[str, Any]:
    return {
        "id": f"subpage-nav-{label.lower().replace(' ', '-').replace('·', '-')[:40]}",
        "type": "status",
        "label": label,
        "size": "strip",
        "status": "ok",
        "message": message,
        "hint": hint,
    }


def build_tax_entities(reports: dict[str, Any], bundle: dict[str, Any]) -> list[dict[str, Any]]:
    del reports
    widgets = [
        _nav(
            "Taxes · Entities",
            "S-corp vs owner pass-through split",
            "Hash #taxes/entities · unmapped when QB classes absent.",
        )
    ]
    try:
        from tax_engine import build_tax_plan_from_bundle

        plan = build_tax_plan_from_bundle(bundle) or {}
    except Exception:
        plan = {}
    entity = str(plan.get("entity") or plan.get("entityType") or "S-corp").strip() or "S-corp"
    state = str(plan.get("state") or "").strip() or "—"
    has_book = bool(plan.get("hasBookData"))
    bridge = plan.get("bridgeLines") if isinstance(plan.get("bridgeLines"), list) else []
    widgets.append(
        {
            "id": "tax-entity-card",
            "type": "status",
            "label": "Practice entity",
            "size": "m",
            "status": "ok" if has_book else "empty",
            "message": f"{entity} · {state}" if has_book else "Unmapped — need QB book income",
            "hint": "Planning entity from tax_engine — CPA review required.",
        }
    )
    owner_lines = [
        str(b.get("line") or "")
        for b in bridge
        if isinstance(b, dict) and any(t in str(b.get("line") or "").lower() for t in ("k-1", "ordinary", "pass", "owner"))
    ]
    widgets.append(
        {
            "id": "tax-owner-pass",
            "type": "status",
            "label": "Owner pass-through signals",
            "size": "l",
            "status": "ok" if owner_lines else "empty",
            "message": f"{len(owner_lines)} bridge line(s)" if owner_lines else "No owner/K-1 lines mapped",
            "hint": ("; ".join(owner_lines[:4]) if owner_lines else "Import QB P&L + tax plan mapping.")[:200],
        }
    )
    return widgets


def build_tax_calendar(reports: dict[str, Any], bundle: dict[str, Any]) -> list[dict[str, Any]]:
    del reports
    widgets = [
        _nav(
            "Taxes · Calendar",
            "Quarterly estimated tax tracker",
            "Hash #taxes/calendar · amounts from tax_engine; payments logged locally.",
        )
    ]
    try:
        from tax_engine import build_tax_plan_from_bundle

        plan = build_tax_plan_from_bundle(bundle) or {}
        quarterly = plan.get("quarterlyEstimates") if isinstance(plan.get("quarterlyEstimates"), list) else []
    except Exception:
        quarterly = []
    try:
        from nr2_local_db import list_tax_payments

        logged = {str(p.get("quarter") or ""): p for p in list_tax_payments()}
    except Exception:
        logged = {}
    items = []
    for q in quarterly[:8]:
        if not isinstance(q, dict):
            continue
        lab = str(q.get("label") or q.get("quarter") or q.get("Period") or "").strip()
        amt = q.get("amount")
        try:
            amt_f = float(amt) if amt is not None and amt != "" else None
        except (TypeError, ValueError):
            amt_f = None
        items.append(
            {
                "label": lab,
                "amount": amt_f,
                "due": str(q.get("due") or q.get("dueDate") or "")[:40],
                "logged": bool(logged.get(lab)),
            }
        )
    widgets.append(
        {
            "id": "tax-calendar",
            "type": "tax-calendar",
            "label": "Quarterly Estimates",
            "size": "full",
            "status": "ok" if items else "empty",
            "emptyMessage": "No quarterly estimates — import QB book income for tax_engine plan",
            "items": items,
            "hint": "Planning only · CPA review · Log payment stores local flag only (not e-file).",
        }
    )
    return widgets


def build_tax_workpapers(reports: dict[str, Any], bundle: dict[str, Any], **kwargs: Any) -> list[dict[str, Any]]:
    """Reuse financial workpaper scrubber pattern under taxes."""
    from apex_subpages_pack import build_financial_workpapers

    widgets = build_financial_workpapers(reports, bundle, **kwargs)
    if widgets and widgets[0].get("type") == "status":
        widgets[0]["label"] = "Taxes · Workpapers"
        widgets[0]["hint"] = "Hash #taxes/workpapers · same import-backed categories as Financial workpapers."
    return widgets


def build_softdent_register(reports: dict[str, Any], bundle: dict[str, Any]) -> list[dict[str, Any]]:
    del reports
    widgets = [
        _nav(
            "SoftDent · Register",
            "Read-only transaction register",
            "Hash #softdent/register · no SoftDent write-back.",
        )
    ]
    rows = (
        _section_rows(bundle, "softdent", "procedures")
        or _section_rows(bundle, "softdent", "register")
        or _section_rows(bundle, "softdent", "transactions")
    )
    out = []
    for row in rows[:80]:
        out.append(
            {
                "date": str(row.get("Date") or row.get("ServiceDate") or row.get("date") or "")[:20],
                "provider": str(row.get("Provider") or row.get("Doctor") or "")[:40],
                "code": str(row.get("ProcCode") or row.get("Code") or row.get("ADA") or "")[:12],
                "amount": _parse_money(row.get("Production") or row.get("Amount") or row.get("Fee")),
                "patientInitials": patient_initials(
                    str(row.get("PatientName") or row.get("Patient") or row.get("Name") or "")
                ),
            }
        )
    widgets.append(
        {
            "id": "sd-register-table",
            "type": "data-table",
            "label": "Register (read-only)",
            "size": "full",
            "status": "ok" if out else "empty",
            "emptyMessage": "No SoftDent procedures/register rows",
            "columns": ["date", "provider", "code", "patientInitials", "amount"],
            "rows": out,
            "hint": "Import SoftDent procedures. Patient initials only.",
        }
    )
    return widgets


def build_softdent_schedule(reports: dict[str, Any], bundle: dict[str, Any]) -> list[dict[str, Any]]:
    del reports
    widgets = [
        _nav(
            "SoftDent · Schedule",
            "Operatory utilization",
            "Hash #softdent/schedule · from operatoryChairs import.",
        )
    ]
    softdent = bundle.get("softdent") if isinstance(bundle.get("softdent"), dict) else {}
    chairs: list[Any] = []
    for key in ("operatory", "operatorySchedule", "schedule"):
        sec = softdent.get(key)
        if isinstance(sec, dict) and isinstance(sec.get("operatoryChairs"), list):
            chairs = sec["operatoryChairs"]
            break
    bars = []
    for chair in chairs[:16]:
        if not isinstance(chair, dict):
            continue
        name = str(chair.get("name") or chair.get("chair") or chair.get("id") or "Chair")[:40]
        slots = chair.get("slots") if isinstance(chair.get("slots"), list) else []
        bars.append({"label": name, "value": float(len(slots))})
    widgets.append(
        {
            "id": "sd-schedule-bars",
            "type": "horizontal-bar",
            "label": "Operatory Slot Load",
            "size": "xl",
            "bars": bars,
            "status": "ok" if bars else "empty",
            "emptyMessage": "No operatoryChairs[] on SoftDent import",
            "hint": "Slot counts per chair — not invented utilization %.",
        }
    )
    return widgets


def build_qb_coa(reports: dict[str, Any], bundle: dict[str, Any]) -> list[dict[str, Any]]:
    del reports
    widgets = [
        _nav("QuickBooks · COA", "Chart of accounts mapping", "Hash #quickbooks/coa · import-backed only.")
    ]
    qb = bundle.get("quickbooks") if isinstance(bundle.get("quickbooks"), dict) else {}
    coa = qb.get("chart_of_accounts") if isinstance(qb.get("chart_of_accounts"), dict) else {}
    rows = coa.get("rows") if isinstance(coa.get("rows"), list) else []
    if not rows:
        rows = _section_rows(bundle, "quickbooks", "expenseCategories")
    out = []
    for row in rows[:60]:
        if not isinstance(row, dict):
            continue
        name = str(row.get("Account") or row.get("Category") or row.get("Name") or "").strip()
        if not name:
            continue
        low = name.lower()
        tag = "dental" if any(t in low for t in ("dental", "lab", "hygiene", "supply")) else "other"
        if any(t in low for t in ("revenue", "income", "production")):
            tag = "revenue"
        out.append(
            {
                "account": name[:60],
                "tag": tag,
                "amount": _parse_money(row.get("Amount") or row.get("Balance") or row.get("Total")),
            }
        )
    widgets.append(
        {
            "id": "qb-coa-table",
            "type": "data-table",
            "label": "Chart of Accounts",
            "size": "full",
            "status": "ok" if out else "empty",
            "emptyMessage": "No COA / expenseCategories in QB import",
            "columns": ["account", "tag", "amount"],
            "rows": out,
            "hint": "Dental tag is heuristic from account name — not a CPA mapping.",
        }
    )
    return widgets


def build_qb_vendors(reports: dict[str, Any], bundle: dict[str, Any]) -> list[dict[str, Any]]:
    del reports
    widgets = [
        _nav("QuickBooks · Vendors", "Vendor spend ranking", "Hash #quickbooks/vendors · from QB expenses.")
    ]
    rows = _section_rows(bundle, "quickbooks", "expenses") or _section_rows(
        bundle, "quickbooks", "vendors"
    )
    totals: dict[str, float] = {}
    for row in rows:
        name = str(
            row.get("Vendor") or row.get("Payee") or row.get("Name") or row.get("Account") or ""
        ).strip()
        if not name:
            continue
        amt = _parse_money(row.get("Amount") or row.get("Total"))
        if amt is None:
            continue
        totals[name] = totals.get(name, 0.0) + float(amt)
    bars = [
        {"label": k[:40], "value": v}
        for k, v in sorted(totals.items(), key=lambda kv: kv[1], reverse=True)[:16]
    ]
    widgets.append(
        {
            "id": "qb-vendor-bars",
            "type": "horizontal-bar",
            "label": "Vendor Spend",
            "size": "xl",
            "bars": bars,
            "status": "ok" if bars else "empty",
            "emptyMessage": "No vendor/payee amounts in QB expenses",
            "hint": "1099 flags not inferred — review with CPA/payroll.",
        }
    )
    return widgets


def build_ar_aging_detail(reports: dict[str, Any], bundle: dict[str, Any]) -> list[dict[str, Any]]:
    del reports
    widgets = [
        _nav(
            "A/R · Aging Detail",
            "Patient-level aging drill-down",
            "Hash #ar/aging-detail · initials only · notes via Collections.",
        )
    ]
    try:
        from apex_claims_narratives_pack import build_aging_buckets

        rows = _section_rows(bundle, "softdent", "claims") or _section_rows(
            bundle, "softdent", "claimStatus"
        )
        aging = build_aging_buckets(rows)
        tiles = []
        for key in ("90", "60", "30"):
            for t in (aging.get("buckets") or {}).get(key) or []:
                if isinstance(t, dict):
                    tiles.append(
                        {
                            "claimId": t.get("claimId"),
                            "patientInitials": patient_initials(str(t.get("patientName") or "")),
                            "ageDays": t.get("ageDays"),
                            "bucket": key,
                            "payer": t.get("payer"),
                            "billedAmount": t.get("billedAmount"),
                        }
                    )
        tiles = tiles[:60]
    except Exception:
        tiles = []
    widgets.append(
        {
            "id": "ar-aging-detail-table",
            "type": "data-table",
            "label": "Aged balances (claim-level)",
            "size": "full",
            "status": "ok" if tiles else "empty",
            "emptyMessage": "No aged SoftDent claims",
            "columns": ["claimId", "patientInitials", "ageDays", "bucket", "payer", "billedAmount"],
            "rows": tiles,
            "hint": "Contact history lives in A/R Collections local notes.",
        }
    )
    return widgets


def build_claims_attachments(
    reports: dict[str, Any], bundle: dict[str, Any], *, claim_id: str | None = None, **_kwargs: Any
):
    """CLM-ATT — same dropzone as documents/claim-docs under claims chrome."""
    widgets = build_claim_docs(reports, bundle, claim_id=claim_id)
    if widgets and widgets[0].get("type") == "status":
        widgets[0]["label"] = "Claims · Attachments"
        widgets[0]["hint"] = "Hash #claims/attachments?id=… · same local storage as Documents Claim Docs."
    return widgets


def build_narrative_templates(reports: dict[str, Any], bundle: dict[str, Any]) -> list[dict[str, Any]]:
    del reports, bundle
    widgets = [
        _nav(
            "Narratives · Templates",
            "Payer narrative template library",
            "Hash #narratives/templates · overrides in LocalStore.",
        )
    ]
    templates: list[dict[str, Any]] = []
    try:
        from apex_claims_narratives_pack import STORE_KEY_PAYER_TEMPLATES, _load_json

        data = _load_json(STORE_KEY_PAYER_TEMPLATES)
        raw = data.get("templates") if isinstance(data.get("templates"), dict) else data
        if isinstance(raw, dict):
            for k, v in list(raw.items())[:40]:
                templates.append(
                    {
                        "payer": str(k)[:40],
                        "preview": str(v if not isinstance(v, dict) else v.get("body") or v.get("text") or "")[
                            :120
                        ],
                    }
                )
    except Exception:
        templates = []
    widgets.append(
        {
            "id": "narr-templates",
            "type": "data-table",
            "label": "Templates",
            "size": "full",
            "status": "ok" if templates else "empty",
            "emptyMessage": "No payer templates stored yet — generate from Narratives workspace",
            "columns": ["payer", "preview"],
            "rows": templates,
            "hint": "Edit/versioning via Narratives bridge; this view is read-oriented.",
        }
    )
    return widgets


def build_narrative_history(reports: dict[str, Any], bundle: dict[str, Any]) -> list[dict[str, Any]]:
    del reports, bundle
    widgets = [
        _nav(
            "Narratives · History",
            "Generated narrative history",
            "Hash #narratives/history · patient initials only.",
        )
    ]
    try:
        from apex_claims_narratives_pack import list_narrative_audit

        entries = list_narrative_audit(40)
    except Exception:
        entries = []
    rows = []
    for e in entries:
        if not isinstance(e, dict):
            continue
        detail = e.get("detail") if isinstance(e.get("detail"), dict) else {}
        rows.append(
            {
                "at": str(e.get("at") or e.get("createdAt") or "")[:19],
                "event": str(e.get("event") or "")[:40],
                "claimId": str(detail.get("claimId") or e.get("claimId") or "")[:24],
                "patientInitials": patient_initials(
                    str(detail.get("patientName") or e.get("patientName") or "")
                ),
            }
        )
    widgets.append(
        {
            "id": "narr-history",
            "type": "data-table",
            "label": "Narrative history",
            "size": "full",
            "status": "ok" if rows else "empty",
            "emptyMessage": "No narrative audit events yet",
            "columns": ["at", "event", "claimId", "patientInitials"],
            "rows": rows,
            "hint": "From nr2:v2:narratives:audit — PHI minimized.",
        }
    )
    return widgets


def build_narrative_audit(reports: dict[str, Any], bundle: dict[str, Any]) -> list[dict[str, Any]]:
    """Read-only compliance view — same source as history, compliance framing."""
    widgets = build_narrative_history(reports, bundle)
    if widgets and widgets[0].get("type") == "status":
        widgets[0]["label"] = "Narratives · Audit"
        widgets[0]["message"] = "Compliance audit trail (read-only)"
        widgets[0]["hint"] = "Hash #narratives/audit · nr2:v2:narratives:audit."
    if len(widgets) > 1:
        widgets[1]["id"] = "narr-audit"
        widgets[1]["label"] = "Audit trail"
    return widgets


def build_tax_docs(reports: dict[str, Any], bundle: dict[str, Any]) -> list[dict[str, Any]]:
    del reports, bundle
    widgets = [
        _nav(
            "Documents · Tax Docs",
            "Tax return library for CPA handoff",
            "Hash #documents/tax-docs · local document_library/tax_returns.",
        )
    ]
    try:
        from apex_backend import build_tax_library_widget

        w = build_tax_library_widget()
        widgets.append(w)
    except Exception:
        widgets.append(
            {
                "id": "tax-docs-empty",
                "type": "status",
                "label": "Tax library",
                "size": "l",
                "status": "empty",
                "message": "Tax library unavailable",
                "hint": "Place PDFs under app_data/nr2/document_library/tax_returns.",
            }
        )
    return widgets


def build_library_codes(reports: dict[str, Any], bundle: dict[str, Any]) -> list[dict[str, Any]]:
    del reports
    widgets = [
        _nav(
            "Library · Codes",
            "ADA / fee schedule reference",
            "Hash #library/codes · SoftDent fee schedule import.",
        )
    ]
    rows = _section_rows(bundle, "softdent", "feeSchedule") or _section_rows(bundle, "softdent", "fees")
    out = []
    for row in rows[:80]:
        code = str(row.get("Code") or row.get("ADA") or row.get("ProcCode") or row.get("cdt") or "").strip()
        if not code:
            continue
        out.append(
            {
                "code": code[:12],
                "description": str(row.get("Description") or row.get("Desc") or "")[:60],
                "fee": _parse_money(row.get("Fee") or row.get("Amount") or row.get("UCR")),
            }
        )
    widgets.append(
        {
            "id": "lib-codes-table",
            "type": "data-table",
            "label": "Fee schedule",
            "size": "full",
            "status": "ok" if out else "empty",
            "emptyMessage": "No SoftDent fee schedule rows",
            "columns": ["code", "description", "fee"],
            "rows": out,
            "hint": "Practice fees from import — not invented CDT amounts.",
        }
    )
    return widgets


def build_om_tasks(reports: dict[str, Any], bundle: dict[str, Any]) -> list[dict[str, Any]]:
    del reports, bundle
    widgets = [
        _nav(
            "Office Mgr · Tasks",
            "Task assignment workbench",
            "Hash #office-manager/tasks · local SQLite only.",
        )
    ]
    try:
        from nr2_local_db import list_tasks

        tasks = list_tasks(include_done=True, limit=50)
    except Exception:
        tasks = []
    widgets.append(
        {
            "id": "om-task-board",
            "type": "task-board",
            "label": "Office tasks",
            "size": "full",
            "status": "ok" if tasks else "empty",
            "emptyMessage": "No tasks yet — add one below",
            "tasks": tasks,
            "hint": "Never leaves localhost (nr2_local.sqlite3).",
        }
    )
    return widgets


def build_hal_history(reports: dict[str, Any], bundle: dict[str, Any]) -> list[dict[str, Any]]:
    del reports, bundle
    widgets = [
        _nav(
            "HAL · History",
            "Operator / HAL interaction log",
            "Hash #hal/history · local audit when present.",
        )
    ]
    entries: list[dict[str, Any]] = []
    try:
        from apex_program_improve_pack import _load_json

        data = _load_json("nr2:v2:hal:history")
        raw = data.get("entries") if isinstance(data.get("entries"), list) else []
        for e in raw[-40:]:
            if isinstance(e, dict):
                entries.append(
                    {
                        "at": str(e.get("at") or "")[:19],
                        "role": str(e.get("role") or "")[:12],
                        "preview": str(e.get("text") or e.get("query") or "")[:100],
                    }
                )
    except Exception:
        entries = []
    widgets.append(
        {
            "id": "hal-history-table",
            "type": "data-table",
            "label": "HAL history",
            "size": "full",
            "status": "ok" if entries else "empty",
            "emptyMessage": "No persisted HAL history yet — chat stays in-session until logged",
            "columns": ["at", "role", "preview"],
            "rows": entries,
            "hint": "Optional local key nr2:v2:hal:history — never invents replies.",
        }
    )
    return widgets


def build_hal_system_logs(reports: dict[str, Any], bundle: dict[str, Any]) -> list[dict[str, Any]]:
    del reports
    widgets = [
        _nav(
            "HAL · System Logs",
            "Import telemetry & freshness",
            "Hash #hal/system-logs · diagnostics from import_loader.",
        )
    ]
    diag = bundle.get("diagnostics") if isinstance(bundle.get("diagnostics"), dict) else {}
    summary = diag.get("summary") if isinstance(diag.get("summary"), dict) else {}
    alerts = []
    try:
        from apex_program_improve_pack import assess_import_health

        health = assess_import_health(bundle)
        for a in health.get("alerts") or []:
            if isinstance(a, dict) and a.get("message"):
                alerts.append({"level": str(a.get("level") or "info"), "message": str(a["message"])[:120]})
    except Exception:
        pass
    widgets.append(
        {
            "id": "hal-sys-summary",
            "type": "status",
            "label": "Import diagnostics",
            "size": "m",
            "status": "ok" if summary else "empty",
            "message": (
                f"connected={summary.get('connected')} partial={summary.get('partial')} "
                f"missing={summary.get('missing')} stale={summary.get('stale')}"
                if summary
                else "Diagnostics unavailable"
            ),
            "hint": "From bundle diagnostics — refresh Sync to update.",
        }
    )
    widgets.append(
        {
            "id": "hal-sys-alerts",
            "type": "data-table",
            "label": "Freshness alerts",
            "size": "full",
            "status": "ok" if alerts else "empty",
            "emptyMessage": "No import health alerts",
            "columns": ["level", "message"],
            "rows": alerts,
            "hint": "Import-backed alerts only.",
        }
    )
    return widgets


WAVE5_BUILDERS: dict[tuple[str, str], Any] = {
    ("taxes", "entities"): build_tax_entities,
    ("taxes", "calendar"): build_tax_calendar,
    ("taxes", "workpapers"): build_tax_workpapers,
    ("softdent", "register"): build_softdent_register,
    ("softdent", "schedule"): build_softdent_schedule,
    ("quickbooks", "coa"): build_qb_coa,
    ("quickbooks", "vendors"): build_qb_vendors,
    ("ar", "aging-detail"): build_ar_aging_detail,
    ("claims", "attachments"): build_claims_attachments,
    ("narratives", "templates"): build_narrative_templates,
    ("narratives", "history"): build_narrative_history,
    ("narratives", "audit"): build_narrative_audit,
    ("documents", "tax-docs"): build_tax_docs,
    ("library", "codes"): build_library_codes,
    ("office-manager", "tasks"): build_om_tasks,
    ("hal", "history"): build_hal_history,
    ("hal", "system-logs"): build_hal_system_logs,
}
