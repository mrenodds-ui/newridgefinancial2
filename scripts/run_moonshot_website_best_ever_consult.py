"""Moonshot AI — Full-site evaluation: best dental office website ever.

CONSULT ONLY. Site: https://www.renodentalcare.org/ (PBHS WordPress).
Evaluates all pages + post-redesign state; recommends what it takes to be
best-in-class. No live edits until operator approves.
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
ask moonshot ai to evaluate my website with all the page and ask what can be done to macke it the best dental office website EVER!
""".strip()

SYSTEM = """You are Moonshot AI (kimi-k2 class) — elite dental practice brand, UX,
conversion, SEO, and patient-experience architect for New Ridge Family Dental
(Dr. Michael Reno, DDS — Wichita, KS).

MISSION: Evaluate the FULL public website (all pages) and prescribe what it takes
to make https://www.renodentalcare.org/ the BEST dental office website EVER —
not merely "better than average." Be ambitious AND practical.

CRITICAL RULES:
1. CONSULT ONLY — recommendations, specs, phases. Do NOT claim you edited the live site.
2. Ground every critique in LIVE FACTS + PAGE INVENTORY below. Do not invent reviews,
   awards, insurance panels, clinical outcomes, or credentials not provided.
3. Account for platform reality: PBHS WordPress Template2120; layoutAccess often false;
   temporary CSS overrides already live via page-content <style id="nr-pro-sitewide">.
4. Separate: (A) already improved this session, (B) still broken/weak, (C) world-class
   upgrades that require PBHS, new content, photography, or rebuild.
5. Rank MUST / SHOULD / NICE. Include conversion, trust, IA, copy, visual system,
   mobile, speed, SEO/local, accessibility, and competitive differentiation.
6. Be specific to New Ridge (family + restorative + comfort + Dr. Reno + Wichita metro).
7. "Best ever" means: patient-first clarity, brand authority, zero stock-photo confusion,
   frictionless new-patient path, proof, and memorable local identity — not gimmicks.

OUTPUT FORMAT (strict markdown):
# Verdict — Can this become best-in-class? (yes/no + why)
## 0. Operator Intent
## 1. Scorecard (1–10) — Design, Trust, Conversion, IA, Content, Mobile, Local SEO, Differentiation
## 2. What Already Improved (credit recent work; do not re-litigate as if undone)
## 3. Full-Site Critique — across ALL page types (homepage, services, new patients,
   insurance/payment, about/doctor/staff/reviews/photos, contact, SEO landing pages,
   under-developed / thin pages, 404s)
## 4. Best-Dental-Website-Ever Standard — the bar (10 principles)
## 5. Gap Analysis — current site vs that bar
## 6. Primary Design + Brand Direction (world-class)
## 7. Information Architecture — ideal sitemap (merge/kill/keep/create)
## 8. Homepage Spec — first viewport + below-fold (wireframe text + copy)
## 9. Page-Type Specs — Services, New Patients, Doctor, Reviews, Contact, Insurance
## 10. Content & Photography Plan
## 11. Conversion System — CTAs, forms, phone, portal, membership
## 12. Technical / PBHS Constraints & Required Tickets
## 13. Phased Roadmap to "Best Ever" (30 / 60 / 90 / 180 days)
## 14. Validation Gates + Risks
DO NOT invent clinical claims. CONSULT ONLY until operator approves implementation.
"""

