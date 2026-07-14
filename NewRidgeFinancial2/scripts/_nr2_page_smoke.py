"""Page-by-page NR2 smoke: APIs + widget payloads. Writes JSON report."""

from __future__ import annotations

import json
import ssl
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE = "https://127.0.0.1:8765"
CTX = ssl._create_unverified_context()
OUT = Path(r"C:\SoftDentFinancialExports\nr2_page_smoke_2026-07-13.json")

PAGES = {
    "financial": [
        "nr2AlertTicker",
        "practiceFinancialOverview",
        "financialProductionTrend",
        "payerMixAndCollections",
        "nr2KpiRibbon",
        "nr2GoalScorecard",
        "nr2MonthlyTrendCombo",
        "nr2CollectionLag",
        "nr2ProductionReconciliation",
        "softdentProductionDaily",
        "providerPerformance",
        "softdentProviderProduction",
        "nr2ProviderCompensationWidget",
        "softdentCollectionsDaily",
        "softdentNewPatientsMTD",
        "softdentClaimsOutstanding",
        "newPatients",
        "softdentAppointmentsSnapshot",
    ],
    "taxes": [
        "quickbooksProfitLossDetail",
        "ebitdaNormalization",
        "quickbooksMonthlyRevenue",
        "quickbooksNetIncomeSummary",
        "quickbooksBalanceSheetSummary",
        "quickbooksCashFlowTrend",
        "quickbooksRevenueByService",
        "quickbooksArAging",
        "quickbooksExpenseBreakdown",
        "accountsPayableAutomation",
        "periodCloseAndPosting",
        "journalPostingQueue",
    ],
    "softdent": [
        "careDeliveryPerformance",
        "softdentCollectionsDaily",
        "softdentNewPatientsMTD",
        "softdentClaimsOutstanding",
        "softdentProviderProduction",
        "softdentAppointmentsSnapshot",
        "softdentArAging",
        "softdentResponsibility",
        "treatmentPlanSummary",
        "caseAcceptance",
        "hygieneRecall",
        "softdentOperatoryGrid",
    ],
    "quickbooks": [
        "quickbooksProfitLossDetail",
        "quickbooksMonthlyRevenue",
        "quickbooksNetIncomeSummary",
        "quickbooksBalanceSheetSummary",
        "quickbooksCashFlowTrend",
        "quickbooksRevenueByService",
        "quickbooksArAging",
        "ebitdaNormalization",
        "quickbooksExpenseBreakdown",
    ],
    "ar": ["arAgingAndCollections", "arOutstandingClaims", "smartClaimsAndReceivables"],
    "claims": ["claimsPipeline"],
    "narratives": ["narrativeWorkflow"],
    "documents": [
        "documentIntakeQueue",
        "documentPreview",
        "periodCloseAndPosting",
        "accountsPayableAutomation",
        "journalPostingQueue",
    ],
    "library": ["documentLibrary"],
    "office-manager": ["officeManagerPriorities", "officeManagerSurfaces"],
    "hal": [
        "halAskHal",
        "halImportHealth",
        "halSituationalHero",
        "halMorningBriefing",
        "practiceFinancialOverview",
        "careDeliveryPerformance",
        "quickbooksProfitLossDetail",
        "arAgingAndCollections",
        "claimsPipeline",
        "caseAcceptance",
        "documentIntakeQueue",
        "officeManagerPriorities",
        "officeManagerSurfaces",
        "nr2AlertTicker",
        "nr2KpiRibbon",
    ],
}

# Apex status/run endpoints to poke (non-destructive GET preferred)
APEX_GETS = [
    "/api/apex/hal/status",
    "/api/apex/hal/orchestrator",
    "/api/apex/hal/should-wave",
    "/api/apex/ticker",
    "/api/apex/unified/snapshot",
    "/api/apex/gold-era-settlement/status",
    "/api/apex/gold-drop-facilitation/status",
    "/api/apex/prodbyada/status",
    "/api/apex/print-preview-audit/status",
    "/api/apex/pwimages-eligibility/status",
]

# Safe HAL prompts (read-only style)
HAL_PROMPTS = [
    "Import status",
    "Summarize MTD production",
]


def fetch(path: str, *, method: str = "GET", body: dict | None = None, timeout: float = 45.0) -> dict:
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, context=CTX, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            elapsed = round((time.perf_counter() - t0) * 1000)
            try:
                payload = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                payload = {"_raw": raw[:500]}
            return {
                "ok": 200 <= resp.status < 300,
                "status": resp.status,
                "ms": elapsed,
                "payload": payload,
            }
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            payload = {"_raw": raw[:500]}
        return {
            "ok": False,
            "status": int(exc.code),
            "ms": round((time.perf_counter() - t0) * 1000),
            "payload": payload,
            "error": str(exc),
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "status": None,
            "ms": round((time.perf_counter() - t0) * 1000),
            "error": f"{type(exc).__name__}:{exc}",
        }


