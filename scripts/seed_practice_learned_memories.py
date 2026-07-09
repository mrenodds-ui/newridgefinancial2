#!/usr/bin/env python3
"""Seed New Ridge Family Financial practice-specific learned memories (no PHI)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NR2 = ROOT / "NewRidgeFinancial2"
sys.path.insert(0, str(NR2))

LEARNED_PATH = ROOT / "app_data" / "nr2" / "learned_memories.jsonl"
STAMP = "2026-07-08T21:00:00Z"
BASE = {
    "created_at": STAMP,
    "last_verified_at": STAMP,
    "confidence": "high",
    "sensitivity_level": "internal_safe",
    "status": "approved",
    "staleness_rule": "verify_monthly",
    "must_not_override": ["guardrails", "runtime_status", "source_availability", "external_submission_policy"],
}


def learned(
    memory_id: str,
    category: str,
    text: str,
    source: str,
    scope: str,
    *,
    notes: str = "",
) -> dict:
    row = dict(BASE)
    row.update(
        {
            "id": memory_id,
            "category": category,
            "text": text,
            "source": source,
            "scope": scope,
            "notes": notes,
        }
    )
    return row


PRACTICE_LEARNED: list[dict] = [
    # --- Entity & structure ---
    learned(
        "nr2-practice-entity-kansas-scorp",
        "tax_accounting",
        "Practice entity is New Ridge Family Financial — Kansas S corporation dental practice. Tax planning uses NR2 Taxes page "
        "and read-only QuickBooks P&L; CPA review required before any IRS or KDOR filing.",
        "validate-pages.mjs entity + NR2 tax scope",
        "taxes",
        notes="Practice entity baseline.",
    ),
    learned(
        "nr2-practice-softdent-qb-split",
        "operator_playbooks",
        "In this office SoftDent is source of truth for production, collections, dental A/R, and claims. QuickBooks is source "
        "of truth for GL, P&L, payroll, and tax prep. HAL must never treat QB revenue as chairside production or QB A/R as patient aging.",
        "hal-manager.json sources",
        "hal",
    ),
    # --- Import paths & sync ---
    learned(
        "nr2-practice-softdent-export-roots",
        "softdent_exports",
        "Primary SoftDent export roots for this office: C:\\Users\\mreno\\SoftDentBridge\\exports, Sensei Gateway DataSync, "
        "C:\\NewRidgeBridge\\exports, and C:\\SoftDentFinancialExports. NR2 auto-pull copies into app_data document_inbox/softdent.",
        "import-manifest.json upstreamRoots.softdent",
        "softdent",
    ),
    learned(
        "nr2-practice-quickbooks-export-roots",
        "quickbooks_readonly",
        "QuickBooks exports for this office land in C:\\Users\\mreno\\QuickBooksExports (and shared SoftDentFinancialExports). "
        "Run Sync-HAL-Imports.ps1 or Refresh imports in HAL after new drops.",
        "import-manifest.json upstreamRoots.quickbooks",
        "quickbooks",
    ),
    learned(
        "nr2-practice-daysheet-final-ar",
        "softdent_exports",
        "This office requires a final SoftDent daysheet per business date for authoritative collections and A/R. Without daysheet "
        "totals, NR2 shows collections as unavailable — not zero. Morning import sync should include latest daysheet.",
        "hal-manager askHal suggestion + import_sync diagnostic",
        "softdent",
    ),
    learned(
        "nr2-practice-import-sync-daily",
        "operator_playbooks",
        "Office routine: run import sync at start of day and after major SoftDent/QuickBooks exports. Check integration health "
        "before month-end, narrative work, or owner briefings.",
        "program_help imports + daily closeout",
        "hal",
    ),
    # --- Top payers (this office mix) ---
    learned(
        "nr2-practice-payer-mix-top-five",
        "insurance_narratives",
        "Primary commercial payers in this office dashboard mix: Delta Dental, Cigna, MetLife, Guardian, and BCBS (verify Kansas "
        "affiliate ID on card). Self-pay and Other appear when exports lack payer breakdown.",
        "page-canvas.js payer defaults + claims exports",
        "insurance_narratives",
    ),
    learned(
        "nr2-practice-delta-code-16-playbook",
        "insurance_narratives",
        "Delta Dental in this office frequently denies major services with code 16 (missing information). Standard appeal pack: "
        "clinical history, radiograph date, fracture or decay narrative, tooth number, and staff-attached periapical or bitewing.",
        "payer_reference delta-dental + CI/eval claims",
        "insurance_narratives",
    ),
    learned(
        "nr2-practice-metlife-downgrade-crowns",
        "insurance_narratives",
        "MetLife in this office often applies alternate benefit downgrades on posterior crowns and composites. Narratives must "
        "document structural loss, cusp fracture, or recurrent decay undermining prior restoration — not cosmetic language.",
        "payer_reference metlife-dental",
        "insurance_narratives",
    ),
    learned(
        "nr2-practice-guardian-frequency-prophy",
        "insurance_narratives",
        "Guardian plans in this office hit frequency limits on prophy and bitewings. When billing SRP same visit, document perio "
        "charting separately from preventive prophy to reduce bundling denials.",
        "payer_reference guardian-dental",
        "insurance_narratives",
    ),
    learned(
        "nr2-practice-bcbs-kansas-routing",
        "insurance_narratives",
        "BCBS Kansas members in this office use state affiliate payer IDs (not generic national BCBS). Confirm card payer ID and "
        "claims address before narrative or resubmit — Kansas routing differs from out-of-state BCBS plans.",
        "payer_reference bcbs-kansas-dental",
        "insurance_narratives",
    ),
    learned(
        "nr2-practice-kancare-separate-workflow",
        "insurance_narratives",
        "KanCare Medicaid in Kansas uses MCO-specific prior auth and stricter medical necessity. Do not reuse Delta or MetLife "
        "commercial narrative templates for KanCare — verify MCO portal and PA status first.",
        "kansas-medicaid-dental-kancare memory + payer_reference",
        "insurance_narratives",
    ),
    # --- Staff routing & workflows (roles, not PHI) ---
    learned(
        "nr2-practice-narrative-review-chain",
        "operator_playbooks",
        "Insurance narrative chain for this office: HAL drafts locally → billing coordinator reviews clinical accuracy → "
        "owner-dentist sign-off on crowns, implants, and SRP quads → attach radiographs → mark ready. HAL never submits to payer.",
        "narrative-staff-review-workflow + hal-manager consent",
        "insurance_narratives",
    ),
    learned(
        "nr2-practice-denied-claims-priority",
        "operator_playbooks",
        "Denied claims aging past 30 days are office priority for narrative and appeal work. Start with highest balance and "
        "code 16 / missing-info denials where chart documentation is already complete.",
        "program_help claims + hal-manager work surfaces",
        "insurance_narratives",
    ),
    learned(
        "nr2-practice-claim-preflight-local",
        "known_workflows",
        "Before narrative work on any CLM-* claim, run claim preflight: eligibility verified, fee schedule, tooth/quadrant match, "
        "denial reason captured, attachments listed. Example eval claims use IDs like CLM-2026-1001 format from SoftDent export.",
        "validate-hal narrative route + hal_employee_workflows",
        "softdent",
    ),
    learned(
        "nr2-practice-eob-before-patient-statement",
        "operator_playbooks",
        "Office policy: post insurance EOB and adjustments in SoftDent before sending patient statements on disputed balances. "
        "HAL process_eob_match stages matches locally — staff post in SoftDent outside HAL.",
        "eob-posting-match-workflow",
        "softdent",
    ),
    learned(
        "nr2-practice-month-end-first-week",
        "operator_playbooks",
        "Month-end close target: first week of following month. Sequence: final daysheet → import sync → EOB sweep → A/R 90+ review → "
        "QuickBooks P&L check → HAL month-end task list → owner review with CPA items flagged.",
        "month-end-reconciliation-playbook",
        "quickbooks",
    ),
    learned(
        "nr2-practice-owner-tax-review",
        "tax_accounting",
        "Owner reviews NR2 Taxes page planning estimates quarterly with CPA. Modeled officer W-2 and K-1 ordinary are planning "
        "only — not filed amounts. Kansas K-120S and owner K-40 flow from same book-to-tax bridge.",
        "tax_engine + nr2-taxes-page-scope",
        "taxes",
    ),
    # --- Consent & outbound ---
    learned(
        "nr2-practice-consent-explicit-outbound",
        "safety_policy",
        "This office requires explicit staff consent per outbound action: payer email, fax, claim packet send, QuickBooks journal "
        "post, IIF export, and SoftDent writeback queue. Standing consent must be documented — sidenote verbal OK is insufficient.",
        "hal-manager status + standing-consent memory",
        "hal",
        notes="Non-negotiable outbound consent for this office.",
    ),
    learned(
        "nr2-practice-level7-writeback",
        "operator_playbooks",
        "QuickBooks Online journal post, IIF export, and SoftDent writeback queue require level 7 executive partner consent in NR2. "
        "HAL prepares drafts and queues only — human confirms each action.",
        "hal-manager practiceSourcePull",
        "hal",
    ),
    # --- Labs & vendors ---
    learned(
        "nr2-practice-lab-glidewell",
        "operator_playbooks",
        "Primary lab vendor appearing in document queue examples: Glidewell (crowns/implant components). Lab invoices route through "
        "accounting document review before any QuickBooks posting.",
        "validate-pages documents sync fixture",
        "quickbooks",
        notes="Vendor from test fixture — confirm with staff if primary lab changes.",
    ),
    # --- SideNotes & operatory ---
    learned(
        "nr2-practice-sidenotes-hub",
        "operator_playbooks",
        "Operatory and front-desk SideNotes route through NR2_SIDENOTES_HUB_DATA shared folder. HAL monitors routing metadata and "
        "voice announcements — not message bodies. Use sidenotes for hygiene recall and same-day handoffs.",
        "hal-manager sidenotes program",
        "hal",
    ),
    learned(
        "nr2-practice-hygiene-recall-sidenotes",
        "operator_playbooks",
        "Hygiene recall gaps flagged in daily closeout should get a sidenote task for front desk confirmation calls. HAL may add "
        "office tasks locally; staff place calls outside HAL.",
        "hal-manager askHal sidenote suggestion",
        "hal",
    ),
    # --- Crown / SRP office standards ---
    learned(
        "nr2-practice-crown-docs-required",
        "insurance_narratives",
        "Office standard for crown appeals: pre-op radiograph, documented fracture or failing restoration, buildup rationale if "
        "D2950 billed, and consent on file. Match tooth number to SoftDent claim line before HAL narrative draft.",
        "crown-d2740 + claim preflight",
        "insurance_narratives",
    ),
    learned(
        "nr2-practice-srp-prophy-same-day",
        "insurance_narratives",
        "When SRP and prophy occur same visit in this office, chart must show perio disease activity (probing, BOP, radiographic "
        "bone loss) separate from preventive cleaning — required for Guardian and Delta bundling appeals.",
        "srp-d4341-vs-prophy memory + payer mix",
        "insurance_narratives",
    ),
    # --- Collections ---
    learned(
        "nr2-practice-collections-trailing-production",
        "operator_playbooks",
        "When collections trail production in this office, triage order: (1) outstanding insurance claims by payer, (2) missing "
        "daysheet for current period, (3) EOB posting lag, (4) patient AR 90+. Do not use QuickBooks cash alone as dental collections.",
        "collections-trailing-production-triage memory",
        "softdent",
    ),
    # --- HAL usage ---
    learned(
        "nr2-practice-hal-pull-approved",
        "known_workflows",
        "Staff approved HAL practice source pull: SoftDent and QuickBooks into local import cache on boot and on demand. "
        "100 generic narrative templates available; best match scored per claim for staff review.",
        "hal-manager practiceSourcePull + hal_narrative_library",
        "hal",
    ),
    learned(
        "nr2-practice-remember-to-teach",
        "operator_playbooks",
        "When office policy or payer behavior changes, staff should tell HAL: Remember this: … — updates learned_memories.jsonl "
        "without a code deploy. Override older learned facts by saving a newer remember with the corrected policy.",
        "staff-remember-learned-memories",
        "hal",
    ),
    learned(
        "nr2-practice-office-manager-steve",
        "operator_playbooks",
        "Steve is the office manager for New Ridge Family Financial. Route import sync, integration health, daily closeout, "
        "month-end coordination, SideNotes hub issues, and cross-department office tasks to Steve. HAL may mention Steve by name "
        "for authorized internal staff workflows.",
        "staff:remember (office manager)",
        "hal",
        notes="Staff-provided role assignment.",
    ),
    learned(
        "nr2-practice-doctor-michael-reno",
        "operator_playbooks",
        "Dr. Michael Reno is the only dentist and owner-doctor at New Ridge Family Financial. Route clinical sign-off on crowns, "
        "implants, SRP quads, and complex treatment plans to Dr. Reno. Officer W-2 and reasonable-compensation planning refer to "
        "Dr. Reno as the working owner-dentist.",
        "staff:remember (provider roster)",
        "hal",
        notes="Single-doctor practice.",
    ),
    # --- Staff workflows (Steve + Dr Reno) ---
    learned(
        "nr2-practice-steve-morning-huddle",
        "operator_playbooks",
        "Morning huddle at New Ridge: Steve (office manager) reviews schedule openings, hygiene recall gaps, outstanding narratives, "
        "and import health. Dr. Michael Reno confirms major treatment blocks. HAL daily closeout supports the checklist — staff act in SoftDent.",
        "NR2 morning huddle playbook",
        "hal",
    ),
    learned(
        "nr2-practice-steve-billing-queue",
        "operator_playbooks",
        "Steve coordinates the billing queue at New Ridge Family Financial: denied claims, narrative drafts awaiting Dr. Reno sign-off, "
        "and EOB posting backlog. Billing staff execute; Steve prioritizes by balance and aging.",
        "staff:remember (billing coordination)",
        "hal",
    ),
    learned(
        "nr2-practice-front-desk-checkin",
        "operator_playbooks",
        "Front desk check-in at New Ridge: verify insurance card and eligibility before seating, confirm fee estimate for uninsured "
        "portions, capture broken-appointment policy acknowledgment, and route complex benefits questions to Steve or billing.",
        "NR2 front desk playbook",
        "hal",
    ),
    learned(
        "nr2-practice-hygiene-handoff",
        "operator_playbooks",
        "Hygiene operatory handoff at New Ridge: document probing and radiograph needs for Dr. Michael Reno exam. Flag same-day SRP "
        "candidates with perio charting before doctor enters. Use SideNotes for front-desk scheduling follow-ups Steve tracks.",
        "NR2 hygiene handoff playbook",
        "hal",
    ),
    learned(
        "nr2-practice-new-patient-intake",
        "operator_playbooks",
        "New patient intake at New Ridge Family Financial: collect demographics and insurance, run eligibility, schedule comprehensive "
        "exam with Dr. Michael Reno, and note self-pay estimates in SoftDent. Steve ensures intake forms complete before first clinical visit.",
        "NR2 new patient workflow",
        "hal",
    ),
    learned(
        "nr2-practice-cigna-prior-auth-majors",
        "insurance_narratives",
        "Cigna dental in this office often requires prior authorization before crowns, implants, and multi-quadrant SRP. Verify PA status "
        "in Cigna portal before scheduling major treatment with Dr. Michael Reno — do not reuse Delta narrative templates.",
        "payer_reference cigna-dental + practice mix",
        "insurance_narratives",
    ),
    learned(
        "nr2-practice-aetna-attachment-preference",
        "insurance_narratives",
        "Aetna dental claims in this office frequently need dated radiographs attached for major services. Include radiograph date and tooth "
        "number in narrative; Steve's billing queue flags Aetna code-16 denials for attachment sweep.",
        "payer_reference aetna-dental + practice mix",
        "insurance_narratives",
    ),
    learned(
        "nr2-practice-implant-dr-reno-signoff",
        "insurance_narratives",
        "Implant cases at New Ridge (D6010/D6058/D6065) require Dr. Michael Reno treatment plan sign-off, CBCT or panoramic reference, "
        "and medical necessity narrative before billing. Single-doctor practice — all surgical and restorative implant claims reference Dr. Reno.",
        "implant narrative + provider roster",
        "insurance_narratives",
    ),
    learned(
        "nr2-practice-softdent-claim-id-format",
        "softdent_exports",
        "SoftDent claim IDs in this office export as CLM-YYYY-#### style rows (eval fixtures use CLM-2026-1001 pattern). HAL claim preflight "
        "and narrative tools key off ClaimId — verify export column alias map if imports show blank IDs.",
        "validate-hal narrative route + import contract",
        "softdent",
    ),
    learned(
        "nr2-practice-qb-payroll-dr-reno",
        "quickbooks_readonly",
        "QuickBooks payroll for New Ridge maps Dr. Michael Reno as owner-dentist W-2 officer wages for S corp reasonable compensation "
        "planning. HAL Taxes page models officer W-2 separately from distributions — CPA confirms filed amounts.",
        "tax_engine + provider roster",
        "quickbooks",
    ),
    learned(
        "nr2-practice-hal-validation-baseline",
        "test_results",
        "HAL validation baseline for New Ridge: validate-hal.mjs runs 100+ suites; pytest covers learning, portal ops, and tax citations. "
        "After memory corpus changes run python scripts/sync_hal_memo_index.py and re-run validation before deploy.",
        "validate-hal.mjs + pytest",
        "testing",
    ),
    # --- Hygiene department ---
    learned(
        "nr2-practice-hygiene-recall-interval",
        "operator_playbooks",
        "Hygiene recall at New Ridge Family Financial: prophy D1110 typically every six months unless perio maintenance D4910 applies after SRP. "
        "Front desk schedules next hygiene before patient leaves; Steve tracks recall gaps in daily closeout and SideNotes tasks.",
        "NR2 hygiene recall playbook",
        "hal",
    ),
    learned(
        "nr2-practice-hygiene-perio-maintenance",
        "insurance_narratives",
        "After SRP at New Ridge, perio maintenance D4910 replaces routine prophy D1110 on insurance claims. Hygiene must chart probing at maintenance visits — "
        "Guardian and Delta deny D4910 without post-SRP charting. Dr. Michael Reno confirms active perio diagnosis when questioned.",
        "SRP + perio maintenance playbook",
        "insurance_narratives",
    ),
    learned(
        "nr2-practice-hygiene-bitewing-frequency",
        "operator_playbooks",
        "Bitewing radiographs at New Ridge follow payer frequency rules — typically one set per year for adults unless clinical findings justify more. "
        "Document caries risk or recurrent decay in chart when billing D0274 outside standard interval; billing appeals need that note.",
        "NR2 radiograph frequency playbook",
        "hal",
    ),
    learned(
        "nr2-practice-hygiene-fluoride-varnish",
        "operator_playbooks",
        "Topical fluoride varnish D1206 at New Ridge: document medical necessity for adults when payer restricts age limits. "
        "Hygiene notes xerostomia, high caries risk, or root exposure — Dr. Michael Reno supports adult fluoride when charted clinically.",
        "NR2 fluoride documentation",
        "hal",
    ),
    learned(
        "nr2-practice-hygiene-srp-same-day-exam",
        "operator_playbooks",
        "Same-day SRP at New Ridge requires Dr. Michael Reno exam (D0120 or D0150) and full perio charting before billing D4341/D4342. "
        "Hygiene completes probing and BOP documentation before doctor enters; Steve's billing queue rejects SRP claims missing quad charting.",
        "NR2 SRP same-day workflow",
        "insurance_narratives",
    ),
    learned(
        "nr2-practice-hygiene-broken-appointment",
        "operator_playbooks",
        "Broken hygiene appointments at New Ridge: front desk logs cancel reason in SoftDent, offers reschedule within two weeks, and flags repeat no-shows to Steve. "
        "HAL may add office tasks — staff place confirmation calls; do not auto-charge fees without documented office policy.",
        "NR2 broken appointment policy",
        "hal",
    ),
    # --- Front desk ---
    learned(
        "nr2-practice-front-desk-checkout",
        "operator_playbooks",
        "Front desk checkout at New Ridge: collect estimated copay or self-pay balance, confirm next appointment is booked, provide post-op instructions for "
        "same-day treatment, and route outstanding insurance questions to Steve or billing before patient leaves.",
        "NR2 front desk checkout",
        "hal",
    ),
    learned(
        "nr2-practice-front-desk-eligibility-270",
        "operator_playbooks",
        "Eligibility at New Ridge check-in: run 270/271 or clearinghouse eligibility before seating for new plans and major treatment days. "
        "Front desk captures member ID and group number from card — Steve reviews failed eligibility responses before proceeding with elective treatment.",
        "NR2 eligibility at check-in",
        "insurance_narratives",
    ),
    learned(
        "nr2-practice-front-desk-balance-before-treatment",
        "operator_playbooks",
        "Office policy at New Ridge: discuss patient portion estimate before starting elective treatment when balance or deductible applies. "
        "Front desk coordinates with Steve on payment arrangements; HAL never processes payments — SoftDent ledger is source of truth.",
        "NR2 patient balance policy",
        "hal",
    ),
    learned(
        "nr2-practice-front-desk-phone-triage",
        "operator_playbooks",
        "Front desk phone triage at New Ridge: clinical emergencies same-day with Dr. Michael Reno schedule; billing and insurance questions to Steve or billing; "
        "HIPAA — verify patient identity before discussing account details. HAL assists staff drafts only — no outbound calls without consent.",
        "NR2 phone triage playbook",
        "hal",
    ),
    learned(
        "nr2-practice-front-desk-after-hours",
        "operator_playbooks",
        "After-hours dental emergencies at New Ridge route to on-call guidance for Dr. Michael Reno — single-doctor practice. "
        "Front desk voicemail instructs true emergencies to seek urgent care; next-business-day pain calls scheduled as limited D0140 problem-focused visits.",
        "NR2 after-hours routing",
        "hal",
    ),
    # --- Additional payers (practice mix) ---
    learned(
        "nr2-practice-uhc-dental-narratives",
        "insurance_narratives",
        "UnitedHealthcare dental in this office uses UHC payer IDs on card — confirm PPO vs Medicare Advantage dental crossover before narrative. "
        "Code 16 and missing radiograph denials common on crowns; attach periapical and date of service in appeal pack Steve prioritizes.",
        "payer_reference uhc-dental",
        "insurance_narratives",
    ),
    learned(
        "nr2-practice-humana-dental-frequency",
        "insurance_narratives",
        "Humana dental at New Ridge hits frequency limits on prophy and bitewings — verify benefit year reset date at eligibility. "
        "When billing major services same year as preventive maxed, document medical necessity separately from routine cleaning.",
        "payer_reference humana-dental",
        "insurance_narratives",
    ),
    learned(
        "nr2-practice-principal-dental-fee-schedule",
        "insurance_narratives",
        "Principal dental in this office adjudicates to contracted fee schedule — CO-45 contractual adjustments expected, not narrative appeals. "
        "Steve routes Principal underpayment review to fee schedule verification, not missing-info narrative team.",
        "payer_reference principal-dental",
        "insurance_narratives",
    ),
    learned(
        "nr2-practice-anthem-bcbs-crossover",
        "insurance_narratives",
        "Anthem and out-of-state BCBS plans at New Ridge require card payer ID verification — do not assume Kansas BCBS routing. "
        "Narrative and claims address differ by state affiliate; billing confirms electronic payer ID before resubmit.",
        "payer_reference anthem-dental + bcbs-kansas",
        "insurance_narratives",
    ),
    learned(
        "nr2-practice-geha-federal-dental",
        "insurance_narratives",
        "GEHA federal employee dental appears in Kansas patient mix — verify FEHB plan year and high-option vs standard benefits before major treatment estimate. "
        "Prior auth may apply on implants; Dr. Michael Reno signs treatment plan for GEHA major services.",
        "payer_reference geha-dental",
        "insurance_narratives",
    ),
    learned(
        "nr2-practice-aarp-delta-seniors",
        "insurance_narratives",
        "AARP Delta Dental plans at New Ridge often cover seniors with separate payer routing from commercial Delta PPO. "
        "Confirm AARP-branded ID card payer ID; code 16 denials use same narrative pack as nr2-practice-delta-code-16-playbook with card-specific routing.",
        "payer_reference aarp-delta",
        "insurance_narratives",
    ),
    learned(
        "nr2-practice-dentaquest-medicaid-mco",
        "insurance_narratives",
        "DentaQuest and other Medicaid MCO dental plans in Kansas require separate workflow from commercial PPO — never reuse Delta or MetLife templates. "
        "Verify KanCare MCO assignment and prior auth portal before scheduling SRP or extractions with Dr. Michael Reno.",
        "payer_reference dentaquest + kancare",
        "insurance_narratives",
    ),
    learned(
        "nr2-practice-sunlife-dental-downgrade",
        "insurance_narratives",
        "Sun Life dental at New Ridge may apply alternate benefit on posterior composites — document extent of caries and cusp involvement like MetLife downgrade playbook. "
        "Billing attaches pre-op radiograph for appeal when Sun Life downgrades D2392 to amalgam alternate.",
        "payer_reference sunlife-dental",
        "insurance_narratives",
    ),
    # --- Tax / owner planning (New Ridge S corp) ---
    learned(
        "nr2-practice-tax-quarterly-cpa-review",
        "tax_accounting",
        "New Ridge Family Financial quarterly tax rhythm: Steve coordinates book close with QuickBooks P&L import, Dr. Michael Reno reviews production vs collections, "
        "and CPA models officer W-2, K-1, and 1040-ES estimates. HAL Taxes page is planning only — not filed returns.",
        "NR2 quarterly tax review",
        "taxes",
    ),
    learned(
        "nr2-practice-tax-kansas-pte-annual",
        "tax_accounting",
        "Each fall CPA compares Kansas PTE tax election vs paying on Dr. Michael Reno's K-40 for New Ridge S corp. "
        "Entity-level PTE may help when owner is in higher Kansas bracket — decision documented before K-120S filing.",
        "kansas-pte-tax-election + practice entity",
        "taxes",
    ),
    learned(
        "nr2-practice-tax-book-to-tax-bridge",
        "tax_accounting",
        "Month-end book-to-tax bridge at New Ridge: QuickBooks P&L categories map to NR2 chart of accounts for CPA prep — dental supplies, lab, payroll, depreciation. "
        "Steve flags uncategorized transactions before quarter-end; HAL read-only never posts adjusting journal entries.",
        "accounting_tools + month-end playbook",
        "taxes",
    ),
    learned(
        "nr2-practice-tax-section179-equipment",
        "tax_accounting",
        "Capital equipment purchases at New Ridge (chairs, CBCT, scanner) route through CPA Section 179 or bonus depreciation analysis. "
        "Dr. Michael Reno approves major purchases; document business use percentage — HAL cites scorp-section-179-dental-equipment for planning questions.",
        "scorp-section-179-dental-equipment + practice",
        "taxes",
    ),
    learned(
        "nr2-practice-tax-w2-distribution-ratio",
        "tax_accounting",
        "Annual reasonable compensation review for Dr. Michael Reno at New Ridge: CPA targets W-2 officer wages relative to S corp net income before distributions. "
        "Under-waged owner-dentist S corps are IRS exam targets — payroll reports and production data support the study Steve gathers for CPA.",
        "scorp-reasonable-compensation-dental + provider roster",
        "taxes",
    ),
    learned(
        "nr2-practice-tax-estimated-payment-calendar",
        "tax_accounting",
        "Federal and Kansas estimated tax due dates for Dr. Michael Reno: April 15, June 15, September 15, January 15 (1040-ES schedule). "
        "Steve reminders on NR2 Taxes page checklist — coordinate amounts with CPA after each quarter QuickBooks close.",
        "scorp-estimated-tax-1040es + kansas-estimated-tax",
        "taxes",
    ),
    learned(
        "nr2-practice-tax-k1-owner-deadline",
        "tax_accounting",
        "New Ridge Form 1120-S and K-120S target March 15 calendar-year filing — K-1s to Dr. Michael Reno before owner 1040/K-40 prep. "
        "Extension via Form 7004 does not extend estimated tax due dates; CPA owns filing — HAL explains deadlines only.",
        "scorp-1120s-deadline + kansas-k120s-return",
        "taxes",
    ),
]


def _load_ids(path: Path) -> set[str]:
    ids: set[str] = set()
    if not path.is_file():
        return ids
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict) and row.get("id"):
            ids.add(str(row["id"]))
    return ids


def main() -> int:
    from knowledge_memory_store import write_browser_memo_index_js

    LEARNED_PATH.parent.mkdir(parents=True, exist_ok=True)
    existing = _load_ids(LEARNED_PATH)
    added = 0
    with LEARNED_PATH.open("a", encoding="utf-8", newline="\n") as handle:
        for row in PRACTICE_LEARNED:
            memory_id = str(row.get("id") or "")
            if not memory_id or memory_id in existing:
                continue
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
            existing.add(memory_id)
            added += 1
    target = write_browser_memo_index_js()
    from knowledge_memory_store import load_approved_memories

    total = len(load_approved_memories())
    print(f"Practice learned: +{added} added -> {LEARNED_PATH}")
    print(f"Total indexable memories (governed + learned): {total}")
    print(f"Browser index refreshed: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
