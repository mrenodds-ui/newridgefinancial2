"""Moonshot AI — scan this workstation for assets that would help NR2 (REPORT).

Operator: have moonshot ai look at my entire computer and see if anything
would help this program - report
"""

from __future__ import annotations

import json
import os
import re
import ssl
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(r"C:\Users\mreno\newridgefamilyfinancial")
if not REPO.is_dir():
    REPO = Path(__file__).resolve().parents[1]

OUT = REPO / ".local_logs" / "moonshot_financial_eval"
DOCS = REPO / "NewRidgeFinancial2" / "docs"
NR2 = REPO / "NewRidgeFinancial2"
OUT.mkdir(parents=True, exist_ok=True)
DOCS.mkdir(parents=True, exist_ok=True)
DATE = datetime.now(timezone.utc).strftime("%Y-%m-%d")

CTX = ssl._create_unverified_context()
BASE = os.getenv("NR2_BROWSER", "https://127.0.0.1:8765").rstrip("/")

INV = OUT / "machine_inventory_for_moonshot.json"
INV_EXTRA = OUT / "machine_inventory_extra.json"

OPERATOR_REQUEST_VERBATIM = (
    "have moonshot ai look at my entire computer and see if anything would "
    "help this program - report"
)

SYSTEM = """You are Moonshot AI (kimi-k2 class) — principal systems architect for
NewRidgeFinancial2 (NR2) on this dental-practice Windows workstation.

CONSULT / REPORT ONLY — DO NOT APPLY CODE. DO NOT invent dollar amounts.
empty ≠ $0. SoftDent: desktop GUI Excel/Preview exports preferred for period-close;
NO silent SoftDent write-back. QuickBooks: READ + consent journal only.
PHI stays local. Cite ONLY paths present in LIVE MACHINE INVENTORY.

Operator (verbatim):
> have moonshot ai look at my entire computer and see if anything would help
> this program - report

Your job: Given a LIVE host inventory (paths, installed apps, running processes,
scheduled tasks, ODBC, Ollama models, export folders, alternate drives, SoftDent
SideNotes package, Sensei DataSync, backups), decide what already on THIS
computer would materially help NR2 — and what to ignore.

Rank recommendations MUST / SHOULD / NICE / IGNORE.
Prefer wiring EXISTING host assets over inventing new vendors.
Call out stale data / dead schedules / duplicate repo copies / backup traps.
If an asset is present but unused by NR2, say exactly how to use it (file/API),
or say "leave alone".

HARD PRODUCT DOCTRINE (do not contradict):
- SoftDent launch policy: prefer Start Menu **CS SoftDent Software.lnk** (ops may
  require -sus); never bare SDWIN as the documented ops path even if observed.
- SoftDent Output Options: Excel or Print Preview only — never Printer.
- Direct C:\\softdent *.dat parsing remains non-default (prior consult); prefer
  report exports → C:\\SoftDentReportExports / C:\\SoftDentFinancialExports.
- Optical program face is nr2-optical-*; do not recommend restoring legacy Apex SPA.
- Repo canonical root is C:\\Users\\mreno\\newridgefamilyfinancial — treat other
  drive copies (D:/E:/F:) as backups/archives unless inventory proves otherwise.

OUTPUT (strict markdown):
# Verdict — what on this computer helps NR2 most
## 0. Operator Intent (verbatim)
## 1. Host snapshot (what is actually here that matters)
## 2. Top opportunities ranked (MUST / SHOULD / NICE) — each with: asset path,
   how it helps NR2, concrete next step, risk
## 3. Already wired / leave alone (so we do not thrash)
## 4. Stale / risky / ignore (duplicate repos, old diagnostics, backup traps)
## 5. SoftDent + QB + Sensei + SideNotes + OCR + SQL Express matrix
## 6. Scheduled-task posture (enable / audit / leave)
## 7. Executive Summary (7 bullets)
## 8. Approval Checklist
DO NOT APPLY CODE. No fake $. No invented paths.
"""


