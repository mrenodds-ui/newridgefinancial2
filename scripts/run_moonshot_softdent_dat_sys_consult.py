"""Moonshot AI — Can SoftDent data be read from C:\\softdent via *.dat + system.sys?

Operator request passed VERBATIM. CONSULT / REPORT ONLY — do not apply code.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / ".local_logs" / "moonshot_financial_eval"
DOCS = REPO / "NewRidgeFinancial2" / "docs"
OUT.mkdir(parents=True, exist_ok=True)
DOCS.mkdir(parents=True, exist_ok=True)
DATE = datetime.now(timezone.utc).strftime("%Y-%m-%d")

HELPER = (
    REPO
    / "_archive"
    / "2026-07-10"
    / ".local_logs"
    / "moonshot_financial_eval"
    / "_run_moonshot_eval.py"
)
sys.path.insert(0, str(HELPER.parent))
from _run_moonshot_eval import extract_message_content, resolve_api_and_endpoint  # noqa: E402

OPERATOR_REQUEST_VERBATIM = """
ask moonshot ai if he can get softdent data from C:\\softdent folder using *.dat and system.sys and report
""".strip()

SYSTEM = """You are Moonshot AI (kimi-k2 class) — SoftDent / Carestream data-integration engineer
for NewRidge Financial 2.0 (NR2).

CRITICAL QUESTION:
Can SoftDent practice data be retrieved DIRECTLY from C:\\softdent using *.dat files
and system.sys? Answer honestly with YES / PARTIAL / NO, then explain how (or why not),
risks, and what NR2 should do instead.

Use LIVE FACTS in the user context as ground truth. Do not invent that system.sys exists
if LIVE FACTS say it is missing. Do not invent a public SoftDent .dat schema.

Cover:
(A) What C:\\softdent *.dat / *.idx / *.sys files actually are (engine family: Btrieve /
    Pervasive / Actian Zen / FairCom c-tree / proprietary SoftDent ISAM — pick based on
    evidence, mark uncertainty).
(B) Role of system.sys vs softdent.sys vs FILE.DDF / FIELD.DDF / INDEX.DDF catalogs.
(C) Feasibility of reading live .dat files from Python/ODBC/Btrieve API without SoftDent UI.
(D) Safety: live locks, corruption risk, PHI, vendor license, concurrent SoftDent users.
(E) Comparison vs NR2's working lanes (SoftDentFinancialExports JSONL, Sensei DataSync,
    report exports, optional SQL ODBC).
(F) If PARTIAL/YES: concrete read-only approach ranked MUST/SHOULD/NICE.
(G) If NO: clear alternatives to get the same data (including transactions).

CONSULT ONLY — report findings. Paste-ready exploratory probes OK; do not claim you
applied production code. Never invent dollar amounts or patient rows.

OUTPUT FORMAT (strict markdown):
# Verdict (YES | PARTIAL | NO)
## 0. Operator Intent (quote verbatim)
## 1. What C:\\softdent Contains (engine + file roles)
## 2. system.sys Reality Check
## 3. Can We Read *.dat Directly? (feasibility + blockers)
## 4. Safe Approaches Ranked (best → worst)
## 5. Recommendation for NR2
## 6. Risks / PHI / Rollback
## 7. Operator Next Actions
"""


def build_context() -> str:
    return """
### LIVE FACTS — C:\\softdent inventory (captured 2026-07-10)

**Path exists:** `C:\\softdent` is a live SoftDent install root (Carestream SoftDent / PracticeWorks family).

**system.sys:** **NOT FOUND** at `C:\\softdent\\system.sys` (any case). No FILE.DDF / FIELD.DDF / INDEX.DDF found at install root.

**Related .sys present:**
- `softdent.sys` (2,870 bytes, modified 2026-07-10) — small binary/config-ish blob; printable strings include corporation/recall boilerplate, NOT a Btrieve system catalog of tables.

**Top-level *.dat count:** **166** `.dat` files in `C:\\softdent` (plus matching `.idx` companions for many).

**Largest / most relevant .dat (size, mtime):**
| File | Size | LastWrite |
|------|------|-----------|
| unlimtxt.dat | ~418 MB | 2026-07-10 | clinical/unlimited text |
| medhist.dat | ~281 MB | 2026-07-09 | medical history |
| **trans.dat** | **~258 MB** | 2026-07-09 | **transactions** |
| images.dat | ~252 MB | 2026-07-09 | images |
| pnotes.dat | ~139 MB | 2026-07-10 | patient notes |
| appts.dat | ~126 MB | 2026-07-09 | appointments |
| account.dat | ~23 MB | 2026-07-09 | accounts |
| patient.dat | ~23 MB | 2026-07-09 | patients |
| dentist.dat | ~50 KB | 2026-07-08 | providers |
| ada.dat / adafee.dat | ~0.9 / 0.5 MB | 2026-07-08 | ADA / fees |
| audit_trans.dat, audit_security.dat, etc. | various | live |

