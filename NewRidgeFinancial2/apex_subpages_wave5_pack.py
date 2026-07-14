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


def build_taxes_planning(reports: dict[str, Any], bundle: dict[str, Any]) -> list[dict[str, Any]]:
    """Taxes · Planning subpage (hal-10562) — quarantined planning KPIs off main cockpit."""
    del reports
    widgets: list[dict[str, Any]] = [
        _nav(
            "Taxes · Planning",
            "Owner / K-1 / quarterly / federal+KS estimates",
            "Hash #taxes/planning · planning only · CPA review · never invent dollars.",
        )
    ]
    try:
        from tax_engine import build_tax_plan_from_bundle

        plan = build_tax_plan_from_bundle(bundle) or {}
    except Exception as exc:  # noqa: BLE001
        widgets.append(
            {
                "id": "tax-planning-engine-error",
                "type": "status",
                "label": "Tax engine",
                "size": "strip",
                "status": "empty",
                "message": "Unavailable",
                "hint": str(exc)[:160],
            }
        )
        return widgets

    has_book = bool(plan.get("hasBookData"))
    period = str(plan.get("periodLabel") or "")

    def _pm(value: Any) -> float | None:
        return _parse_money(value)

    def _money(wid: str, label: str, value: float | None, hint: str) -> dict[str, Any]:
        if value is None:
            return {
                "id": wid,
                "type": "kpi",
                "label": label,
                "value": None,
                "status": "empty",
                "emptyMessage": "No data",
                "hint": hint,
                "collapseWhenEmpty": True,
                "omitWhenEmpty": False,  # subpage may show honest empties as chips
                "size": "s",
                "keepEmpty": True,
            }
        return {
            "id": wid,
            "type": "kpi",
            "label": label,
            "value": float(value),
            "unit": "money",
            "hint": hint,
            "size": "s",
        }

    if has_book:
        widgets.append(
            _money(
                "tax-book-net",
                "Book Net Income",
                _pm(plan.get("bookNetIncome")),
                f"From QuickBooks P&L import ({period or 'period unknown'}).",
            )
        )
        widgets.append(
            _money(
                "tax-est-owner",
                "Est. Owner Tax (planning)",
                _pm(plan.get("totalOwnerTaxEstimate")),
                str(plan.get("disclaimer") or "Planning estimate — CPA review required."),
            )
        )
        widgets.append(
            _money(
                "tax-k1-ordinary",
                "Est. K-1 Ordinary",
                _pm(plan.get("k1Ordinary")),
                "Derived from book net after book-to-tax bridge lines.",
            )
        )
        widgets.append(
            {
                "id": "tax-modeled-w2",
                "type": "kpi",
                "label": "Modeled Officer W-2",
                "value": None,
                "status": "empty",
                "emptyMessage": "No payroll W-2",
                "hint": "No payroll W-2 import — planning salary scenarios are notes only (not shown as $).",
                "collapseWhenEmpty": True,
                "keepEmpty": True,
                "size": "s",
            }
        )
        quarterly = plan.get("quarterlyEstimates") if isinstance(plan.get("quarterlyEstimates"), list) else []
        if quarterly:
            q1 = quarterly[0] if isinstance(quarterly[0], dict) else {}
            fed = _pm(q1.get("federal"))
            ks = _pm(q1.get("kansas"))
            if fed is not None and ks is not None:
                widgets.append(
                    _money(
                        "tax-q-estimate",
                        "Quarterly Estimate (Q1 split)",
                        fed + ks,
                        f"Federal {fed:,.0f} + Kansas {ks:,.0f} · planning only.",
                    )
                )
        fed = _pm(plan.get("federalTaxEstimate"))
        ks = _pm(plan.get("kansasTaxEstimate"))
        if fed is not None:
            widgets.append(
                _money(
                    "tax-federal-est",
                    "Federal Tax (planning)",
                    fed,
                    str(plan.get("federalRateLabel") or "Federal planning rate") + " — CPA review required.",
                )
            )
        if ks is not None:
            widgets.append(
                _money(
                    "tax-kansas-est",
                    "Kansas Tax (planning)",
                    ks,
                    str(plan.get("kansasRateLabel") or "Kansas planning rate") + " — CPA review required.",
                )
            )
        try:
            from apex_backend import (
                build_ebitda_scrubber,
                build_ebitda_waterfall,
                build_filing_workflow_widget,
                build_scenario_manager_widget,
                build_variance_alert_widget,
                build_workpaper_widget,
                _visual_boost_taxes,
            )

            widgets.append(build_ebitda_waterfall(bundle))
            widgets.append(build_ebitda_scrubber(bundle))
            widgets.append(build_scenario_manager_widget())
            widgets.append(build_filing_workflow_widget())
            widgets.append(build_workpaper_widget(plan, bundle))
            widgets.append(build_variance_alert_widget(bundle))
            widgets.extend(_visual_boost_taxes(plan))
        except Exception:
            pass
        scenarios = plan.get("compScenarios") if isinstance(plan.get("compScenarios"), list) else []
        if scenarios:
            notes = [
                str(s.get("note") or "").strip()
                for s in scenarios
                if isinstance(s, dict) and str(s.get("note") or "").strip()
            ]
            widgets.append(
                {
                    "id": "tax-comp-note",
                    "type": "status",
                    "label": "Compensation scenario",
                    "size": "strip",
                    "status": "ok",
                    "message": f"{len(scenarios)} planning scenarios",
                    "hint": (notes[0] if notes else "Document with BLS/MGMA · CPA review.")
                    + " — salary dollars not shown (not from payroll import).",
                }
            )
    else:
        for wid, label, hint in (
            ("tax-book-net", "Book Net Income", "QuickBooks P&L net income not imported — tax KPIs stay empty."),
            ("tax-est-owner", "Est. Owner Tax (planning)", "S-corp estimates require QuickBooks book net income."),
            ("tax-k1-ordinary", "Est. K-1 Ordinary", "Import QuickBooks P&L to unlock book-to-tax planning KPIs."),
            ("tax-modeled-w2", "Modeled Officer W-2", "No book income — W-2 scenarios not shown (would invent dollars)."),
            ("tax-q-estimate", "Quarterly Estimate", "Estimated tax quarters appear after QB net income is available."),
        ):
            widgets.append(
                {
                    "id": wid,
                    "type": "kpi",
                    "label": label,
                    "value": None,
                    "status": "empty",
                    "emptyMessage": "No data",
                    "hint": hint,
                    "collapseWhenEmpty": True,
                    "keepEmpty": True,
                    "size": "s",
                }
            )
        widgets.append(
            {
                "id": "tax-comp-note",
                "type": "status",
                "label": "Compensation scenario",
                "size": "strip",
                "status": "empty",
                "message": "Awaiting book data",
                "hint": "S-corp reasonable-comp scenarios unlock after QuickBooks P&L import.",
            }
        )

    if plan.get("disclaimer"):
        widgets.insert(
            1,
            {
                "id": "tax-disclaimer",
                "type": "status",
                "label": "TAX PLANNING — CPA REVIEW",
                "size": "strip",
                "status": "ok",
                "message": "PLANNING ESTIMATES ONLY — NOT FOR FILING",
                "hint": str(plan.get("disclaimer")),
            },
        )
    # hal-10610: planning data-table + calendar live on this subpage (moved off taxes main)
    try:
        from apex_better_backend_widgets_pack import (
            build_tax_calendar_main,
            build_tax_planning_data_table,
        )

        planning_table = build_tax_planning_data_table(bundle)
        if planning_table:
            widgets.append(planning_table)
        widgets.append(build_tax_calendar_main(bundle))
    except Exception:
        pass
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