def _load_dotenv() -> None:
    for path in (REPO / ".env", NR2 / ".env"):
        if not path.is_file():
            continue
        try:
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                name, _, val = line.partition("=")
                name = name.strip()
                val = val.strip().strip("'").strip('"')
                if name and val and not os.getenv(name):
                    os.environ[name] = val
        except OSError:
            pass


def resolve_api_and_endpoint() -> tuple[str, str, str]:
    _load_dotenv()
    candidates = (
        ("MOONSHOT_API_KEY", os.getenv("MOONSHOT_API_KEY", "").strip()),
        ("OPENROUTER_API_KEY", os.getenv("OPENROUTER_API_KEY", "").strip()),
        ("KIMI_K2_API_KEY", os.getenv("KIMI_K2_API_KEY", "").strip()),
    )
    key_name, api_key = "", ""
    for name, val in candidates:
        if val and len(val) >= 20:
            key_name, api_key = name, val
            break
    if not api_key:
        for name, val in candidates:
            if val:
                key_name, api_key = name, val
                break
    base = (
        os.getenv("MOONSHOT_API_BASE") or os.getenv("KIMI_K2_BASE_URL") or ""
    ).strip()
    if not base:
        if key_name == "MOONSHOT_API_KEY" or (api_key or "").startswith("sk-nv"):
            base = "https://api.moonshot.ai/v1/chat/completions"
        else:
            base = "https://openrouter.ai/api/v1/chat/completions"
    if not base.endswith("/chat/completions"):
        base = base.rstrip("/") + "/chat/completions"
    return key_name, api_key, base


def extract_message_content(raw: dict) -> str:
    try:
        choices = raw.get("choices") or []
        if not choices:
            return ""
        msg = (choices[0] or {}).get("message") or {}
        content = msg.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    parts.append(str(block.get("text") or ""))
                elif isinstance(block, str):
                    parts.append(block)
            return "\n".join(p for p in parts if p)
        return str(content or "")
    except Exception:
        return ""


_SECRET_KEYS = re.compile(
    r"(token|secret|password|api[_-]?key|authorization|hubToken|csrf|session)",
    re.I,
)


def _sanitize(obj):
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if _SECRET_KEYS.search(str(k)):
                out[k] = "[REDACTED]"
            else:
                out[k] = _sanitize(v)
        return out
    if isinstance(obj, list):
        return [_sanitize(x) for x in obj]
    if isinstance(obj, str) and len(obj) > 80 and re.fullmatch(r"[A-Za-z0-9_\-]{40,}", obj):
        return "[REDACTED_LIKELY_TOKEN]"
    return obj


def get_json(path: str, timeout: int = 45):
    try:
        with urllib.request.urlopen(BASE + path, context=CTX, timeout=timeout) as r:
            return _sanitize(json.loads(r.read().decode("utf-8", "replace")))
    except Exception as e:  # noqa: BLE001
        return {"error": type(e).__name__, "msg": str(e)[:240]}


def _load_json(path: Path) -> dict:
    if not path.is_file():
        return {"missing": True, "path": str(path)}
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc), "path": str(path)}


