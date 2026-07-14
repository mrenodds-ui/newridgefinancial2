# SoftDent Full Product Knowledge (encoded for NR2/HAL)

**Date:** 2026-07-13  
**Goal:** SoftDent **inside and out** — whole-product Help knowledge in the program, not titles alone.

---

## What was learned

Source of truth: Carestream **SoftDent Online Help OH_DE1010** decompiled from this PC:

`C:\SoftDent\WinHelp\SoftDent_OnlineHelp_OH_DE1010.chm`

| Surface | Encoded |
|---------|---------|
| Help TOC | **2040** topics (full `.hhc` tree) |
| Help topic **bodies** | **1874** searchable Help pages in `softdent_product_kb_topics.json` (~3 MB) |
| howSoftDentWorks | Lifecycle map + **18** core Help articles (posting, reports, ERA, schedule, charting, insurance, …) |
| Reports menu | **13 categories**, **167** named reports with descriptions |
| Product modules | Scheduling, Patients/Accounts, Transactions/Codes, Insurance/eClaims/ERA, Accounting, Practice Management analytics, Charting/Tx Planning, Imaging, Rx/Labs, Security/Utilities, Sensei integrations |
| Roles / workflows | Front Desk, Hygienist, Dental Assistant, Treatment Coordinator, Office Manager |
| Keystrokes | F1 Help, F3 Account, F4 Provider, F5 Patient, F8 ADA, F10 menus |
| Office doctrine | Launch `.lnk -sus`, Sign On COMPUTE, Excel/Preview only, period $ vs ops lane |
| Electronic Services | `ECSHELP.hlp` topic titles (claim validation, payer lists) — not full WinHelp bodies |

**Honesty:** HAL searches real Carestream Help **body text**. Long pages are truncated (~3.5k chars; core how-it-works up to ~12k). Full product knowledge ≠ full GUI automation.

---

## How the PROGRAM knows it

| Artifact | Role |
|----------|------|
| `softdent_product_kb.json` | TOC, reports, modules, howSoftDentWorks |
| `softdent_product_kb_topics.json` | Searchable Help article bodies (inside-out) |
| `softdent_product_kb.py` | Deep `lookup_topic_bodies` + HAL formatter |
| `scripts/build_softdent_product_kb.py` | Rebuild from Help extract |
| HAL local policy | `policy:softdent-product-kb` |
| LLM inject | `compile_softdent_signon_guidance` on product questions |
| API | `GET /api/apex/hal/softdent-kb?q=Account+Aging` |

Automation catalogs stay separate for pulls: `softdent_gui_menu_map.json`, `softdent_master_reports.json`.

---

## Rebuild

```text
hh -decompile C:\SoftDentReportExports\softdent_help_extract C:\SoftDent\WinHelp\SoftDent_OnlineHelp_OH_DE1010.chm
python NewRidgeFinancial2\scripts\build_softdent_product_kb.py
python -m unittest NewRidgeFinancial2.test_softdent_product_kb -v
```

Restart Apex after rebuild so HAL reloads the topic body cache.

---

## Ask HAL examples

- “How does SoftDent work inside and out?”
- “Describe SoftDent Account Aging from Help”
- “SoftDent charting / treatment plan / ERA”
- API: `/api/apex/hal/softdent-kb?q=unsubmitted+claims`