STORE_KEY_HAL_HISTORY = "nr2:v2:hal:history"


def _hal_history_entries(limit: int = 80) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    try:
        from apex_program_improve_pack import _load_json

        data = _load_json(STORE_KEY_HAL_HISTORY)
        raw = data.get("entries") if isinstance(data.get("entries"), list) else []
        for e in raw[-limit:]:
            if not isinstance(e, dict):
                continue
            role = str(e.get("role") or "hal").strip().lower()[:16] or "hal"
            if role not in {"user", "operator", "hal", "system"}:
                role = "hal"
            if role == "user":
                role = "operator"
            text = str(e.get("text") or e.get("query") or e.get("preview") or "").strip()
            if not text:
                continue
            entries.append(
                {
                    "id": str(e.get("id") or "")[:40],
                    "at": str(e.get("at") or "")[:19],
                    "role": role,
                    "text": text[:2000],
                    "preview": text[:140],
                }
            )
    except Exception:
        return []
    return entries


def append_hal_history_entry(
    role: str,
    text: str,
    *,
    entry_id: str | None = None,
) -> dict[str, Any]:
    """Persist one HAL chat turn to local store (loopback audit — never invents content)."""
    from apex_program_improve_pack import _load_json, _save_json, _utc_now

    cleaned_role = str(role or "hal").strip().lower()[:16] or "hal"
    if cleaned_role == "user":
        cleaned_role = "operator"
    if cleaned_role not in {"operator", "hal", "system"}:
        cleaned_role = "hal"
    body = str(text or "").strip()
    if not body or body == "Thinking…":
        return {"ok": False, "error": "empty"}
    data = _load_json(STORE_KEY_HAL_HISTORY)
    entries = data.get("entries") if isinstance(data.get("entries"), list) else []
    if not isinstance(entries, list):
        entries = []
    entry = {
        "id": str(entry_id or f"h-{_utc_now()}")[:48],
        "at": _utc_now()[:19],
        "role": cleaned_role,
        "text": body[:2000],
    }
    entries.append(entry)
    payload = {"entries": entries[-200:], "updatedAt": _utc_now()}
    _save_json(STORE_KEY_HAL_HISTORY, payload)
    return {"ok": True, "entry": entry, "count": len(payload["entries"])}


