#!/usr/bin/env python3
"""Idempotent seed of extended HAL governed memories + bootstrap learned facts."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NR2 = ROOT / "NewRidgeFinancial2"
sys.path.insert(0, str(NR2))

MEMORIES_PATH = ROOT / "docs" / "hal_knowledge" / "memories.jsonl"
LEARNED_PATH = ROOT / "app_data" / "nr2" / "learned_memories.jsonl"
STAMP = "2026-07-08T00:00:00Z"
BASE = {
    "created_at": STAMP,
    "last_verified_at": STAMP,
    "confidence": "high",
    "sensitivity_level": "internal_safe",
    "status": "approved",
    "staleness_rule": "verify_monthly",
}


def mem(
    memory_id: str,
    category: str,
    text: str,
    source: str,
    scope: str,
    *,
    staleness_rule: str = "verify_monthly",
    must_not_override: list[str] | None = None,
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
            "staleness_rule": staleness_rule,
            "must_not_override": must_not_override
            or ["guardrails", "runtime_status", "source_availability"],
            "notes": notes,
        }
    )
    return row


EXTENDED: list[dict] = [
    # --- Denial / ERA ---
    mem(
        "denial-code-16-lacks-info",
        "insurance_narratives",
        "Claim adjustment code 16 means information requested from the provider was not supplied or was insufficient. "
        "Appeal with narrative sections for history, clinical findings, radiographs or photos, CDT justification, and "
        "tooth or quadrant alignment. Attach chart excerpts; HAL drafts locally only.",
        "CARC code 16 + NR2 narrative workflow",
        "insurance_narratives",
        must_not_override=["guardrails", "external_submission_policy"],
    ),
    mem(
        "adjustment-co-45-contractual",
        "insurance_narratives",
        "CO-45 is contractual obligation — payer reduced fee to allowed amount, not a clinical denial. Do not draft "
        "medical-necessity appeals for CO-45 alone; review fee schedule, write-off policy, and patient portion (PR) instead.",
        "ERA adjustment CO-45",
        "insurance_narratives",
    ),
    mem(
        "adjustment-pr-1-patient-responsibility",
        "insurance_narratives",
        "PR-1 indicates patient responsibility (deductible, copay, or coinsurance). Separate from clinical denial — "
        "verify benefits, post patient balance, and use financial policy; narratives rarely apply unless paired with denial code 16.",
        "ERA adjustment PR-1",
        "insurance_narratives",
    ),
    mem(
        "era-remark-prefix-risk",
        "insurance_narratives",
        "High-risk ERA remark prefixes for follow-up: N4 (missing info), N30 (patient ineligible), N130 (consult plan "
        "benefits), CO (contractual), PR (patient responsibility). Map remark to narrative or billing action before resubmit.",
        "era_denial_trainer remark prefixes",
        "insurance_narratives",
    ),
    mem(
        "denial-frequency-limit-appeal",
        "insurance_narratives",
        "Frequency-limit denials require proof the service is a new episode, different tooth or quadrant, or medically "
        "necessary repeat (e.g., recurrent decay, new fracture). Cite dates of prior service and clinical change — never invent prior history.",
        "Frequency limit appeals",
        "insurance_narratives",
        must_not_override=["guardrails", "external_submission_policy"],
    ),
    mem(
        "denial-missing-narrative-d2740",
        "insurance_narratives",
        "Common pair: D2740 crown denied for missing narrative or insufficient documentation. Use fracture, failing "
        "restoration, or structural compromise template; attach bitewing or periapical radiograph reference in chart.",
        "COMMON_DENIAL_CDT_PAIRS D2740",
        "insurance_narratives",
    ),
    mem(
        "denial-missing-attachment-xray",
        "insurance_narratives",
        "Attachment denials (radiograph, photo, perio chart) need a cover letter listing enclosed items with date taken "
        "and tooth number. HAL may list required attachments; staff must actually attach files outside HAL.",
        "Attachment denial workflow",
        "insurance_narratives",
        must_not_override=["guardrails", "external_submission_policy"],
    ),
    # --- SoftDent ---
    mem(
        "softdent-claims-field-alias-map",
        "softdent_exports",
        "SoftDent claims export canonical fields: ClaimId, PatientName, Payer, ServiceDate, ClaimAmount, ClaimStatus, "
        "Procedure, DenialReason. Legacy aliases include claim_id, patient_ref, payer_name. import_contract.pick_field "
        "resolves case-insensitive matches for HAL aggregates.",
        "import-manifest.json softdent.claims",
        "softdent",
    ),
    mem(
        "softdent-procedures-export-narratives",
        "softdent_exports",
        "Procedures export fields Code, Tooth, Surface, Date, MRN, Description support narrative preflight — verify "
        "narrative tooth and CDT match procedures export before drafting payer letters.",
        "import-manifest.json softdent.procedures",
        "softdent",
    ),
    mem(
        "softdent-aggregate-coverage-files",
        "softdent_exports",
        "Additional SoftDent aggregate CSVs (outstanding_claims_by_company, unsubmitted_claims, insurance_income, "
        "payment_plans) supplement KPIs but are not required manifest datasets. Missing optional files must not block claims workbench.",
        "docs/export_automation_instructions.md",
        "softdent",
    ),
    mem(
        "softdent-daysheet-final-for-ar",
        "softdent_exports",
        "Authoritative collections and same-day A/R reconciliation require a final daysheet export when production is "
        "reported without collectionsReported. Widgets show collections unavailable — not zero — until daysheet loads.",
        "import_sync collections diagnostic",
        "softdent",
        staleness_rule="runtime_check_required",
    ),
    mem(
        "softdent-bridge-fallback-dashboard",
        "softdent_exports",
        "Dashboard may read bridge-fallback snapshot when export file is stale. Treat bridge data as provisional; run "
        "import sync and verify integration health before month-end decisions.",
        "practice_source_access bridge-fallback",
        "softdent",
        staleness_rule="runtime_check_required",
    ),
    mem(
        "softdent-dental-ar-vs-qb-gl",
        "softdent_exports",
        "SoftDent patient A/R aging is dental operational balances. QuickBooks GL A/R (account 1100 in NR2 COA) reflects "
        "accounting ledger — totals will differ. Reconcile with timing, adjustments, and insurance lag — never assume equality.",
        "NR2 financial boundary",
        "softdent",
    ),
    mem(
        "softdent-claimstatus-denial-fields",
        "softdent_exports",
        "Claim status export adds denial_reason, narrative_needed, paid_amount, date_submitted. Use for denial queue "
        "prioritization and narrative template matching — still read-only in HAL.",
        "import-manifest.json softdent.claimStatus",
        "softdent",
    ),
    mem(
        "softdent-clinical-notes-boundary",
        "softdent_exports",
        "Clinical notes import supplies sanitized snippets for authorized staff workflows. HAL must not dump full NoteText "
        "rows or expose unrestricted clinical notes in prompts — use approved aggregates and staff review.",
        "docs/hal_phi_rag_architecture.md",
        "softdent",
        staleness_rule="never",
        must_not_override=["guardrails"],
    ),
    # --- QuickBooks ---
    mem(
        "qb-import-dataset-field-map",
        "quickbooks_readonly",
        "QuickBooks manifest datasets: revenue (TotalIncome), profitAndLoss (NetIncome), expenses (TotalExpense), "
        "expenseCategories (Category, Amount), ar (Bucket, Balance). SDK probe maps total_income, total_expenses, ar_aging.",
        "import-manifest.json quickbooks.*",
        "quickbooks",
    ),
    mem(
        "qb-category-to-coa-hints",
        "quickbooks_readonly",
        "Map QB expense categories to NR2 planning COA: Payroll → 6200, Supplies → 5200, Insurance → 5050, Equipment → 1500, "
        "Depreciation → 6100. Journal drafts in accounting_tools.py are review-only — HAL never posts to QuickBooks.",
        "accounting_tools.py CHART_OF_ACCOUNTS",
        "quickbooks",
    ),
    mem(
        "qb-ar-not-softdent-ar",
        "quickbooks_readonly",
        "QuickBooks A/R aging in imports reflects GL balances, not dental patient responsibility by payer. For insurance "
        "follow-up and patient collections, use SoftDent A/R and claims exports.",
        "NR2 dual A/R architecture",
        "quickbooks",
    ),
    mem(
        "qb-export-only-read-mode",
        "quickbooks_readonly",
        "QuickBooks Mode 1 export-only reads CSV drops in document-inbox. Mode 2 SDK live read is read-only summary — "
        "no write path. HAL explains and prepares journal drafts for human review only.",
        "docs/quickbooks_desktop_safe_architecture.md",
        "quickbooks",
    ),
    mem(
        "qb-revenue-vs-collections-timing",
        "quickbooks_readonly",
        "QB revenue and net income follow accrual timing; SoftDent collections track operational cash and insurance receipts. "
        "Collections trailing production is normal short-term — triage with SoftDent aging before adjusting books.",
        "program_help ar topic",
        "quickbooks",
    ),
    mem(
        "qb-payroll-expense-mapping",
        "quickbooks_readonly",
        "Officer and staff payroll in QuickBooks supports S corp reasonable compensation documentation. Cross-check W-2 "
        "totals to tax planning officer W-2 scenario — CPA confirms final comp.",
        "tax_engine + accounting_tools",
        "taxes",
    ),
    # --- Compliance ---
    mem(
        "hipaa-minimum-necessary-chat",
        "operator_playbooks",
        "HAL internal staff assistant may use patient names for authorized workflows but must apply minimum necessary — "
        "no bulk PHI, no texting unsecured narrative packages, no emailing payer without standing written consent.",
        "HIPAA minimum necessary + NR2 consent",
        "hal",
        staleness_rule="never",
        must_not_override=["guardrails", "auth", "external_submission_policy"],
    ),
    mem(
        "hipaa-patient-text-email-rules",
        "operator_playbooks",
        "Patient SMS or email of clinical or financial details requires practice HIPAA policy and consent. HAL may draft "
        "messages locally; staff send through approved portal or secure channels — HAL never transmits.",
        "HIPAA communications",
        "hal",
        staleness_rule="never",
        must_not_override=["guardrails", "external_submission_policy"],
    ),
    mem(
        "osha-bloodborne-dental",
        "operator_playbooks",
        "Dental OSHA bloodborne pathogens: PPE, sharps disposal, sterilization logs, exposure incident protocol. HAL may "
        "explain checklist items; emergency response stays with trained staff and written office policy.",
        "OSHA dental summary",
        "hal",
    ),
    mem(
        "osha-sharps-incident-response",
        "operator_playbooks",
        "Needlestick or sharps exposure: encourage wound care, source patient testing per policy, document incident, "
        "notify occupational health. HAL provides checklist only — not medical treatment advice.",
        "OSHA exposure incident",
        "hal",
    ),
    mem(
        "kansas-dental-assistant-scope",
        "operator_playbooks",
        "Kansas dental assistant expanded functions require training and dentist supervision per board rules. HAL must not "
        "instruct assistants to perform out-of-scope procedures — refer to state board and office delegation policy.",
        "Kansas dental board scope summary",
        "hal",
    ),
    mem(
        "infection-control-cdc-dental",
        "operator_playbooks",
        "CDC dental infection control: instrument processing (clean, inspect, pack, sterilize, spore test logs), waterline "
        "maintenance, single-use disposables. HAL summarizes; compliance officer maintains logs.",
        "CDC dental infection control summary",
        "hal",
    ),
    # --- Scheduling / front desk ---
    mem(
        "hygiene-recare-intervals",
        "operator_playbooks",
        "Hygiene recare: typical prophy interval 6 months; perio maintenance 3–4 months after SRP. Align SoftDent recall "
        "with clinical probing and payer frequency limits before billing D4910 or D1110.",
        "Dental hygiene recare",
        "softdent",
    ),
    mem(
        "broken-appointment-policy-template",
        "operator_playbooks",
        "Broken appointments: document no-show in chart, reschedule within policy window, consider confirmation calls "
        "for high-value production. HAL may track office tasks; no automated patient contact without staff consent workflow.",
        "Front desk scheduling",
        "hal",
    ),
    mem(
        "new-patient-intake-checklist",
        "operator_playbooks",
        "New patient intake: demographics, insurance card scan, medical history, HIPAA forms, benefit verification, "
        "assignment of benefits, emergency contact. Eligibility 270/271 before major treatment when possible.",
        "New patient workflow",
        "hal",
    ),
    mem(
        "emergency-same-day-triage",
        "operator_playbooks",
        "Same-day emergency triage: pain, swelling, trauma, bleeding — schedule urgent operatory, document chief complaint "
        "and vitals, consider medical referral for airway or severe infection signs.",
        "Dental emergency triage",
        "hal",
    ),
    mem(
        "operatory-turnover-supplies",
        "operator_playbooks",
        "Operatory turnover: dispose sharps, disinfect surfaces, restock anesthetic and composites, verify sterilization "
        "pouches for next patient. HAL may reference checklist; assistants execute chairside.",
        "Clinical ops turnover",
        "hal",
    ),
    # --- Clinical documentation ---
    mem(
        "perio-staging-chart-requirements",
        "insurance_narratives",
        "Periodontal staging for SRP appeals: probing depths by tooth, BOP, recession, mobility, furcation, radiographic "
        "bone loss, diagnosis (localized vs generalized). Align with AAP staging when documenting advanced disease.",
        "Periodontal charting standards",
        "insurance_narratives",
    ),
    mem(
        "radiograph-selection-narrative",
        "insurance_narratives",
        "Narrative radiograph references: bitewing for interproximal decay, periapical for periapical pathology or endo, "
        "panoramic for third molar or broad survey, CBCT for implant site. Cite date and region — do not claim images not in chart.",
        "Radiograph selection documentation",
        "insurance_narratives",
    ),
    mem(
        "informed-consent-major-treatment",
        "insurance_narratives",
        "Major treatment (crowns, SRP quads, extractions, implants) requires signed informed consent with alternatives "
        "and fees before insurance narrative or claim — consent forms are separate from payer letters.",
        "Informed consent workflow",
        "insurance_narratives",
    ),
    mem(
        "referral-vs-treat-in-house",
        "operator_playbooks",
        "Refer endo, perio surgery, complex extractions, implants, or sedation cases when beyond GP scope or patient "
        "preference. Document referral in chart; HAL may suggest referral criteria not replace clinical judgment.",
        "Clinical referral guidance",
        "hal",
    ),
    mem(
        "emergency-pulpitis-documentation",
        "insurance_narratives",
        "Emergency pulpitis narrative: onset timing, spontaneous pain, percussion, cold test, radiograph findings, "
        "palliative treatment if performed, and definitive endo plan. Urgent same-day codes need symptom documentation.",
        "Emergency endo documentation",
        "insurance_narratives",
    ),
    mem(
        "extraction-medical-necessity-d7140",
        "insurance_narratives",
        "Extraction D7140/D7210 appeals: non-restorable tooth, severe bone loss, fracture, failed prior restoration, "
        "patient declined root canal. Document informed refusal of alternatives when applicable.",
        "Extraction medical necessity",
        "insurance_narratives",
    ),
    mem(
        "bridge-d6210-medical-necessity",
        "insurance_narratives",
        "Fixed bridge D6210+ narratives: missing tooth function, abutment health, occlusal considerations, why removable "
        "partial is insufficient. Include pontic site and abutment teeth matching claim lines.",
        "Bridge narrative guidance",
        "insurance_narratives",
    ),
    mem(
        "composite-surface-documentation-d2391",
        "insurance_narratives",
        "Posterior composite D2391–D2394 requires documented surfaces (MOD, DO, etc.), caries depth, and why amalgam "
        "alternate benefit is inadequate when appealing downgrade denials.",
        "Composite surface documentation",
        "insurance_narratives",
    ),
    mem(
        "medical-history-red-flags-dental",
        "operator_playbooks",
        "Medical history red flags: anticoagulants, bisphosphonates, cardiac conditions, uncontrolled diabetes, pregnancy, "
        "allergies to anesthetics or latex. Update health history annually; consult physician when clearance needed.",
        "Medical history dental",
        "hal",
    ),
    mem(
        "antibiotic-prophylaxis-guidance",
        "operator_playbooks",
        "Antibiotic prophylaxis for dental treatment follows current ADA/AAOS guidelines for at-risk cardiac and joint "
        "patients. HAL summarizes historical guidance — clinician and physician decide regimen.",
        "ADA prophylaxis summary",
        "hal",
    ),
    # --- Deployment / integration ---
    mem(
        "import-manifest-source-of-truth",
        "deployment_notes",
        "import-manifest.json version 1 defines required SoftDent and QuickBooks datasets, filenames, fields, and widget "
        "bindings. import_contract.py fallbacks apply when manifest missing — prefer manifest in production.",
        "import-manifest.json",
        "deployment",
        staleness_rule="expires_90d",
    ),
    mem(
        "direct-first-imports-mode",
        "deployment_notes",
        "NR2_DIRECT_FIRST_IMPORTS reads upstream export roots before cache when enabled. Live source availability still "
        "wins over memory — check integration health after enabling.",
        "practice_source_access direct-first",
        "deployment",
        staleness_rule="expires_90d",
    ),
    mem(
        "integration-health-severity-guide",
        "deployment_notes",
        "Integration health: connected = usable, stale = guidance only with watermark, missing = unavailable not zero. "
        "Optional datasets degrade widgets without blocking HAL chat. Run Sync-HAL-Imports.ps1 to refresh.",
        "integration_health.py",
        "hal",
    ),
    mem(
        "sync-hal-imports-operator-path",
        "deployment_notes",
        "Operators refresh imports via HAL Refresh imports or Sync-HAL-Imports.ps1. Files land in document-inbox "
        "softdent/ and quickbooks/ under app_data — HAL never writes back to SoftDent or QuickBooks.",
        "program_help imports",
        "deployment",
    ),
    mem(
        "support-bundle-contents",
        "deployment_notes",
        "Support bundle packages redacted env keys, integration health, import diagnostics, automation runs, and "
        "learned_memories.jsonl path listing for troubleshooting — no raw PHI exports.",
        "support_bundle.py",
        "deployment",
    ),
    mem(
        "payer-reference-json-curated",
        "project_architecture",
        "Curated payer routing and narrative hints live in NewRidgeFinancial2/data/payer_reference.json (40+ payers). "
        "HAL injects payer reference matches at ask time — not member-specific benefits; verify 270/271 eligibility live.",
        "payer_reference_store.py",
        "insurance_narratives",
        staleness_rule="verify_monthly",
    ),
    # --- Known workflows ---
    mem(
        "hal-employee-workflow-staging-local",
        "known_workflows",
        "hal_employee_workflows stages claim preflight, EOB match, deposit reconciliation, and month-end tasks in local "
        "SQLite only — no SoftDent or QuickBooks writeback.",
        "hal_employee_workflows.py",
        "hal",
    ),
    mem(
        "narrative-template-selection-scoring",
        "known_workflows",
        "select_best_narrative_for_claim scores 100 generic MemoAI drafts by procedure tags and denial reason keywords "
        "from SoftDent claim row. Staff must review selected draft before any payer use.",
        "hal_narrative_library.py",
        "insurance_narratives",
    ),
    mem(
        "practice-source-pull-read-only",
        "known_workflows",
        "practice_source_pull assembles SoftDent and QuickBooks sections read-only for HAL briefings. approved mode in "
        "hal-manager.json — nothing written upstream.",
        "practice_source_access.py",
        "hal",
    ),
    mem(
        "document-sync-review-queue",
        "known_workflows",
        "document_sync merges import summaries into local review queue. Journal posting drafts remain review-required; "
        "OCR documents may flag review_required until staff triages.",
        "document_sync.py",
        "quickbooks",
    ),
    mem(
        "import-sync-widget-feed-chain",
        "known_workflows",
        "import_sync → evaluate_bundle diagnostics → widget feed refresh. Stale or missing datasets propagate DEGRADED "
        "widget status with missing-data hints rather than fabricated numbers.",
        "import_loader + import_diagnostics",
        "hal",
    ),
    # --- Program help mirror ---
    mem(
        "program-help-topic-index",
        "operator_playbooks",
        "Program help topics: imports (sync/stale), widgets (degraded/no data), documents (posting queue), claims (denied/"
        "appeal), ar (SoftDent vs QB), support (bundle), daily-closeout, hal-chat (local AI lanes). Ask HAL how do I… to match.",
        "program_help.py TOPICS",
        "hal",
    ),
    mem(
        "daily-closeout-checklist-expanded",
        "operator_playbooks",
        "Daily closeout checks: import freshness, Ollama probe, documents queue, denied claims aging, A/R 90+ exposure, "
        "treatment plan exports, hygiene recall gaps. Run from Office Manager or ask HAL for daily closeout.",
        "daily_closeout.py",
        "hal",
    ),
    mem(
        "collections-trailing-production-triage",
        "operator_playbooks",
        "When collections trail production: check insurance outstanding claims, EOB posting lag, patient AR 90+, and "
        "final daysheet presence. Do not infer zero collections — use unavailable state when exports incomplete.",
        "program_help ar + softdent daysheet",
        "softdent",
    ),
    mem(
        "treatment-plan-acceptance-tracking",
        "operator_playbooks",
        "Treatment plan KPIs use treatment_plan_summary export: presented vs accepted vs scheduled vs completed. Low "
        "acceptance may need financial presentation review — HAL reads aggregates only.",
        "import-manifest softdent.treatmentPlans",
        "softdent",
    ),
    # --- Learning system ---
    mem(
        "hal-learn-as-you-go-policy",
        "project_architecture",
        "HAL learns via governed memories.jsonl (maintainer-approved) and learned_memories.jsonl (staff remember + import "
        "sync observations). Learning provides guidance only — never overrides guardrails, consent, or live import status.",
        "hal_learning.py + knowledge_memory_store",
        "hal",
        staleness_rule="never",
        must_not_override=["guardrails", "auth", "runtime_status"],
    ),
    mem(
        "hal-memory-search-priority",
        "project_architecture",
        "At answer time precedence: auth and guardrails, live runtime and source availability, deterministic import data, "
        "governed MemoAI memories, payer reference hints, learned staff facts, session handoff context.",
        "docs/hal_knowledge/README.md",
        "hal",
        staleness_rule="never",
    ),
    mem(
        "hal-session-handoff-context",
        "known_workflows",
        "HAL stores local session handoff (last claim, narrative, payer, page, topic) in app_data/nr2/hal_session_context.json "
        "for continuity between turns — no external sync, cleared on demand.",
        "hal_learning.py session context",
        "hal",
    ),
    # --- Kansas practice context ---
    mem(
        "kansas-bcbs-dental-routing",
        "insurance_narratives",
        "Blue Cross Blue Shield of Kansas dental claims route to state affiliate payer IDs on patient card — not national "
        "BCBS generic. Verify Kansas vs out-of-state BCBS plan before narrative and submission routing.",
        "Kansas BCBS dental routing",
        "insurance_narratives",
    ),
    mem(
        "kansas-medicaid-dental-kancare",
        "insurance_narratives",
        "Kansas KanCare Medicaid dental uses MCO-specific prior auth and frequency rules. Medical necessity language stricter "
        "than commercial PPO — never apply Delta or MetLife playbook to Medicaid without MCO policy review.",
        "Kansas KanCare dental summary",
        "insurance_narratives",
    ),
    # --- Dental general knowledge ---
    mem(
        "local-anesthetic-documentation",
        "operator_playbooks",
        "Document anesthetic: agent, carpules, technique, aspiration noted, post-op instructions. Allergy and epinephrine "
        "contraindications must appear in medical history before administration.",
        "Clinical anesthesia documentation",
        "hal",
    ),
    mem(
        "nitrous-oxide-documentation",
        "operator_playbooks",
        "Nitrous oxide sedation requires informed consent, vital signs, fasting instructions when applicable, and recovery "
        "assessment before discharge. Billing codes vary by payer — verify coverage separately.",
        "Nitrous documentation",
        "hal",
    ),
    mem(
        "dental-cdt-year-governance",
        "insurance_narratives",
        "CDT codes update annually January 1. HAL narrative playbooks reference common codes (D2740, D4341, D6010) — "
        "staff verify current year CDT descriptor on claim before submission.",
        "ADA CDT annual update",
        "insurance_narratives",
    ),
]

BOOTSTRAP_LEARNED: list[dict] = [
    mem(
        "nr2-bootstrap-office-role",
        "operator_playbooks",
        "New Ridge Financial 2 HAL serves as internal dental office staff assistant: billing, narratives, imports, taxes, "
        "and operations. Staff may teach office-specific facts with remember — HAL merges learned facts with governed MemoAI.",
        "NR2 bootstrap learned memory",
        "hal",
        notes="Bootstrap — staff may supersede with newer learned facts.",
    ),
    mem(
        "nr2-bootstrap-learn-triggers",
        "operator_playbooks",
        "Staff can say remember this, save this, or our office always… to store payer quirks, internal policies, and "
        "vendor contacts in learned memory. No PHI, secrets, or submit overrides.",
        "NR2 bootstrap learn triggers",
        "hal",
        notes="Bootstrap learn-as-you-go hint.",
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


def merge_memories(path: Path, rows: list[dict]) -> tuple[int, int]:
    existing = _load_ids(path)
    added = 0
    skipped = 0
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            memory_id = str(row.get("id") or "")
            if not memory_id or memory_id in existing:
                skipped += 1
                continue
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
            existing.add(memory_id)
            added += 1
    return added, skipped


def main() -> int:
    from knowledge_memory_store import write_browser_memo_index_js

    added, skipped = merge_memories(MEMORIES_PATH, EXTENDED)
    learned_added, learned_skipped = merge_memories(LEARNED_PATH, BOOTSTRAP_LEARNED)
    target = write_browser_memo_index_js()
    print(f"Governed: +{added} added, {skipped} skipped -> {MEMORIES_PATH}")
    print(f"Learned bootstrap: +{learned_added} added, {learned_skipped} skipped -> {LEARNED_PATH}")
    print(f"Browser index: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