LIVE_FACTS = """
### PRACTICE
- New Ridge Family Dental — Dr. Michael Reno, DDS
- 2135 North Ridge Rd Ste 700, Wichita, KS 67212
- Phone: (316) 722-6060
- Hours: Monday–Thursday, 7:00 AM–4:00 PM
- Serves: Andover, Cheney, Goddard, Maize, Haysville, Derby, Newton, Colwich KS
- Platform: PBHS WordPress (footer: Family Dentistry Website Design by PBHS © 2026)
- Admin: /admin — layoutAccess/canUpdateLayouts often false

### ALREADY LIVE (2026-07-10 redesign session — credit these)
- Color Options navy #1E3A5F
- Hero collage → single office photo (CSS hide panels 2–4)
- Hero CTAs navy + white text
- Mega-nav SEO strip HIDDEN — primary nav: Home / Services / New Patients /
  Insurance & Payment / About / Contact
- Hero H1 overlay: Modern Family Dentistry in Wichita
- Hero subhead overlay: Comprehensive dental care for every generation…
- Eyebrow: Wichita · Andover · Goddard
- Footer tagline overlay: Modern Family Dentistry in Wichita
- Review title: What Wichita Families Are Saying
- Misleading "Read More Reviews about {random page}" CTAs hidden
- Banner Slides: office photo 20250728_155656-rotated.jpg
- Meet the Doctor banner locked to Dr. Reno sitting photo (blueeyes_77f17b.png)
  instead of rotating stock woman/lifestyle photos
- Overrides via <style id="nr-pro-sitewide"> on all 93 pages (compact CSS; no scripts)

### STILL OBSERVED WEAKNESSES (post-redesign)
- Source H1 in DOM still "Comfort-Focused…" (visual overlay only — a11y/SEO mismatch)
- Homepage still has dense mid-page portal/action card stack + video strip
- Featured icon tiles still rotate odd destinations (ops/policy pages sometimes)
- Stock PBHS photos still appear in some component areas (photo609/photo579 etc.)
- Demo/theme logo asset still referenced in places (demo-logo-2156-lg.png)
- NR helper JS still rotates stock heroImages unless CSS locks background
- layoutAccess false — cannot cleanly edit Layout parts in admin
- Original NR CSS/JS bundle not editable from this login
- Some SEO landing / utility pages thin or "under development" style content
  appears in homepage featured cards
- /insurance-and-payment/ sampled as 404 (nav may use different slug —
  Insurance & Payment exists in primary nav; verify canonical URL)
- 93 pages total — many SEO/utility pages still in sitemap even if mega-nav hidden
- Review carousel still exists but CTAs hidden (may need real reviews CTA to
  Patient Reviews page)
- Membership popup still present ("No Insurance? Perfect!")

### KEY PAGE SAMPLES (fetched 2026-07-10)
- / title varies; visual hero improved; stock assets still in HTML
- /services/ — Services & Treatments
- /patient-information/scheduling/ — Scheduling
- /patient-information/first-visit/ — First Visit
- /about-us/dr-michael-reno/ — Dr. Michael Christian Reno + blueeyes portrait in content
- /about-us/patient-reviews/ — Patient Testimonials
- /about-us/office-photos/ — real office photos present
- /contact/ — Contact New Ridge Family Dental
- /insurance-and-payment/ — 404 in sample (broken path or wrong guess)

### FULL PAGE INVENTORY (93 pages — titles)
Includes core IA plus many SEO/utility pages, e.g.:
Free Consultation Request, Dental Insurance Guide, Downtown Wichita Dentist,
Dentist in Northwest Wichita, Dental Implants, Cosmetic Dentistry,
Before & After Gallery, Blog & News, Dental Emergencies, FAQ,
Financing & Insurance Options, Contact Us, About Our Practice,
Patient Success Stories, Family Dentist in South Wichita, Orthodontics,
Our Team, Patient Portal, Patient Testimonials, Pricing & Cost Information,
plus full SoftDent-style service tree (preventive/restorative/dentures/cosmetic/
sedation/new patients/policies/etc.)

Operator goal: evaluate ALL pages and prescribe what makes this the BEST dental
office website EVER. CONSULT ONLY.
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

    # Attach compact page list if snapshot exists
    snap_path = OUT / "website_pages_snapshot.json"
    page_list = ""
    if snap_path.exists():
        try:
            snap = json.loads(snap_path.read_text(encoding="utf-8"))
            titles = [
                f"- {p.get('title')} — /{p.get('slug')}/"
                for p in (snap.get("pages") or [])
            ]
            page_list = (
                f"\n### COMPLETE PAGE LIST ({snap.get('pageCount')} pages)\n"
                + "\n".join(titles)
                + "\n"
            )
        except Exception as exc:  # noqa: BLE001
            page_list = f"\n(page snapshot unreadable: {exc})\n"

    print(f"Using {key_name} @ {base_url} model={model}")
    user = (
        "OPERATOR REQUEST (VERBATIM — do not rewrite):\n\n"
        f"{OPERATOR_REQUEST_VERBATIM}\n\n"
        "CONSULT ONLY — full-site evaluation + roadmap to best dental website ever.\n\n"
        "## Context\n\n"
        + LIVE_FACTS
        + page_list
    )
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
        ],
        "temperature": 1.0,
        "max_tokens": 16000,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    if "openrouter" in base_url.lower():
        headers["HTTP-Referer"] = "https://github.com/NewRidgeFamilyFinancial"
        headers["X-Title"] = "NR2 Best Dental Website Ever Consult"

    print("Calling Moonshot AI (best-ever website consult)...")
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
    except Exception as exc:  # noqa: BLE001
        content = str(exc)
        status = "error"

    header = (
        f"# Moonshot AI — Best Dental Website Ever (FULL-SITE CONSULT)\n\n"
        f"**Date:** {DATE}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Endpoint:** {base_url}  \n"
        f"**Status:** {status}  \n"
        f"**Site:** https://www.renodentalcare.org/  \n"
        f"**Platform:** PBHS WordPress (admin `/admin`)  \n"
        f"**Pages evaluated:** 93 (inventory attached)  \n"
        f"**Script:** `scripts/run_moonshot_website_best_ever_consult.py`  \n"
        f"**Apply:** DO NOT EDIT LIVE until operator approves specific phases.\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    full = header + (content or "(empty)")
    out_file = OUT / f"MOONSHOT_WEBSITE_BEST_EVER_CONSULT_{DATE}.md"
    doc_file = DOCS / f"MOONSHOT_WEBSITE_BEST_EVER_CONSULT_{DATE}.md"
    out_file.write_text(full, encoding="utf-8")
    doc_file.write_text(full, encoding="utf-8")
    print(out_file)
    print(doc_file)
    print(f"chars={len(content or '')} status={status}")
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