def classify_widget(entry: dict, key: str) -> str:
    if not entry.get("ok"):
        return "broken"
    payload = entry.get("payload") or {}
    # Page widget bundle
    widgets = payload.get("widgets") if isinstance(payload, dict) else None
    if isinstance(widgets, list):
        hit = next((w for w in widgets if isinstance(w, dict) and w.get("id") == key or w.get("key") == key), None)
        if hit is None:
            # sometimes keyed differently
            hit = next(
                (
                    w
                    for w in widgets
                    if isinstance(w, dict)
                    and key in str(w.get("id") or "")
                    or key in str(w.get("key") or "")
                ),
                None,
            )
        if hit is None:
            return "missing"
        # honesty empty
        if hit.get("empty") or hit.get("pending") or hit.get("gapCode"):
            return "honest_empty_or_gap"
        if hit.get("error"):
            return "broken"
        return "working"
    # Single widget or page payload
    if payload.get("error") and not payload.get("ok", True):
        return "broken"
    if payload.get("gapCode") or payload.get("pending"):
        return "honest_empty_or_gap"
    return "working"


def main() -> int:
    report: dict = {
        "checkedAt": datetime.now(timezone.utc).isoformat(),
        "base": BASE,
        "restartNote": "start_nr2_browser.ps1 -Restart -SkipValidation",
        "pages": {},
        "apexGets": {},
        "halPrompts": {},
        "summary": {},
    }

    boot = fetch("/")
    report["bootHtml"] = {
        "ok": boot.get("ok"),
        "status": boot.get("status"),
        "ms": boot.get("ms"),
        "error": boot.get("error"),
    }

    for path in APEX_GETS:
        r = fetch(path)
        slim = {k: r.get(k) for k in ("ok", "status", "ms", "error")}
        pl = r.get("payload") if isinstance(r.get("payload"), dict) else {}
        slim["gapCode"] = pl.get("gapCode") or (pl.get("readiness") or {}).get("reason")
        slim["reply"] = (pl.get("reply") or "")[:160]
        report["apexGets"][path] = slim

    for page, keys in PAGES.items():
        page_result = fetch(f"/api/apex/widgets/{page}")
        entry: dict = {
            "apiOk": page_result.get("ok"),
            "status": page_result.get("status"),
            "ms": page_result.get("ms"),
            "error": page_result.get("error"),
            "widgets": {},
        }
        payload = page_result.get("payload") if isinstance(page_result.get("payload"), dict) else {}
        widget_list = payload.get("widgets") if isinstance(payload.get("widgets"), list) else []
        by_key = {}
        for w in widget_list:
            if not isinstance(w, dict):
                continue
            k = w.get("key") or w.get("id") or w.get("widgetId")
            if k:
                by_key[str(k)] = w
        entry["returnedCount"] = len(widget_list)
        entry["returnedKeys"] = sorted(by_key.keys())
        for key in keys:
            w = by_key.get(key)
            if w is None:
                # fuzzy
                w = next((v for kk, v in by_key.items() if key in kk or kk in key), None)
            if w is None:
                entry["widgets"][key] = {"state": "missing_from_page_api"}
                continue
            state = "working"
            if w.get("error"):
                state = "broken"
            elif w.get("empty") or w.get("pending") or w.get("gapCode") or w.get("noData"):
                state = "honest_empty_or_gap"
            elif w.get("status") in {"error", "failed"}:
                state = "broken"
            elif str(w.get("tone") or "").lower() in {"danger", "error"} and w.get("ok") is False:
                state = "broken"
            title = w.get("title") or w.get("label") or key
            entry["widgets"][key] = {
                "state": state,
                "title": title,
                "gapCode": w.get("gapCode"),
                "empty": w.get("empty"),
                "ok": w.get("ok"),
            }
        report["pages"][page] = entry

    for prompt in HAL_PROMPTS:
        # try common ask endpoints
        candidates = [
            ("/api/apex/hal/orchestrate", {"query": prompt, "page": "financial"}),
            ("/api/hal/ask", {"q": prompt, "page": "financial"}),
            ("/api/ask", {"question": prompt}),
        ]
        tried = []
        for path, body in candidates:
            r = fetch(path, method="POST", body=body, timeout=90.0)
            tried.append(
                {
                    "path": path,
                    "ok": r.get("ok"),
                    "status": r.get("status"),
                    "ms": r.get("ms"),
                    "error": r.get("error"),
                    "replyPreview": str(
                        (r.get("payload") or {}).get("reply")
                        or (r.get("payload") or {}).get("answer")
                        or (r.get("payload") or {}).get("message")
                        or ""
                    )[:200],
                }
            )
            if r.get("ok"):
                break
        report["halPrompts"][prompt] = tried

    # summary counts
    working = missing = gap = broken = 0
    for page, entry in report["pages"].items():
        for _k, w in (entry.get("widgets") or {}).items():
            st = w.get("state")
            if st == "working":
                working += 1
            elif st == "missing_from_page_api":
                missing += 1
            elif st == "honest_empty_or_gap":
                gap += 1
            else:
                broken += 1
    report["summary"] = {
        "widgetWorking": working,
        "widgetHonestEmptyOrGap": gap,
        "widgetMissing": missing,
        "widgetBroken": broken,
        "apexGetOk": sum(1 for v in report["apexGets"].values() if v.get("ok")),
        "apexGetFail": sum(1 for v in report["apexGets"].values() if not v.get("ok")),
        "bootOk": bool(report["bootHtml"].get("ok")),
    }

    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))
    print("WROTE", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