Also present: `SoftDent_DatabaseSet\\*.bak` (PracticeWorks/SoftDentMFC backups), `PWSvr\\`, `VXDATA\\`, `DataSync\\`, `tranlogs\\`, `exports\\`, `SDReports\\`.

**Binary headers (first bytes):** proprietary binary — not SQLite, not CSV, not JSON. Example `trans.dat` starts `7da82210...` with embedded record-size-like fields; paired `trans.idx` (~84 MB) present. Files look like classic SoftDent ISAM/Btrieve-style data+index pairs.

**NR2 current working lanes (already live):**
1. `C:\\SoftDentFinancialExports` JSONL (daysheet, transactions_for_period, register, aging) → analytics SQLite
2. Sensei Gateway DataSync JSON → `sd_patients` / `sd_appointments` / `sd_procedures` (thousands of rows)
3. SoftDent report CSV exports → import inbox
4. Optional SQL ODBC lane exists in code but DSN historically unset
5. Explicit ops policy: `softdent_database_export_ingest.py` says it does **NOT** parse live `.dat`/`.idx` files

**Prior NR2 diagnostics stance:** Direct flat-file ingestion is a *candidate only* until vendor-supported read-only access + table mappings confirmed; active pipeline is report exports → analytics SQLite.

**Build:** hal-10370 (transaction JSONL extract already applied).

### Operator ask
Answer whether Moonshot can get SoftDent data from C:\\softdent using *.dat and system.sys — and report findings.
"""


def main() -> int:
    key_name, api_key, base_url = resolve_api_and_endpoint()
    if not api_key:
        print("No Moonshot/OpenRouter API key.", file=sys.stderr)
        return 1

    if "moonshot" in (base_url or "").lower():
        model = str(os.getenv("MOONSHOT_MODEL") or "kimi-k2.5").strip()
    else:
        model = str(
            os.getenv("MOONSHOT_MODEL") or os.getenv("KIMI_K2_MODEL") or "moonshotai/kimi-k2"
        ).strip()

    print(f"Using {key_name} @ {base_url} model={model}")
    user = (
        "OPERATOR REQUEST (VERBATIM — do not rewrite):\n\n"
        f"{OPERATOR_REQUEST_VERBATIM}\n\n"
        "CONSULT / REPORT ONLY. Answer YES / PARTIAL / NO with evidence from LIVE FACTS.\n\n"
        "## Context\n\n"
        + build_context()
    )

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
        ],
        "temperature": 1.0,
        "max_tokens": 12000,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    if "openrouter" in base_url.lower():
        headers["HTTP-Referer"] = "https://github.com/NewRidgeFamilyFinancial"
        headers["X-Title"] = "NR2 SoftDent DAT/system.sys Feasibility"

    print("Calling Moonshot AI (DAT/system.sys feasibility report)...")
    req = urllib.request.Request(
        base_url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=3600) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        content = extract_message_content(body)
        status = "ok"
    except urllib.error.HTTPError as exc:
        content = f"HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')[:4000]}"
        status = f"HTTP {exc.code}"
    except Exception as exc:
        content = str(exc)
        status = "error"

    header = (
        f"# Moonshot AI — SoftDent C:\\softdent *.dat + system.sys Feasibility\n\n"
        f"**Date:** {DATE}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Endpoint:** {base_url}  \n"
        f"**Status:** {status}  \n"
        f"**Build reviewed:** hal-10370  \n"
        f"**Script:** `scripts/run_moonshot_softdent_dat_sys_consult.py`  \n"
        f"**Apply:** Report only.\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    full = header + (content or "(empty)")
    out_file = OUT / f"MOONSHOT_SOFTDENT_DAT_SYS_CONSULT_{DATE}.md"
    doc_file = DOCS / f"MOONSHOT_SOFTDENT_DAT_SYS_CONSULT_{DATE}.md"
    out_file.write_text(full, encoding="utf-8")
    doc_file.write_text(full, encoding="utf-8")
    print(out_file)
    print(doc_file)
    print(f"chars={len(content or '')} status={status}")
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