def _hal_ask_widget() -> dict[str, Any]:
    """Live Ask HAL rail — same chat surface as #hal, mounted on History/System Logs."""
    return {
        "id": "hal-ask",
        "type": "hal-chat",
        "label": "Ask HAL",
        "status": "ok",
        "hint": "Live HAL — asks here persist to History.",
    }


def build_hal_history(reports: dict[str, Any], bundle: dict[str, Any]) -> list[dict[str, Any]]:
    """HAL History — conversation log + live Ask HAL rail (#hal/history)."""
    del reports, bundle
    entries = _hal_history_entries(80)
    op_n = sum(1 for e in entries if e.get("role") == "operator")
    hal_n = sum(1 for e in entries if e.get("role") == "hal")
    sys_n = sum(1 for e in entries if e.get("role") == "system")
    last_at = entries[-1]["at"] if entries else "—"
    return [
        {
            "id": "hal-history-strip",
            "type": "hal-sub-strip",
            "label": "History",
            "size": "strip",
            "status": "ok" if entries else "empty",
            "title": "HAL · History",
            "subtitle": "Local audit of asks, replies, and board actions",
            "metrics": [
                {"key": "operator", "label": "Asks", "value": op_n},
                {"key": "hal", "label": "Replies", "value": hal_n},
                {"key": "system", "label": "System", "value": sys_n},
                {"key": "last", "label": "Last", "value": last_at if entries else "—"},
            ],
            "hint": "Replay sends the ask to the HAL rail on this page.",
        },
        {
            "id": "hal-history-feed",
            "type": "hal-history-feed",
            "label": "Conversation log",
            "size": "full",
            "status": "ok" if entries else "empty",
            "emptyMessage": "No history yet — ask HAL in the rail; turns land here.",
            "hint": "Filter by role · Replay asks HAL here · Copy for replies.",
            "entries": list(reversed(entries)),
            "filters": ["all", "operator", "hal", "system"],
            "counts": {"all": len(entries), "operator": op_n, "hal": hal_n, "system": sys_n},
        },
        _hal_ask_widget(),
    ]


