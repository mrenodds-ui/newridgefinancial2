"""Moonshot AI — New Ridge Family Dental website professional redesign.

CONSULT ONLY for design recommendations. Live edit requires operator WordPress login.
Site: https://www.renodentalcare.org/ (PBHS WordPress — not classic RevenueWell CMS).
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
can you interact with revenuewell via ui to have moonshot ai look at my website and update it to highly professional website page?
my website is www.renodentalcare.org. i want both
""".strip()

SYSTEM = """You are Moonshot AI (kimi-k2 class) — dental practice brand/UX architect for
New Ridge Family Dental (Dr. Michael Reno, Wichita KS S-corp). The operator wants a
HIGHLY PROFESSIONAL public website redesign for https://www.renodentalcare.org/

CRITICAL FACTS:
1. Live site footer: "Family Dentistry Website Design by PBHS © 2026"
2. Admin is WordPress login at /admin → wp-login.php (PBHS WordPress), NOT classic
   RevenueWell drag-drop CMS. Operator said "RevenueWell" but platform evidence = PBHS/WP.
3. CONSULT FIRST — produce a professional redesign plan. Editing happens after approval
   via WordPress/PBHS admin UI (operator must log in).
4. Do NOT invent clinical claims, reviews, awards, or insurance acceptance not on the site.
5. Ground in LIVE FACTS below. Prefer denser, calmer, brand-first patient conversion UX.
6. Rank MUST / SHOULD / NICE. Wireframe homepage first viewport. Paste-ready copy where useful.
7. Call out what to KEEP (strong photos, phone, address, hours, Dr. Reno) vs REMOVE/MERGE.

OUTPUT FORMAT (strict markdown):
# Verdict
## 0. Operator Intent + Platform Reality (PBHS/WordPress vs RevenueWell)
## 1. Critique of Current Site (why it feels less professional)
## 2. Recommended Professional Design Direction (primary)
Brand, typography, color, hero, density, CTA hierarchy.
## 3. Homepage Wireframe (text) — first viewport + below-fold
## 4. Information Architecture — nav cleanup
## 5. Copy Spec (CONSULT) — hero, CTAs, section headlines
## 6. Page-by-Page Priority List
## 7. RevenueWell / PBHS Edit Feasibility
What can be done in WP admin vs needs PBHS/theme support.
## 8. Phases + Validation Gate
## 9. Risks & Rollback
DO NOT invent reviews/awards. CONSULT ONLY until operator approves edits.
"""

LIVE_FACTS = """
### LIVE SITE FACTS (captured 2026-07-10)
URL: https://www.renodentalcare.org/
Title: Wichita Family Dentist | New Ridge Family Dental | Dr. Michael Reno
Designer footer: Family Dentistry Website Design by PBHS © 2026
Admin: https://www.renodentalcare.org/admin → WordPress login (Email/Password)

Practice:
- New Ridge Family Dental
- Dr. Michael Reno, DDS
- 2135 North Ridge Rd Ste 700, Wichita, KS 67212
- Phone: (316) 722-6060
- Hours: Monday–Thursday, 7:00 AM–4:00 PM
- Serves: Andover, Cheney, Goddard, Maize, Haysville, Derby, Newton, Colwich KS

Homepage structure observed:
1. TOP mega-link bar: ~30+ SEO/utility links (Financing, FAQ, Orthodontics, Portal,
   Testimonials, Pricing, Referral, Special Offers, AI Radiographs, Videos, etc.)
2. Secondary nav: Home | Services | New Patients | Insurance & Payment | About | Contact
   + Request Appointment + phone
3. Hero: 4-panel office photo collage; brand "NEW RIDGE FAMILY DENTAL";
   H1 "Comfort-Focused Dentistry for Wichita Families";
   CTAs: Call Our Office | Request Appointment
4. Icon strip: PATIENT REGISTRATION | TEETH CLEANING & DENTAL CHECKUPS | FINANCIAL AGREEMENT POLICY
   (Financial Agreement Policy as a top-3 homepage destination feels unprofessional/ops-heavy)
5. Mid-page: "Professional care with clear next steps…" + OPEN PATIENT PORTAL / REQUEST APPOINTMENT
   (blue buttons with low-contrast copper text noted)
6. Action cards: Portal / Scheduling / Insurance; New/Returning/Urgent guidance
7. Videos: Dental Insurance, First Visit, Crowns
8. Legacy blocks: Periodontal Maintenance, Cosmetic Dentistry, Office Photos, Meet the Doctor
9. Review carousel with odd labels e.g. "READ MORE REVIEWS ABOUT MISSED APPOINTMENT POLICY"
10. Popup: "No Insurance? Perfect! … In-House Membership Plan"
11. Accessibility widget present

Services page: Preventive / Restorative / Cosmetic / Urgent & Comfort — clean enough.

Operator pain: wants HIGHLY PROFESSIONAL website; asked for RevenueWell UI edit + Moonshot
look. Reality: PBHS WordPress — edit via WP admin after login.

CONSULT ONLY — recommend professional redesign; do not invent content.
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
        "CONSULT ONLY — highly professional website redesign recommendations.\n\n"
        "## Context\n\n"
        + LIVE_FACTS
    )
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
        ],
        "temperature": 1.0,
        "max_tokens": 14000,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    if "openrouter" in base_url.lower():
        headers["HTTP-Referer"] = "https://github.com/NewRidgeFamilyFinancial"
        headers["X-Title"] = "NR2 Website Professional Redesign Consult"

    print("Calling Moonshot AI (website consult)...")
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
        f"# Moonshot AI — New Ridge Website Professional Redesign (CONSULT)\n\n"
        f"**Date:** {DATE}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Endpoint:** {base_url}  \n"
        f"**Status:** {status}  \n"
        f"**Site:** https://www.renodentalcare.org/  \n"
        f"**Platform:** PBHS WordPress (admin `/admin`)  \n"
        f"**Script:** `scripts/run_moonshot_website_pro_redesign_consult.py`  \n"
        f"**Apply:** DO NOT EDIT LIVE until operator approves + logs into WP admin.\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    full = header + (content or "(empty)")
    out_file = OUT / f"MOONSHOT_WEBSITE_PRO_REDESIGN_CONSULT_{DATE}.md"
    doc_file = DOCS / f"MOONSHOT_WEBSITE_PRO_REDESIGN_CONSULT_{DATE}.md"
    out_file.write_text(full, encoding="utf-8")
    doc_file.write_text(full, encoding="utf-8")
    print(out_file)
    print(doc_file)
    print(f"chars={len(content or '')} status={status}")
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