def _shrink_inventory(inv: dict) -> dict:
    """Keep Moonshot prompt under control while preserving decision-critical fields."""
    if not isinstance(inv, dict) or inv.get("missing"):
        return inv
    path_snaps = inv.get("pathSnaps") or {}
    keep_paths = [
        r"C:\softdent",
        r"C:\SoftDent",
        r"C:\SoftDent\PWImages",
        r"C:\SoftDentReportExports",
        r"C:\SoftDentFinancialExports",
        r"C:\SoftDentFinancialExports\softdent_financial_analytics.db",
        r"C:\Users\mreno\newridgefamilyfinancial",
        r"C:\Users\mreno\newridgefamilyfinancial\app_data\nr2\document_inbox",
        r"C:\Users\mreno\AppData\Local\Programs\Ollama",
        r"C:\Users\mreno\.ollama",
        r"C:\Program Files (x86)\Intuit",
        r"C:\Program Files\Intuit",
    ]
    slim_paths = {}
    for p in keep_paths:
        if p in path_snaps:
            snap = dict(path_snaps[p])
            # Drop huge name lists if present
            if isinstance(snap.get("subdirs"), list) and len(snap["subdirs"]) > 40:
                snap["subdirs"] = snap["subdirs"][:40]
                snap["subdirsTruncated"] = True
            slim_paths[p] = snap

    apps = inv.get("installedAppsOfInterest") or []
    app_names = sorted(
        {
            str(a.get("name") or "")
            for a in apps
            if isinstance(a, dict) and a.get("name")
        }
    )

    procs = inv.get("runningProcessesOfInterest") or []
    proc_names = sorted(
        {
            str(p.get("name") or "")
            for p in procs
            if isinstance(p, dict) and p.get("name")
        }
    )

    return {
        "scannedAtUtc": inv.get("scannedAtUtc"),
        "computerName": inv.get("computerName"),
        "disks": inv.get("disks"),
        "mappedDrives": inv.get("mappedDrives"),
        "toolsOnPath": inv.get("toolsOnPath"),
        "ollamaModels": inv.get("ollamaModels"),
        "odbcUserDsns": inv.get("odbcUserDsns"),
        "odbcSystemDsns": inv.get("odbcSystemDsns"),
        "odbcSystemDsnsWow64": inv.get("odbcSystemDsnsWow64"),
        "scheduledTasksOfInterest": inv.get("scheduledTasksOfInterest"),
        "softdentShortcuts": inv.get("softdentShortcuts"),
        "startMenuHits": inv.get("startMenuHits"),
        "desktopHits": inv.get("desktopHits"),
        "downloadsHits": inv.get("downloadsHits"),
        "documentsHits": inv.get("documentsHits"),
        "installedAppNames": app_names,
        "runningProcessNames": proc_names,
        "pathSnapsKey": slim_paths,
        "inboxTreeHead": (inv.get("inboxTree") or [])[:40],
        "reportExportsNote": (
            "See pathSnapsKey[C:\\SoftDentReportExports] newestFiles/topExtensions"
        ),
        "financialExportsNote": (
            "See pathSnapsKey[C:\\SoftDentFinancialExports]; analytics.db ~177MB live"
        ),
    }