def build_hal_system_logs(reports: dict[str, Any], bundle: dict[str, Any]) -> list[dict[str, Any]]:
    """HAL System Logs — diagnostic console + live Ask HAL rail (#hal/system-logs)."""
    del reports
    diag = bundle.get("diagnostics") if isinstance(bundle.get("diagnostics"), dict) else {}
    summary = diag.get("summary") if isinstance(diag.get("summary"), dict) else {}
    connected = int(summary.get("connected") or 0) if summary else 0
    partial = int(summary.get("partial") or 0) if summary else 0
    missing = int(summary.get("missing") or 0) if summary else 0
    stale = int(summary.get("stale") or 0) if summary else 0
    total = int(summary.get("total") or 0) if summary else 0

    if total > 0 and missing == 0 and partial == 0 and stale == 0:
        posture = "Operational"
        posture_hint = "All tracked datasets connected."
    elif total > 0:
        posture = "Degraded"
        posture_hint = "Missing or partial imports — refresh Sync before posting."
    else:
        posture = "Standby"
        posture_hint = "Awaiting import diagnostics."

    alerts: list[dict[str, Any]] = []
    try:
        from apex_program_improve_pack import assess_import_health

        health = assess_import_health(bundle)
        for a in health.get("alerts") or []:
            if isinstance(a, dict) and a.get("message"):
                level = str(a.get("level") or "info").lower()
                if level not in {"error", "warn", "warning", "info", "ok"}:
                    level = "info"
                if level == "warning":
                    level = "warn"
                alerts.append(
                    {
                        "level": level,
                        "at": str(a.get("at") or a.get("ts") or "")[:19],
                        "source": str(a.get("source") or a.get("datasetKey") or "import")[:40],
                        "message": str(a["message"])[:180],
                    }
                )
    except Exception:
        pass

    datasets = diag.get("datasets") if isinstance(diag.get("datasets"), list) else []
    gap_n = 0
    for row in datasets:
        if not isinstance(row, dict):
            continue
        if str(row.get("severity") or "") == "optional":
            continue
        if row.get("automated") is False:
            continue
        status = str(row.get("status") or "")
        if status in {"missing", "stale", "partial"} or int(row.get("rowCount") or 0) <= 0:
            gap_n += 1
            if len(alerts) < 40:
                alerts.append(
                    {
                        "level": "error" if status == "missing" else "warn",
                        "at": "",
                        "source": str(row.get("datasetKey") or "dataset")[:40],
                        "message": str(row.get("detail") or f"{status} · rows={row.get('rowCount') or 0}")[:180],
                    }
                )

    log_lines = alerts[:60]
    return [
        {
            "id": "hal-sys-strip",
            "type": "hal-sub-strip",
            "label": "System Logs",
            "size": "strip",
            "status": "ok" if summary else "empty",
            "title": "HAL · System Logs",
            "subtitle": posture_hint,
            "metrics": [
                {"key": "posture", "label": "Posture", "value": posture},
                {"key": "connected", "label": "Connected", "value": f"{connected}/{total}" if total else "—"},
                {"key": "partial", "label": "Partial", "value": partial if summary else "—"},
                {"key": "missing", "label": "Missing", "value": missing if summary else "—"},
                {"key": "stale", "label": "Stale", "value": stale if summary else "—"},
                {"key": "gaps", "label": "Gaps", "value": gap_n},
            ],
            "hint": "Ask HAL about a console line from the Ask button on each row.",
        },
        {
            "id": "hal-sys-console",
            "type": "hal-sys-console",
            "label": "Diagnostic console",
            "size": "full",
            "status": "ok" if log_lines else "empty",
            "emptyMessage": "No import health alerts — Sync looks quiet.",
            "hint": "Import-backed lines only · Ask HAL about a row · Sync to refresh.",
            "lines": log_lines,
            "filters": ["all", "error", "warn", "info"],
        },
        _hal_ask_widget(),
    ]


