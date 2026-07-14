#!/usr/bin/env python3
"""Build softdent_product_kb.json from local SoftDent Online Help CHM extract + NR2 catalogs.

Usage:
  python NewRidgeFinancial2/scripts/build_softdent_product_kb.py
  python NewRidgeFinancial2/scripts/build_softdent_product_kb.py --help-root C:\\SoftDentReportExports\\softdent_help_extract
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from datetime import date
from pathlib import Path

NR2 = Path(__file__).resolve().parents[1]
DEFAULT_HELP_ROOT = Path(r"C:\SoftDentReportExports\softdent_help_extract")
OUT_PATH = NR2 / "softdent_product_kb.json"
TOPICS_OUT_PATH = NR2 / "softdent_product_kb_topics.json"
HELP_BASE_URL = (
    "https://help.carestreamdental.com/rh/web/server/SoftDent/projects_responsive/OH_DE1010/"
)

# Core “how SoftDent works” pages always embedded with fuller text
HOW_IT_WORKS_PAGES = (
    "AbtPM.htm",
    "HnRpt.htm",
    "AcctRp.htm",
    "HnPMR.htm",
    "KystrkSht.htm",
    "Daily_Reports__End_of_Day.htm",
    "AccesERA.htm",
    "HnPstTrn.htm",
    "HnTrPln.htm",
    "HnOpScd.htm",
    "HnChtImg.htm",
    "HnInsCo.htm",
    "HnInsPlnInf.htm",
    "InsRpt.htm",
    "ActAgeRp.htm",
    "RegstrRpt.htm",
    "Daysheet.htm",
    "Using_Online_Help.htm",
    "Tutorial.htm",
)

REPORT_CATEGORY_PAGES = {
    "Accounting": "AcctRp.htm",
    "Practice Management": "HnPMR.htm",
    "Patient": "PtRpt.htm",
    "Account": "ActRpt.htm",
    "Recall/Appt": "RclApRpt.htm",
    "Provider/Referring Dr": "PvdrRpt.htm",
    "Insurance": "InsRpt.htm",
    "Trojan Plan": "TroPlnRpt.htm",
    "ADA/Trans/Diag Codes": "TrDiag.htm",
    "Rx/Pharmacies/Labs": "RxLabRpt.htm",
    "Report Manager": "BlubkRpt.htm",
    "Audit Trail": "HnAudTrlRpt.htm",
    "User-Selected": "UsrSelRpt14.htm",
}

# Alternate filenames seen in CHM extract
REPORT_CATEGORY_ALT = {
    "Accounting": ("AcctRp.htm", "AcctRpts14.htm"),
    "Patient": ("PtRpt.htm", "PtRpts14.htm"),
    "Account": ("ActRpt.htm", "ActRpts14.htm"),
    "Recall/Appt": ("RclApRpt.htm",),
    "Provider/Referring Dr": ("PvdrRpt.htm", "ProvRpts.htm"),
    "Insurance": ("InsRpt.htm",),
    "Trojan Plan": ("TroPlnRpt.htm", "Trojan.htm"),
    "ADA/Trans/Diag Codes": ("TrDiag.htm",),
    "Rx/Pharmacies/Labs": ("RxLabRpt.htm",),
    "Report Manager": ("BlubkRpt.htm", "Adding_a_New_Report_to_a_Report_Group.htm"),
    "Audit Trail": ("HnAudTrlRpt.htm", "Audit_Trail_Reports.htm", "AudTrail.htm"),
    "User-Selected": ("UsrSelRpt14.htm", "Creating_User-Selected_Reports.htm"),
}

NR2_GUI_MAP = {
    "register": {"menu": "Reports > Accounting > Registers > Period", "phase": 1},
    "collections": {
        "menu": "Reports > Practice Management > Collection Reports > Summary",
        "phase": 1,
    },
    "transactions": {"menu": "Reports > Accounting > Trans for a Period", "phase": 1},
    "daysheet": {"menu": "Reports > Accounting > Daysheet", "phase": 1},
    "aging": {"menu": "Reports > Accounting > Account Aging", "phase": 1},
    "writeoff_totals": {
        "menu": "Reports > Practice Management > Insurance Reports > Writeoff Totals",
        "phase": 2,
    },
    "insurance_payment_distribution": {
        "menu": "Reports > Accounting > Insurance Payment Distribution",
        "phase": 2,
    },
    "insurance_payment_analysis": {
        "menu": "Reports > Practice Management > Insurance Reports > Insurance Income",
        "phase": 2,
        "notes": "Print Preview only on v19.1.4 — not gold CSV",
    },
    "production_by_ada_code": {
        "menu": "Reports > Practice Management > Production Reports > Production by ADA Code",
        "phase": 2,
    },
}


def _strip_tags(text: str) -> str:
    text = re.sub(r"(?is)<script.*?>.*?</script>", " ", text)
    text = re.sub(r"(?is)<style.*?>.*?</style>", " ", text)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _find_page(root: Path, primary: str, alts: tuple[str, ...] = ()) -> Path | None:
    for name in (primary, *alts):
        p = root / name
        if p.is_file():
            return p
    return None


def parse_hhc_toc(hhc_path: Path) -> list[dict]:
    """Parse HTML Help .hhc into flat list with inferred depth via nesting."""
    raw = hhc_path.read_text(encoding="utf-8", errors="replace")
    # Walk tokens
    entries: list[dict] = []
    depth = 0
    for m in re.finditer(
        r"(</?ul\b[^>]*>)|(<param\s+name=\"Name\"\s+value=\"([^\"]*)\"\s*/?>)|"
        r"(<param\s+name=\"Local\"\s+value=\"([^\"]*)\"\s*/?>)",
        raw,
        re.I,
    ):
        tok = m.group(0).lower()
        if tok.startswith("<ul"):
            depth += 1
            continue
        if tok.startswith("</ul"):
            depth = max(0, depth - 1)
            continue
        if m.group(3) is not None:
            name = html.unescape(m.group(3)).strip()
            if name:
                entries.append({"name": name, "local": "", "depth": depth})
            continue
        if m.group(5) is not None and entries:
            local = html.unescape(m.group(5)).strip().replace("\\", "/")
            entries[-1]["local"] = local
    return entries


def top_level_books(toc: list[dict]) -> list[str]:
    # Depth 1 or lowest common depth books
    if not toc:
        return []
    min_d = min(e["depth"] for e in toc)
    books = []
    seen = set()
    for e in toc:
        if e["depth"] <= min_d + 1 and e["name"] not in seen:
            # Prefer book-like (no Local or Local ends with folder)
            books.append(e["name"])
            seen.add(e["name"])
    return books[:80]


def parse_report_table(page: Path) -> list[dict]:
    """Extract report name / description / frequency from SoftDent Help HTML tables."""
    raw = page.read_text(encoding="utf-8", errors="replace")
    rows: list[dict] = []
    # Table rows: <tr> ... </tr>
    for tr in re.findall(r"(?is)<tr[^>]*>(.*?)</tr>", raw):
        cells = re.findall(r"(?is)<t[dh][^>]*>(.*?)</t[dh]>", tr)
        if len(cells) < 2:
            continue
        cleaned = [_strip_tags(c) for c in cells]
        if not cleaned[0] or cleaned[0].lower() in {"report name", "name", "description"}:
            continue
        name = cleaned[0]
        # Skip pure headers
        if name.lower() in {"accounting reports", "practice management reports"}:
            continue
        desc = cleaned[1] if len(cleaned) > 1 else ""
        freq = cleaned[2] if len(cleaned) > 2 else ""
        # Drop "For more information..." tails for brevity in KB
        desc = re.sub(r"(?i)\s*For more information,?\s*see.*$", "", desc).strip()
        rows.append({"name": name, "description": desc, "frequency": freq})
    return rows


def parse_abt_modules(page: Path | None) -> list[str]:
    if not page or not page.is_file():
        return []
    text = _strip_tags(page.read_text(encoding="utf-8", errors="replace"))
    # Topics listed after "This online help contains the following topics:"
    m = re.search(r"following topics:\s*(.+?)(?:Related|Backing Up|$)", text, re.I)
    if not m:
        return []
    chunk = m.group(1)
    # Split on "What's New" keeps separately; also Known topic starts
    known_starts = [
        "Finding Answers",
        "What's New",
        "Backing Up Data",
        "Related Documentation",
        "End of Year Procedures",
        "Getting Started",
        "Entering Providers",
        "Handling Transactions",
        "Setting Up Insurance",
        "Handling Patients",
        "Handling Accounts",
        "Scheduling",
        "Charting",
        "Treatment Planning",
        "Electronic Claims",
        "ERA",
        "Imaging",
        "Reports",
        "Security",
        "Utilities",
    ]
    # Fallback: split on capital sequences by scanning known phrases presence
    found = []
    for phrase in [
        "Finding Answers",
        "Backing Up Data",
        "Related Documentation",
        "End of Year Procedures",
        "Getting Started",
        "Entering Providers, Employers, and Schools",
        "Handling Transactions and Codes",
        "Setting Up Insurance",
    ]:
        if phrase.lower() in chunk.lower():
            found.append(phrase)
    # Also pull What's New version headings
    for wn in re.findall(r"What's New in Version [0-9.]+", chunk):
        found.append(wn)
    return found or [chunk[:200]]


def parse_keystrokes(page: Path | None) -> dict:
    if not page or not page.is_file():
        return {}
    text = _strip_tags(page.read_text(encoding="utf-8", errors="replace"))
    keys = {}
    for m in re.finditer(r"\b(F\d{1,2})\s+([A-Z][^F]{5,80?}?)(?=\sF\d|\sKeystroke|$)", text):
        keys[m.group(1)] = m.group(2).strip(" .")
    # Fallback known from our OPS + Help
    keys.setdefault("F1", "Opens the online help")
    keys.setdefault("F3", "Opens the Account search window")
    keys.setdefault("F4", "Opens the Provider search window")
    keys.setdefault("F5", "Opens the Patient search window")
    keys.setdefault("F8", "Opens the ADA Code search window")
    keys.setdefault("F10", "Opens SoftDent main menus (prefer over Alt+letter when AMS steals Accel)")
    return keys


def extract_title(raw: str, fallback: str) -> str:
    m = re.search(r"(?is)<title[^>]*>(.*?)</title>", raw)
    if m:
        t = _strip_tags(m.group(1))
        if t:
            return t
    return fallback


def ingest_help_topic_bodies(
    help_root: Path,
    *,
    max_chars: int = 3500,
    how_it_works_max_chars: int = 12000,
) -> tuple[list[dict], dict[str, dict]]:
    """Strip every SoftDent Help .htm into searchable topic bodies."""
    topics: list[dict] = []
    how_it_works: dict[str, dict] = {}
    how_set = {n.lower() for n in HOW_IT_WORKS_PAGES}
    for htm in sorted(help_root.glob("*.htm")):
        # Skip obvious non-topic assets mistakenly named .htm
        if htm.stem.lower().startswith("+") or "button" in htm.stem.lower():
            continue
        try:
            raw = htm.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        body = _strip_tags(raw)
        if len(body) < 60:
            continue
        title = extract_title(raw, htm.stem.replace("_", " "))
        # Drop “SoftDent Help” noise prefixes
        title = re.sub(r"(?i)^softDent help\s*[|>]\s*", "", title).strip() or title
        is_how = htm.name.lower() in how_set
        cap = how_it_works_max_chars if is_how else max_chars
        entry = {
            "id": htm.stem,
            "file": htm.name,
            "title": title,
            "body": body[:cap],
            "helpUrl": HELP_BASE_URL + htm.name,
            "chars": len(body),
            "truncated": len(body) > cap,
        }
        topics.append(entry)
        if is_how:
            how_it_works[htm.stem] = {
                "title": title,
                "file": htm.name,
                "helpUrl": entry["helpUrl"],
                "body": body[:how_it_works_max_chars],
                "truncated": len(body) > how_it_works_max_chars,
            }
    return topics, how_it_works


def build_how_softdent_works(how_pages: dict[str, dict], doctrine: dict) -> dict:
    """Operational map HAL uses to explain SoftDent end-to-end."""
    return {
        "summary": (
            "SoftDent is Carestream/Sensei on-premise dental practice management (Win32). "
            "Staff work in Account/Patient/Provider lists, post transactions, schedule operatories, "
            "manage insurance plans/claims/ERA, chart/treatment-plan, and run 200+ reports via "
            "Reports → Output Options (Excel or Print Preview — never Printer at this office)."
        ),
        "lifecycle": [
            "Launch CS SoftDent Software.lnk (-sus) → Sign On",
            "Daily scheduling / check-in (operatory schedule, patients F5, accounts F3)",
            "Post production & payments (Handling Transactions)",
            "Insurance: plans/companies, claim batch, eClaims, ERA remits",
            "End of day: Daysheet + recommended daily reports",
            "Period close money: Register / Aging / Collections / Trans Excel → NR2 sync",
            "Practice analytics: Practice Management report family",
            "Clinical: charting, treatment plans, imaging launcher",
            "Admin: audit trail, backup, year-end, CDT updates",
        ],
        "officeDoctrine": doctrine,
        "coreHelpArticles": how_pages,
    }


def load_nr2_automation(nr2: Path) -> dict:
    gui = {}
    master = {}
    gpath = nr2 / "softdent_gui_menu_map.json"
    mpath = nr2 / "softdent_master_reports.json"
    if gpath.is_file():
        gui = json.loads(gpath.read_text(encoding="utf-8-sig"))
    if mpath.is_file():
        master = json.loads(mpath.read_text(encoding="utf-8-sig"))
    return {"guiMenuMap": gui, "masterReports": master}


def build_kb(help_root: Path, nr2: Path) -> dict:
    hhc = help_root / "SoftDent_OnlineHelp_OH_DE1010.hhc"
    toc = parse_hhc_toc(hhc) if hhc.is_file() else []
    books = top_level_books(toc)

    report_categories: dict[str, dict] = {
        "overview": {
            "helpTopic": "HnRpt.htm",
            "helpUrl": HELP_BASE_URL + "HnRpt.htm",
            "categoryCount": 13,
            "categories": [
                "Accounting",
                "Patient",
                "Account",
                "Recall/Appt",
                "Provider/Referring Dr",
                "Insurance",
                "Trojan Plan",
                "ADA/Trans/Diag Codes",
                "Rx/Pharmacies/Labs",
                "Practice Management",
                "Report Manager",
                "Audit Trail",
                "User-Selected",
            ],
            "note": "SoftDent includes over 200 reports across thirteen report categories.",
        }
    }

    all_reports: list[dict] = []
    for cat, primary in REPORT_CATEGORY_PAGES.items():
        alts = REPORT_CATEGORY_ALT.get(cat, ())
        page = _find_page(help_root, primary, alts)
        reports = parse_report_table(page) if page else []
        # Practice Management page lists many without nested Insurance Reports submenu label —
        # keep as flat under category.
        report_categories[cat] = {
            "helpTopic": page.name if page else primary,
            "helpUrl": HELP_BASE_URL + (page.name if page else primary),
            "menuPath": f"Reports > {cat}",
            "reports": reports,
            "reportCount": len(reports),
            "sourceFilePresent": bool(page),
        }
        for r in reports:
            all_reports.append(
                {
                    "category": cat,
                    "name": r["name"],
                    "description": r["description"],
                    "frequency": r.get("frequency") or "",
                    "helpUrl": report_categories[cat]["helpUrl"],
                    "nr2GuiId": None,
                }
            )

    # Link NR2 GUI ids
    for rep in all_reports:
        lname = rep["name"].lower()
        for gid, meta in NR2_GUI_MAP.items():
            mlabel = meta["menu"].split(">")[-1].strip().lower()
            if mlabel in lname or lname in mlabel or (
                gid == "register" and "register" in lname
            ) or (gid == "aging" and "aging" in lname) or (
                gid == "transactions" and "transaction" in lname and "period" in lname
            ) or (gid == "insurance_payment_analysis" and "insurance income" in lname) or (
                gid == "production_by_ada_code" and "ada code" in lname
            ) or (gid == "collections" and "collection" in lname and "summary" in lname) or (
                gid == "writeoff_totals" and "write" in lname and "off" in lname
            ) or (gid == "insurance_payment_distribution" and "payment distribution" in lname) or (
                gid == "daysheet" and "daysheet" in lname
            ):
                rep["nr2GuiId"] = gid

    eod = _find_page(help_root, "Daily_Reports__End_of_Day.htm", ("Daily_Reports_End_of_Day.htm",))
    eod_reports = []
    if eod:
        text = _strip_tags(eod.read_text(encoding="utf-8", errors="replace"))
        for name in [
            "Daysheet",
            "End of Day Call Backs",
            "Daily Register",
            "Unsubmitted Claims",
            "Daily Operatory Schedule",
        ]:
            if name.lower() in text.lower():
                eod_reports.append(name)

    keystrokes = parse_keystrokes(_find_page(help_root, "KystrkSht.htm"))
    modules = parse_abt_modules(_find_page(help_root, "AbtPM.htm"))

    nr2_auto = load_nr2_automation(nr2)
    gui_ids = list((nr2_auto.get("guiMenuMap") or {}).get("reports") or {}.keys())

    product_modules = [
        {
            "id": "scheduling",
            "label": "Scheduling / Appointments",
            "summary": "Operatories, appointment book, confirmation, daily op schedule, end-of-day callbacks.",
            "helpHints": ["Daily Op Schedule", "Recall/Appt reports", "Contact Expert"],
        },
        {
            "id": "patients_accounts",
            "label": "Patients & Accounts",
            "summary": "Patient/account search (F5/F3), demographics, guarantors, budget plans, statements.",
            "helpHints": ["Account reports", "Patient reports", "Budget Plan Reports"],
        },
        {
            "id": "transactions_codes",
            "label": "Transactions & Codes",
            "summary": "Posting transactions, ADA/transaction/diagnosis codes, fee schedules.",
            "helpHints": ["Handling Transactions and Codes", "ADA/Trans/Diag Codes reports"],
        },
        {
            "id": "insurance_edi",
            "label": "Insurance, eClaims & ERA",
            "summary": "Insurance companies/plans, claim batching, electronic claims, ERA remittance access.",
            "helpHints": ["Insurance reports", "AccesERA.htm", "Electronic Services Help (ECSHELP)"],
        },
        {
            "id": "accounting_money",
            "label": "Accounting & Period Money",
            "summary": "Daysheet, Registers, Aging, Trans for a Period, Deposit Slip, Credit Card Settlement.",
            "helpHints": ["Accounting Reports", "AcctRp.htm"],
            "nr2Priority": "period_close_truth",
        },
        {
            "id": "practice_management",
            "label": "Practice Management Analytics",
            "summary": "Production, collections, receivables, treatment plans, referrals, hygiene, forecasts.",
            "helpHints": ["Practice Management Reports", "HnPMR.htm"],
        },
        {
            "id": "clinical_charting",
            "label": "Clinical Charting & Treatment Planning",
            "summary": "Charting, treatment plans, clinical documentation (often paired with imaging).",
            "helpHints": ["Treatment Plan reports", "Charting Help topics in TOC"],
        },
        {
            "id": "imaging",
            "label": "Imaging / CS Imaging",
            "summary": "Imaging Launcher / CS Imaging integration alongside SoftDent PMS.",
            "helpHints": ["Imaging Launcher", "acquire image topics"],
        },
        {
            "id": "rx_labs",
            "label": "Rx / Pharmacies / Labs",
            "summary": "ePrescriptions, pharmacy lists, lab cases.",
            "helpHints": ["Rx/Pharmacies/Labs reports", "Lab Case"],
        },
        {
            "id": "security_utilities",
            "label": "Security, Backup & Utilities",
            "summary": "Sign On / Change Login, audit trail, backup, year-end, software update (-sus).",
            "helpHints": ["Audit Trail", "Backing Up Data", "End of Year Procedures"],
        },
        {
            "id": "integrations",
            "label": "Sensei / DataSync / Bridge integrations",
            "summary": "Sensei DataSync and SoftDentBridge exports feed NR2 ops detail — not period $ truth.",
            "helpHints": ["DataSync", "SoftDentBridge exports"],
        },
    ]

    office_doctrine = {
        "practiceBuild": "CS SoftDent Software v19.1.4 (desktop Win32)",
        "launch": "CS SoftDent Software.lnk with -sus (never bare SDWIN.EXE)",
        "signOn": {"user": "COMPUTE", "passwordEnv": "SOFTDENT_SIGNON_PASSWORD", "passwordCase": "lowercase"},
        "outputOptions": ["Excel", "Print Preview"],
        "never": ["Printer", "Esc on SoftDent main", "Alt+R for Reports (AMD Instant Replay)", "invented SoftDent dollars"],
        "excelLandPath": r"C:\SoftDentReportExports",
        "periodCloseTruth": "desktop SoftDent Excel exports",
        "opsDetailLane": "Sensei / sd_* / ODBC when populated — do not override desktop Register $",
        "localHelpChm": r"C:\SoftDent\WinHelp\SoftDent_OnlineHelp_OH_DE1010.chm",
        "localHelpExtract": str(help_root),
        "electronicServicesHelp": r"C:\SoftDent\ECSHELP.hlp",
        "onlineHelpPortal": HELP_BASE_URL + "Using_Online_Help.htm",
        "supportPortal": "https://gosensei.com/softdent-support/",
    }

    topic_bodies, how_pages = ingest_help_topic_bodies(help_root)
    how_softdent_works = build_how_softdent_works(how_pages, office_doctrine)

    kb = {
        "version": 2,
        "built": str(date.today()),
        "title": "SoftDent full product knowledge base (this office + Carestream Help)",
        "honesty": (
            "Encodes SoftDent Online Help (OH_DE1010 CHM) inside-out for HAL: full TOC, "
            "thirteen report categories with descriptions, searchable Help topic bodies "
            f"({len(topic_bodies)} pages), and howSoftDentWorks lifecycle + core articles. "
            "Never invent SoftDent dollar amounts. Full product knowledge ≠ full GUI automation."
        ),
        "officeDoctrine": office_doctrine,
        "howSoftDentWorks": how_softdent_works,
        "topicBodiesFile": "softdent_product_kb_topics.json",
        "topicBodyCount": len(topic_bodies),
        "productModules": product_modules,
        "helpToc": {
            "source": "SoftDent_OnlineHelp_OH_DE1010.hhc",
            "entryCount": len(toc),
            "topLevelBooks": books,
            "entries": [
                {
                    "name": e["name"],
                    "local": e["local"],
                    "depth": e["depth"],
                    "helpUrl": (HELP_BASE_URL + e["local"].split("/")[-1]) if e["local"] else None,
                }
                for e in toc
            ],
        },
        "gettingStartedTopics": modules,
        "keystrokes": keystrokes,
        "reportCatalog": {
            "categories": report_categories,
            "allReports": all_reports,
            "reportCountParsed": len(all_reports),
            "endOfDayRecommended": eod_reports,
        },
        "nr2Automation": {
            "guiExportIds": gui_ids,
            "guiIdHints": NR2_GUI_MAP,
            "masterOrder": list((nr2_auto.get("masterReports") or {}).get("masterOrder") or []),
            "phase1Order": list((nr2_auto.get("guiMenuMap") or {}).get("phase1_order") or []),
            "phase2Reserved": list((nr2_auto.get("guiMenuMap") or {}).get("phase2_reserved") or []),
        },
        "electronicServices": {
            "localCnt": r"C:\SoftDent\ECSHELP.cnt",
            "topics": [
                "Claim Validation Error Codes",
                "Special Payer Error Codes & Requirements",
                "ES Program Options",
                "ES Report Descriptions",
                "Payer List",
                "FAQ / Troubleshooting Internet Transfer",
            ],
        },
        "helpUrlBase": HELP_BASE_URL,
        "_topicBodies": topic_bodies,
    }
    return kb


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--help-root", type=Path, default=DEFAULT_HELP_ROOT)
    ap.add_argument("--out", type=Path, default=OUT_PATH)
    ap.add_argument("--topics-out", type=Path, default=TOPICS_OUT_PATH)
    args = ap.parse_args()
    if not args.help_root.is_dir():
        print(f"Help extract missing: {args.help_root}", file=sys.stderr)
        print("Decompile SoftDent_OnlineHelp_OH_DE1010.chm first.", file=sys.stderr)
        return 2
    kb = build_kb(args.help_root, NR2)
    topic_bodies = list(kb.pop("_topicBodies", []) or [])
    args.out.write_text(json.dumps(kb, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    topics_payload = {
        "version": 2,
        "built": kb.get("built"),
        "source": "SoftDent_OnlineHelp_OH_DE1010.chm",
        "topicCount": len(topic_bodies),
        "topics": topic_bodies,
    }
    args.topics_out.write_text(
        json.dumps(topics_payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    cats = kb["reportCatalog"]["categories"]
    parsed = kb["reportCatalog"]["reportCountParsed"]
    toc_n = kb["helpToc"]["entryCount"]
    print(f"Wrote {args.out} ({args.out.stat().st_size} bytes)")
    print(f"Wrote {args.topics_out} ({args.topics_out.stat().st_size} bytes)")
    print(f"TOC entries: {toc_n}; report rows: {parsed}; topic bodies: {len(topic_bodies)}")
    print(f"howSoftDentWorks core articles: {len((kb.get('howSoftDentWorks') or {}).get('coreHelpArticles') or {})}")
    for name in [
        "Accounting",
        "Practice Management",
        "Patient",
        "Account",
        "Insurance",
        "Recall/Appt",
    ]:
        meta = cats.get(name) or {}
        print(f"  {name}: {meta.get('reportCount', 0)} reports (present={meta.get('sourceFilePresent')})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