def build_audit() -> dict:
    build = {}
    try:
        build = json.loads((NR2 / "nr2-build.json").read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        build = {"error": str(exc)}

    inv = _shrink_inventory(_load_json(INV))
    extra = _load_json(INV_EXTRA)

    # Trim extra SideNotes / DataSync noise
    if isinstance(extra, dict) and not extra.get("missing"):
        for k in list(extra.keys()):
            if isinstance(extra[k], dict) and "names" in extra[k]:
                names = extra[k].get("names") or []
                if len(names) > 30:
                    extra[k] = {
                        **extra[k],
                        "names": names[:30],
                        "namesTruncated": True,
                    }

    return {
        "repoRoot": str(REPO),
        "operatorAsk": OPERATOR_REQUEST_VERBATIM,
        "build": build,
        "base": BASE,
        "liveApis": {
            "appInfo": get_json("/api/app-info", 20),
            "halStatus": get_json("/api/apex/hal/status", 30),
            "importReadiness": get_json("/api/import-readiness", 45),
            "browserSession": get_json("/api/browser-session", 20),
        },
        "machineInventory": inv,
        "machineInventoryExtra": extra,
        "operatorDoctrineReminders": [
            "Canonical repo: C:\\Users\\mreno\\newridgefamilyfinancial",
            "SoftDent GUI Excel/Preview only; export folder C:\\SoftDentReportExports",
            "Analytics/inbox also under C:\\SoftDentFinancialExports + app_data\\nr2",
            "Do not recommend parsing live SoftDent .dat as default lane",
            "Do not recommend restoring legacy Apex SPA",
        ],
    }


def main() -> int:
    key_name, api_key, base_url = resolve_api_and_endpoint()
    if not api_key:
        blocker = DOCS / f"MOONSHOT_WHOLE_COMPUTER_HELP_BLOCKED_{DATE}.md"
        blocker.write_text(
            "# Moonshot AI — whole computer help (BLOCKED)\n\n"
            f"**Date:** {DATE}\n"
            "**Status:** no API key\n\n"
            f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
            "Set MOONSHOT_API_KEY / OPENROUTER_API_KEY and rerun:\n"
            f"`python {REPO / 'scripts' / 'run_moonshot_whole_computer_help_consult.py'}`\n",
            encoding="utf-8",
        )
        print("No API key", file=sys.stderr)
        print("Wrote", blocker)
        return 1

    if (api_key or "").startswith("sk-nv") or "moonshot.ai" in (base_url or "").lower():
        model = str(os.getenv("MOONSHOT_MODEL") or "kimi-k2.5").strip()
    else:
        model = str(
            os.getenv("MOONSHOT_MODEL")
            or os.getenv("KIMI_K2_MODEL")
            or "moonshotai/kimi-k2.5"
        ).strip()

    print(f"Using {key_name} @ {base_url} model={model}", flush=True)
    if not INV.is_file():
        print(f"Missing inventory file: {INV}", file=sys.stderr)
        print("Run the PowerShell machine scan first.", file=sys.stderr)
        return 1

    audit = build_audit()
    print("Audit built.", flush=True)

    user = (
        f"OPERATOR REQUEST (verbatim):\n{OPERATOR_REQUEST_VERBATIM}\n\n"
        "LIVE MACHINE INVENTORY + NR2 STATUS (sanitized JSON). "
        "Treat this as ground truth for what exists on the computer.\n\n"
        f"```json\n{json.dumps(audit, indent=2, default=str)[:90000]}\n```\n\n"
        "Return markdown only. CONSULT / REPORT ONLY. "
        "Rank what on THIS computer helps NR2. Real paths only."
    )

    body = {
        "model": model,
        "temperature": 1 if "moonshot" in (base_url or "").lower() else 0.25,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
        ],
        "max_tokens": 14000,
    }
    url = base_url.rstrip("/")
    if not url.endswith("/chat/completions"):
        url = url + "/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if "openrouter" in url.lower():
        headers["HTTP-Referer"] = "https://github.com/NewRidgeFamilyFinancial"
        headers["X-Title"] = "NR2 Whole Computer Help Consult"

    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=900) as resp:
            raw = json.loads(resp.read().decode("utf-8", "replace"))
        text = extract_message_content(raw) or ""
        status = "ok"
    except Exception as exc:  # noqa: BLE001
        print(f"Moonshot call failed: {exc}", file=sys.stderr)
        raw = {"error": str(exc)}
        text = f"Moonshot call failed: {exc}"
        status = "error"

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    raw_path = OUT / f"moonshot_whole_computer_help_{stamp}.json"
    audit_path = OUT / f"moonshot_whole_computer_help_audit_{stamp}.json"
    md_path = DOCS / f"MOONSHOT_WHOLE_COMPUTER_HELP_CONSULT_{DATE}.md"
    out_copy = OUT / f"MOONSHOT_WHOLE_COMPUTER_HELP_CONSULT_{DATE}.md"

    raw_path.write_text(json.dumps(raw, indent=2)[:500000], encoding="utf-8")
    audit_path.write_text(
        json.dumps(audit, indent=2, default=str)[:400000], encoding="utf-8"
    )

    header = (
        f"# Moonshot AI — whole computer help for NR2 (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}\n"
        f"**Model:** `{model}`\n"
        f"**Key:** {key_name}\n"
        f"**Endpoint:** {url}\n"
        f"**Status:** {status}\n"
        f"**Build:** `{audit.get('build', {}).get('BUILD_ID', '?')}`\n"
        f"**Repo root:** `{REPO}`\n"
        f"**Inventory:** `.local_logs/moonshot_financial_eval/machine_inventory_for_moonshot.json`\n"
        f"**Script:** `scripts/run_moonshot_whole_computer_help_consult.py`\n"
        f"**Apply:** DO NOT APPLY until operator approves.\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    doc = header + (text.strip() or "_(empty Moonshot response)_") + "\n"
    md_path.write_text(doc, encoding="utf-8")
    out_copy.write_text(doc, encoding="utf-8")
    print("Wrote", md_path)
    print("Status", status, "chars", len(text))
    return 0 if status == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