def build_claims_kanban_subpage(reports: dict[str, Any], bundle: dict[str, Any]) -> list[dict[str, Any]]:
    """Full Claims workbench — moved off main page (Moonshot compact Phase 4)."""
    del reports
    widgets: list[dict[str, Any]] = [
        _nav(
            "Claims · Kanban",
            "Full table + kanban workbench",
            "Hash #claims/kanban · SoftDent read-only · NR2 actions only.",
        )
    ]
    try:
        from apex_claims_narratives_pack import build_status_columns, kanban_widget
        from apex_program_improve_pack import apply_era_to_kanban_columns, attachment_counts

        claim_rows = _section_rows(bundle, "softdent", "claims") or _section_rows(
            bundle, "softdent", "claimStatus"
        )
        kanban_payload = build_status_columns(claim_rows if isinstance(claim_rows, list) else [])
        cols = kanban_payload.get("columns") if isinstance(kanban_payload.get("columns"), dict) else {}
        kanban_payload["columns"] = apply_era_to_kanban_columns(cols)
        kanban_payload["counts"] = {
            k: len(v) if isinstance(v, list) else 0 for k, v in (kanban_payload.get("columns") or {}).items()
        }
        att_counts = attachment_counts()
        for _col, cards in (kanban_payload.get("columns") or {}).items():
            if not isinstance(cards, list):
                continue
            for card in cards:
                if not isinstance(card, dict):
                    continue
                cid = str(card.get("claimId") or "")
                n = int(att_counts.get(cid) or 0)
                if n and not card.get("attachments"):
                    card["attachments"] = {"current": n, "required": None}
        widgets.append(kanban_widget(kanban_payload))
    except Exception as exc:
        widgets.append(
            {
                "id": "claims-kanban-error",
                "type": "status",
                "label": "Kanban",
                "size": "strip",
                "status": "empty",
                "emptyMessage": f"Kanban unavailable: {exc}",
            }
        )
    return widgets


def build_om_operatory_subpage(reports: dict[str, Any], bundle: dict[str, Any]) -> list[dict[str, Any]]:
    """Operatory detail drill-down (Moonshot compact Phase 4)."""
    widgets = build_softdent_schedule(reports, bundle)
    if widgets and isinstance(widgets[0], dict) and widgets[0].get("type") == "status":
        widgets[0]["label"] = "Office Mgr · Operatory"
        widgets[0]["hint"] = "Hash #office-manager/operatory · from operatoryChairs import."
    try:
        from apex_bar_trend_page_org_pack import build_operatory_util_chart
        from apex_financial_console_pack import collapse_empty_large

        util = build_operatory_util_chart(bundle)
        if util.get("status") == "empty":
            util = collapse_empty_large(util)
        else:
            util["size"] = "m"
        widgets.insert(1, util)
    except Exception:
        pass
    return widgets


def _build_ops_via_parent(page: str, reports: dict[str, Any], bundle: dict[str, Any]) -> list[dict[str, Any]]:
    """Reuse parent page builders; surface only demoted widgets on #{page}/ops."""
    from apex_backend import _PAGE_BUILDERS
    from apex_compact_pages_pack import select_demoted_widgets

    builder = _PAGE_BUILDERS.get(str(page or "").strip().lower())
    if not callable(builder):
        return select_demoted_widgets([], page=page)
    try:
        widgets = builder(reports or {}, bundle or {})
    except Exception:
        widgets = []
    return select_demoted_widgets(widgets if isinstance(widgets, list) else [], page=page)


def build_financial_ops(reports: dict[str, Any], bundle: dict[str, Any]) -> list[dict[str, Any]]:
    return _build_ops_via_parent("financial", reports, bundle)


def build_claims_ops(reports: dict[str, Any], bundle: dict[str, Any]) -> list[dict[str, Any]]:
    return _build_ops_via_parent("claims", reports, bundle)


def build_taxes_ops(reports: dict[str, Any], bundle: dict[str, Any]) -> list[dict[str, Any]]:
    return _build_ops_via_parent("taxes", reports, bundle)


def build_hal_ops(reports: dict[str, Any], bundle: dict[str, Any]) -> list[dict[str, Any]]:
    return _build_ops_via_parent("hal", reports, bundle)


def build_softdent_ops(reports: dict[str, Any], bundle: dict[str, Any]) -> list[dict[str, Any]]:
    return _build_ops_via_parent("softdent", reports, bundle)


