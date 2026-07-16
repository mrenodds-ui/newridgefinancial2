"""Teach HAL (and staff) how to pull SoftDent reports via the desktop app.

Source of truth for menus: softdent_gui_menu_map.json + softdent_master_reports.json.
Carestream Help bodies remain in softdent_product_kb_topics.json for deep “what is this report”.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
MENU_MAP_PATH = ROOT / "softdent_gui_menu_map.json"
MASTER_PATH = ROOT / "softdent_master_reports.json"
EXPORT_DIR = r"C:\SoftDentReportExports"

# Permanent SoftDent Select File Name rule (never contradict this in HAL teach).
SOFTDENT_SELECT_FILE_PATH_HYGIENE = (
    "NEVER type SoftDentReportExports or C:\\SOFTDE~1 into SoftDent Select File Name — "
    "keep SoftDent's own folder (e.g. OneDrive\\Documents). "
    f"After SoftDent saves, NR2 lands/copies Excel under {EXPORT_DIR} "
    "(temp %LOCALAPPDATA%\\Temp\\SDWIN*.csv → Excel SaveCopyAs is OK)."
)


def _ascii_menu(path: str) -> str:
    return (
        str(path or "")
        .replace("→", "->")
        .replace("–", "-")
        .replace("—", "-")
    )


MONEY_PULL_CMD = (
    r"python scripts\run_softdent_report_manager_multi_pull.py"
)

# Backward-compatible alias (same Phase-1 money pack)
MONEY_PULL_CMD_LEGACY = (
    r"python scripts\run_softdent_money_widget_pull.py "
    r"--reports register,daysheet,aging,collections"
)


@lru_cache(maxsize=1)
def _load_menu_map() -> dict[str, Any]:
    if not MENU_MAP_PATH.is_file():
        return {}
    return json.loads(MENU_MAP_PATH.read_text(encoding="utf-8-sig"))


@lru_cache(maxsize=1)
def _load_master() -> dict[str, Any]:
    if not MASTER_PATH.is_file():
        return {}
    return json.loads(MASTER_PATH.read_text(encoding="utf-8-sig"))


def clear_softdent_report_pull_cache() -> None:
    _load_menu_map.cache_clear()
    _load_master.cache_clear()


def universal_report_pull_steps() -> list[str]:
    return [
        "Launch SoftDent only via CS SoftDent Software.lnk (-sus) — never bare SDWIN.EXE.",
        "Sign On: COMPUTE / computer (or SOFTDENT_SIGNON_* env). Keyboard or mouse; never Esc on SoftDent main.",
        "Before unattended pulls: close or minimize Chrome Claim Management / NR2 Optical Claims — they steal SoftDent focus.",
        "Open the report: Reports → <category> → <report> (F10 menus preferred if 64-bit menu_select fails ElementNotEnabled).",
        "Output Options appears: click Excel then Enter — OR click Print Preview then Enter. NEVER Printer. NEVER File.",
        "If Excel is GREYED OUT on Output Options: use Print Preview only (NR2 will not invent money from preview; empty ≠ $0 until Excel is enabled in SoftDent).",
        "If SoftDent shows Waiting for printer connection… → Cancel (Alt+C) and choose Excel or Print Preview.",
        "Setup window: set Start/End (or as-of) dates; Doctors/Providers 999 = all unless filtering; OK.",
        SOFTDENT_SELECT_FILE_PATH_HYGIENE,
        "Print Preview path: page to the LAST page for exact totals (page 1 is often incomplete).",
        "Morning money bundle (aging/register/collections) needs Excel enabled for money beams; Preview-only keeps attest_only.",
        "NR2: https://127.0.0.1:8765 → SoftDent page → Sync (or refresh_softdent_period_imports). "
        "Never invent SoftDent dollars; empty ≠ $0.",
    ]


def office_report_catalog() -> list[dict[str, Any]]:
    """NR2-known SoftDent GUI pulls for this office (phased money/ops)."""
    gui = (_load_menu_map().get("reports") or {})
    master = (_load_master().get("reports") or {})
    order = list((_load_menu_map().get("phase1_order") or [])) + [
        rid
        for rid in (_load_menu_map().get("phase2_reserved") or [])
        if rid in gui or rid in master
    ]
    # Also include gui reports not already ordered
    for rid in gui:
        if rid not in order:
            order.append(rid)
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for rid in order:
        if rid in seen:
            continue
        seen.add(rid)
        g = gui.get(rid) or {}
        m = master.get(rid) or {}
        if not g and not m:
            continue
        excel = bool(g.get("excelExport", m.get("excelExport", True)))
        preview = bool(
            g.get("printPreviewAvailable", m.get("printPreviewAvailable", False))
            or str(g.get("outputMode") or m.get("outputMode") or "").startswith("print_preview")
            or str(g.get("outputMode") or "") == "excel_or_preview"
        )
        if str(m.get("outputMode") or "") == "print_preview_only":
            excel = False
            preview = True
        out.append(
            {
                "id": rid,
                "label": g.get("label") or m.get("label") or rid,
                "menuPath": _ascii_menu(
                g.get("menuPath") or m.get("guiMenuPath") or m.get("guiWin32Path") or ""
            ),
                "phase": g.get("phase") or ("1" if rid in (_load_menu_map().get("phase1_order") or []) else "2"),
                "excel": excel,
                "printPreview": preview,
                "landAs": g.get("canonical_template") or "",
                "note": g.get("note") or m.get("why") or "",
                "proven": bool(g.get("proven")),
            }
        )
    return out


def _match_catalog_reports(query: str) -> list[dict[str, Any]]:
    q = str(query or "").lower()
    hits: list[dict[str, Any]] = []
    for row in office_report_catalog():
        blob = f"{row['id']} {row['label']} {row['menuPath']} {row.get('note') or ''}".lower()
        tokens = [t for t in re.split(r"[^a-z0-9]+", q) if len(t) >= 3]
        if not tokens:
            continue
        if sum(1 for t in tokens if t in blob) >= 1 and (
            row["id"] in q
            or any(t in blob for t in tokens if t not in {"softdent", "report", "reports", "pull", "export", "how"})
        ):
            hits.append(row)
    # Prefer named money reports when query is generic
    if not hits and re.search(r"\b(pull|export|run|how).{0,30}(report|softdent)\b", q):
        return [r for r in office_report_catalog() if str(r.get("phase")) == "1"][:5]
    return hits[:8]


def format_softdent_report_pull_hal_reply(query: str = "") -> str:
    """HAL teaching reply: how to pull SoftDent reports on this PC."""
    steps = universal_report_pull_steps()
    lines = [
        "HOW TO PULL SOFTDENT REPORTS (desktop SoftDent — this office):",
        " ".join(f"{i}) {s}" for i, s in enumerate(steps, 1)),
        "Hard rules: Excel or Print Preview only — never Printer; never File; never Esc on SoftDent main; "
        "never Alt+R for Reports (AMD Instant Replay steals it); SoftDent is 32-bit — prefer F10. "
        "If Excel is greyed out on Output Options → Print Preview only (empty ≠ $0 for money until Excel enabled). "
        "Minimize Chrome Claim Management / NR2 Optical Claims before unattended pulls (focus thieves). "
        + SOFTDENT_SELECT_FILE_PATH_HYGIENE,
    ]
    catalog = office_report_catalog()
    phase1 = [r for r in catalog if str(r.get("phase")) == "1" or r.get("phase") == 1]
    if phase1:
        lines.append("Phase-1 money/ops pulls (use these menus):")
        for r in phase1:
            mode = []
            if r.get("excel"):
                mode.append("Excel")
            if r.get("printPreview"):
                mode.append("Print Preview")
            mode_s = "/".join(mode) or "see Help"
            land = f" → land as {r['landAs']}" if r.get("landAs") else ""
            lines.append(f"- {r['id']}: {r['menuPath']} ({mode_s}){land}.")
    phase2 = [r for r in catalog if r not in phase1]
    if phase2:
        lines.append("Also automated / known GUI reports:")
        for r in phase2[:8]:
            mode = "Excel" if r.get("excel") else ("Print Preview only" if r.get("printPreview") else "Help")
            lines.append(f"- {r['id']}: {r['menuPath']} ({mode}).")
    hits = _match_catalog_reports(query)
    if hits and str(query or "").strip():
        lines.append("For your ask, use:")
        for r in hits:
            extra = f" Note: {r['note']}" if r.get("note") else ""
            lines.append(f"- {r['label']}: {r['menuPath']}.{extra}")
    # Special: Trans Format 1
    q = str(query or "").lower()
    if re.search(r"\b(transaction|account\s+tx|ledger|trans\s+for)\b", q):
        lines.append(
            "Transactions detail: Reports → Accounting → Trans for a Period → Excel → "
            "Format 1 = List Each Transaction Separately; Doctors 999. "
            + SOFTDENT_SELECT_FILE_PATH_HYGIENE
        )
    if re.search(r"\b(insurance income|gold|write.?off)\b", q):
        lines.append(
            "Insurance Income / Writeoff Totals on v19.1.4 are often Print Preview only — "
            "not gold InsCo×ADA CSV lines. Preview last page for totals; do not invent gold CSV."
        )
    lines.append(
        "SoftDent Report Manager multi-report: Reports → Report Manager → Set up a Report Group "
        f"named `NR2 Money Widgets` (Register/Collections/Trans/Daysheet/Aging) with Excel "
        "(never Printer; SoftDent Help says Printer — override). Date macros MM/01/YY…MM/99/YY. "
        "Run: Advanced Options → Run Now. If Report Manager is grayed out, use sequential pack."
    )
    lines.append(
        f"Automated bulk pull: `{MONEY_PULL_CMD}` "
        "(Sign On + GUI; falls back to sequential Excel). After files land: SoftDent → Sync in NR2."
    )
    lines.append(
        "Any other SoftDent report (200+ in Help): same Output Options shell - "
        "Reports -> category -> report -> Excel or Print Preview -> Setup -> save/read last page. "
        "Ask HAL the report name for Help text via softdent-product-kb."
    )
    return _ascii_menu(" ".join(lines))


def query_touches_softdent_report_pull(query: str) -> bool:
    """True when user asks how to pull/run/export SoftDent reports."""
    q = str(query or "").lower()
    if re.search(
        r"\b("
        r"(how|teach|show|walk).{0,40}(pull|run|export|get|generate).{0,40}softdent|"
        r"(how|teach|show).{0,40}softdent.{0,40}(report|excel|export|pull)|"
        r"pull\s+softdent|"
        r"softdent\s+(report\s+)?(pull|export)|"
        r"export\s+(from\s+)?softdent|"
        r"run\s+(the\s+)?softdent\s+report|"
        r"softdent\s+output\s+options|"
        r"(excel|print\s*preview).{0,30}softdent\s+report|"
        r"how\s+do\s+i\s+(get|pull|export|run).{0,40}(register|daysheet|aging|collections).{0,20}(from\s+)?softdent|"
        r"teach.{0,20}(hal|him|me).{0,30}(softdent\s+)?report"
        r")\b",
        q,
    ):
        return True
    if "softdent" in q and re.search(
        r"\b(pull|export|run|generate).{0,20}(report|register|daysheet|aging|collections)\b",
        q,
    ):
        return True
    return False


if __name__ == "__main__":
    import sys

    q = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "how to pull SoftDent reports"
    print(format_softdent_report_pull_hal_reply(q))