def build_ar_ops(reports: dict[str, Any], bundle: dict[str, Any]) -> list[dict[str, Any]]:
    return _build_ops_via_parent("ar", reports, bundle)


def build_qb_ops(reports: dict[str, Any], bundle: dict[str, Any]) -> list[dict[str, Any]]:
    return _build_ops_via_parent("quickbooks", reports, bundle)


def build_om_ops(reports: dict[str, Any], bundle: dict[str, Any]) -> list[dict[str, Any]]:
    return _build_ops_via_parent("office-manager", reports, bundle)


def build_content_ops(reports: dict[str, Any], bundle: dict[str, Any]) -> list[dict[str, Any]]:
    return _build_ops_via_parent("content", reports, bundle)


def build_documents_ops(reports: dict[str, Any], bundle: dict[str, Any]) -> list[dict[str, Any]]:
    return _build_ops_via_parent("documents", reports, bundle)


def build_narratives_ops(reports: dict[str, Any], bundle: dict[str, Any]) -> list[dict[str, Any]]:
    return _build_ops_via_parent("narratives", reports, bundle)


def build_library_ops(reports: dict[str, Any], bundle: dict[str, Any]) -> list[dict[str, Any]]:
    return _build_ops_via_parent("library", reports, bundle)


def build_content_documents(reports: dict[str, Any], bundle: dict[str, Any]) -> list[dict[str, Any]]:
    from apex_backend import _documents_widgets

    return _documents_widgets(reports or {}, bundle or {})


def build_content_narratives(reports: dict[str, Any], bundle: dict[str, Any]) -> list[dict[str, Any]]:
    from apex_backend import _narratives_widgets

    return _narratives_widgets(reports or {}, bundle or {})


def build_content_library(reports: dict[str, Any], bundle: dict[str, Any]) -> list[dict[str, Any]]:
    from apex_backend import _library_widgets

    return _library_widgets(reports or {}, bundle or {})


WAVE5_BUILDERS: dict[tuple[str, str], Any] = {
        ("taxes", "entities"): build_tax_entities,
        ("taxes", "calendar"): build_tax_calendar,
        ("taxes", "planning"): build_taxes_planning,
        ("taxes", "workpapers"): build_tax_workpapers,
        ("taxes", "ops"): build_taxes_ops,
    ("softdent", "register"): build_softdent_register,
    ("softdent", "schedule"): build_softdent_schedule,
    ("softdent", "ops"): build_softdent_ops,
    ("quickbooks", "coa"): build_qb_coa,
    ("quickbooks", "vendors"): build_qb_vendors,
    ("quickbooks", "ops"): build_qb_ops,
    ("ar", "aging-detail"): build_ar_aging_detail,
    ("ar", "ops"): build_ar_ops,
    ("claims", "attachments"): build_claims_attachments,
    ("claims", "kanban"): build_claims_kanban_subpage,
    ("claims", "ops"): build_claims_ops,
    ("narratives", "templates"): build_narrative_templates,
    ("narratives", "history"): build_narrative_history,
    ("narratives", "audit"): build_narrative_audit,
    ("narratives", "ops"): build_narratives_ops,
    ("documents", "tax-docs"): build_tax_docs,
    ("documents", "ops"): build_documents_ops,
    ("library", "codes"): build_library_codes,
    ("library", "ops"): build_library_ops,
    ("content", "ops"): build_content_ops,
    ("content", "documents"): build_content_documents,
    ("content", "narratives"): build_content_narratives,
    ("content", "library"): build_content_library,
    ("content", "templates"): build_narrative_templates,
    ("content", "tax-docs"): build_tax_docs,
    ("content", "codes"): build_library_codes,
    ("office-manager", "tasks"): build_om_tasks,
    ("office-manager", "operatory"): build_om_operatory_subpage,
    ("office-manager", "ops"): build_om_ops,
    ("financial", "ops"): build_financial_ops,
    ("hal", "history"): build_hal_history,
    ("hal", "system-logs"): build_hal_system_logs,
    ("hal", "ops"): build_hal_ops,
}
