/** Auto-synced MemoAI index — run: python scripts/sync_hal_memo_index.py */
const HalMemoIndex = (function () {
  const PRIORITY_BY_ID = {
  "insurance-narrative-local-only": {
    "title": "Insurance Narrative Local Only",
    "detail": "Insurance narrative export and drafting remain local-only. Narratives are review-required and must stay not_submitted; HAL must never submit, send, fax, or upload narrative packages.",
    "source": "docs/insurance_narratives.md",
    "category": "insurance_narratives"
  },
  "no-external-submit-actions": {
    "title": "No External Submit Actions",
    "detail": "HAL must never submit, send, fax, upload, or perform Gateway actions on behalf of the operator. Unsafe external-action requests must be refused or limited to local review guidance.",
    "source": "docs/hal_phi_rag_architecture.md boundary rules",
    "category": "safety_policy"
  },
  "nr2-taxes-page-scope": {
    "title": "Nr2 Taxes Page Scope",
    "detail": "The NR2 Taxes page under Financial provides read-only federal and Kansas S corporation tax checklists for the practice entity. HAL may explain deadlines, reasonable compensation, K-1 flow-through, and Kansas K-120S topics from MemoAI memories. HAL must not e-file, submit returns…",
    "source": "NewRidgeFinancial2/site/moonshot-page-registry.js taxes page",
    "category": "tax_accounting"
  },
  "scorp-1120s-deadline": {
    "title": "Scorp 1120s Deadline",
    "detail": "Calendar-year S corporations must generally file Form 1120-S by March 15 (or the next business day). Form 7004 may extend the filing deadline. Issue K-1s to shareholders when the return is filed.",
    "source": "IRS Form 1120-S due date (summary)",
    "category": "tax_accounting"
  },
  "scorp-reasonable-compensation-dental": {
    "title": "Scorp Reasonable Compensation Dental",
    "detail": "Owner-dentists who work in the practice should receive reasonable W-2 wages before taking substantial S corporation distributions. The IRS examines dental S corps for unreasonably low officer compensation paired with high distributions. Document compensation studies and payroll r…",
    "source": "IRS reasonable compensation guidance (summary)",
    "category": "tax_accounting"
  },
  "scorp-section-199a-qbi": {
    "title": "Scorp Section 199a Qbi",
    "detail": "Shareholders may qualify for the Section 199A qualified business income deduction on S corp pass-through income, subject to taxable income limits, specified service trade or business rules for certain fields, and W-2 wage/UBIA limitations. Dental practice facts vary—have the CPA…",
    "source": "IRS Section 199A overview (summary)",
    "category": "tax_accounting"
  },
  "kansas-pte-tax-election": {
    "title": "Kansas Pte Tax Election",
    "detail": "Kansas allows certain pass-through entities, including S corporations, to elect pass-through entity (PTE) tax so tax is paid at the entity level with a corresponding owner credit. Compare PTE tax vs paying Kansas tax on the individual return with the CPA each year.",
    "source": "Kansas PTE tax election (summary)",
    "category": "tax_accounting"
  },
  "scorp-quickbooks-readonly-prep": {
    "title": "Scorp Quickbooks Readonly Prep",
    "detail": "HAL may use read-only QuickBooks P&L and expense imports on the Taxes page to help staff and the CPA reconcile book income to tax return line items. HAL must not post adjusting entries, file returns, or treat import totals as final tax liabilities.",
    "source": "NR2 QuickBooks read-only boundary + Taxes page",
    "category": "tax_accounting"
  },
  "nr2-practice-entity-kansas-scorp": {
    "title": "Nr2 Practice Entity Kansas Scorp",
    "detail": "Practice entity is New Ridge Family Financial — Kansas S corporation dental practice. Tax planning uses NR2 Taxes page and read-only QuickBooks P&L; CPA review required before any IRS or KDOR filing.",
    "source": "validate-pages.mjs entity + NR2 tax scope",
    "category": "tax_accounting"
  },
  "nr2-practice-softdent-qb-split": {
    "title": "Nr2 Practice Softdent Qb Split",
    "detail": "In this office SoftDent is source of truth for production, collections, dental A/R, and claims. QuickBooks is source of truth for GL, P&L, payroll, and tax prep. HAL must never treat QB revenue as chairside production or QB A/R as patient aging.",
    "source": "hal-manager.json sources",
    "category": "operator_playbooks"
  },
  "nr2-practice-softdent-export-roots": {
    "title": "Nr2 Practice Softdent Export Roots",
    "detail": "Primary SoftDent export roots for this office: C:\\Users\\mreno\\SoftDentBridge\\exports, Sensei Gateway DataSync, C:\\NewRidgeBridge\\exports, and C:\\SoftDentFinancialExports. NR2 auto-pull copies into app_data document_inbox/softdent.",
    "source": "import-manifest.json upstreamRoots.softdent",
    "category": "softdent_exports"
  },
  "nr2-practice-quickbooks-export-roots": {
    "title": "Nr2 Practice Quickbooks Export Roots",
    "detail": "QuickBooks exports for this office land in C:\\Users\\mreno\\QuickBooksExports (and shared SoftDentFinancialExports). Run Sync-HAL-Imports.ps1 or Refresh imports in HAL after new drops.",
    "source": "import-manifest.json upstreamRoots.quickbooks",
    "category": "quickbooks_readonly"
  },
  "nr2-practice-daysheet-final-ar": {
    "title": "Nr2 Practice Daysheet Final Ar",
    "detail": "This office requires a final SoftDent daysheet per business date for authoritative collections and A/R. Without daysheet totals, NR2 shows collections as unavailable — not zero. Morning import sync should include latest daysheet.",
    "source": "hal-manager askHal suggestion + import_sync diagnostic",
    "category": "softdent_exports"
  },
  "nr2-practice-import-sync-daily": {
    "title": "Nr2 Practice Import Sync Daily",
    "detail": "Office routine: run import sync at start of day and after major SoftDent/QuickBooks exports. Check integration health before month-end, narrative work, or owner briefings.",
    "source": "program_help imports + daily closeout",
    "category": "operator_playbooks"
  },
  "nr2-practice-payer-mix-top-five": {
    "title": "Nr2 Practice Payer Mix Top Five",
    "detail": "Primary commercial payers in this office dashboard mix: Delta Dental, Cigna, MetLife, Guardian, and BCBS (verify Kansas affiliate ID on card). Self-pay and Other appear when exports lack payer breakdown.",
    "source": "page-canvas.js payer defaults + claims exports",
    "category": "insurance_narratives"
  },
  "nr2-practice-delta-code-16-playbook": {
    "title": "Nr2 Practice Delta Code 16 Playbook",
    "detail": "Delta Dental in this office frequently denies major services with code 16 (missing information). Standard appeal pack: clinical history, radiograph date, fracture or decay narrative, tooth number, and staff-attached periapical or bitewing.",
    "source": "payer_reference delta-dental + CI/eval claims",
    "category": "insurance_narratives"
  },
  "nr2-practice-metlife-downgrade-crowns": {
    "title": "Nr2 Practice Metlife Downgrade Crowns",
    "detail": "MetLife in this office often applies alternate benefit downgrades on posterior crowns and composites. Narratives must document structural loss, cusp fracture, or recurrent decay undermining prior restoration — not cosmetic language.",
    "source": "payer_reference metlife-dental",
    "category": "insurance_narratives"
  },
  "nr2-practice-guardian-frequency-prophy": {
    "title": "Nr2 Practice Guardian Frequency Prophy",
    "detail": "Guardian plans in this office hit frequency limits on prophy and bitewings. When billing SRP same visit, document perio charting separately from preventive prophy to reduce bundling denials.",
    "source": "payer_reference guardian-dental",
    "category": "insurance_narratives"
  },
  "nr2-practice-bcbs-kansas-routing": {
    "title": "Nr2 Practice Bcbs Kansas Routing",
    "detail": "BCBS Kansas members in this office use state affiliate payer IDs (not generic national BCBS). Confirm card payer ID and claims address before narrative or resubmit — Kansas routing differs from out-of-state BCBS plans.",
    "source": "payer_reference bcbs-kansas-dental",
    "category": "insurance_narratives"
  },
  "nr2-practice-kancare-separate-workflow": {
    "title": "Nr2 Practice Kancare Separate Workflow",
    "detail": "KanCare Medicaid in Kansas uses MCO-specific prior auth and stricter medical necessity. Do not reuse Delta or MetLife commercial narrative templates for KanCare — verify MCO portal and PA status first.",
    "source": "kansas-medicaid-dental-kancare memory + payer_reference",
    "category": "insurance_narratives"
  },
  "nr2-practice-narrative-review-chain": {
    "title": "Nr2 Practice Narrative Review Chain",
    "detail": "Insurance narrative chain for this office: HAL drafts locally → billing coordinator reviews clinical accuracy → owner-dentist sign-off on crowns, implants, and SRP quads → attach radiographs → mark ready. HAL never submits to payer.",
    "source": "narrative-staff-review-workflow + hal-manager consent",
    "category": "operator_playbooks"
  },
  "nr2-practice-denied-claims-priority": {
    "title": "Nr2 Practice Denied Claims Priority",
    "detail": "Denied claims aging past 30 days are office priority for narrative and appeal work. Start with highest balance and code 16 / missing-info denials where chart documentation is already complete.",
    "source": "program_help claims + hal-manager work surfaces",
    "category": "operator_playbooks"
  },
  "nr2-practice-claim-preflight-local": {
    "title": "Nr2 Practice Claim Preflight Local",
    "detail": "Before narrative work on any CLM-* claim, run claim preflight: eligibility verified, fee schedule, tooth/quadrant match, denial reason captured, attachments listed. Example eval claims use IDs like CLM-2026-1001 format from SoftDent export.",
    "source": "validate-hal narrative route + hal_employee_workflows",
    "category": "known_workflows"
  },
  "nr2-practice-eob-before-patient-statement": {
    "title": "Nr2 Practice Eob Before Patient Statement",
    "detail": "Office policy: post insurance EOB and adjustments in SoftDent before sending patient statements on disputed balances. HAL process_eob_match stages matches locally — staff post in SoftDent outside HAL.",
    "source": "eob-posting-match-workflow",
    "category": "operator_playbooks"
  },
  "nr2-practice-month-end-first-week": {
    "title": "Nr2 Practice Month End First Week",
    "detail": "Month-end close target: first week of following month. Sequence: final daysheet → import sync → EOB sweep → A/R 90+ review → QuickBooks P&L check → HAL month-end task list → owner review with CPA items flagged.",
    "source": "month-end-reconciliation-playbook",
    "category": "operator_playbooks"
  },
  "nr2-practice-owner-tax-review": {
    "title": "Nr2 Practice Owner Tax Review",
    "detail": "Owner reviews NR2 Taxes page planning estimates quarterly with CPA. Modeled officer W-2 and K-1 ordinary are planning only — not filed amounts. Kansas K-120S and owner K-40 flow from same book-to-tax bridge.",
    "source": "tax_engine + nr2-taxes-page-scope",
    "category": "tax_accounting"
  },
  "nr2-practice-consent-explicit-outbound": {
    "title": "Nr2 Practice Consent Explicit Outbound",
    "detail": "This office requires explicit staff consent per outbound action: payer email, fax, claim packet send, QuickBooks journal post, IIF export, and SoftDent writeback queue. Standing consent must be documented — sidenote verbal OK is insufficient.",
    "source": "hal-manager status + standing-consent memory",
    "category": "safety_policy"
  },
  "nr2-practice-level7-writeback": {
    "title": "Nr2 Practice Level7 Writeback",
    "detail": "QuickBooks Online journal post, IIF export, and SoftDent writeback queue require level 7 executive partner consent in NR2. HAL prepares drafts and queues only — human confirms each action.",
    "source": "hal-manager practiceSourcePull",
    "category": "operator_playbooks"
  },
  "nr2-practice-lab-glidewell": {
    "title": "Nr2 Practice Lab Glidewell",
    "detail": "Primary lab vendor appearing in document queue examples: Glidewell (crowns/implant components). Lab invoices route through accounting document review before any QuickBooks posting.",
    "source": "validate-pages documents sync fixture",
    "category": "operator_playbooks"
  },
  "nr2-practice-sidenotes-hub": {
    "title": "Nr2 Practice Sidenotes Hub",
    "detail": "Operatory and front-desk BlueNote route through NR2_SIDENOTES_HUB_DATA / HAL-BlueNote-Workstation shared folder. HAL monitors routing metadata and voice announcements — not message bodies. Use BlueNote for hygiene recall and same-day handoffs.",
    "source": "hal-manager sidenotes program",
    "category": "operator_playbooks"
  },
  "nr2-practice-hygiene-recall-sidenotes": {
    "title": "Nr2 Practice Hygiene Recall Sidenotes",
    "detail": "Hygiene recall gaps flagged in daily closeout should get a sidenote task for front desk confirmation calls. HAL may add office tasks locally; staff place calls outside HAL.",
    "source": "hal-manager askHal sidenote suggestion",
    "category": "operator_playbooks"
  },
  "nr2-practice-crown-docs-required": {
    "title": "Nr2 Practice Crown Docs Required",
    "detail": "Office standard for crown appeals: pre-op radiograph, documented fracture or failing restoration, buildup rationale if D2950 billed, and consent on file. Match tooth number to SoftDent claim line before HAL narrative draft.",
    "source": "crown-d2740 + claim preflight",
    "category": "insurance_narratives"
  },
  "nr2-practice-srp-prophy-same-day": {
    "title": "Nr2 Practice Srp Prophy Same Day",
    "detail": "When SRP and prophy occur same visit in this office, chart must show perio disease activity (probing, BOP, radiographic bone loss) separate from preventive cleaning — required for Guardian and Delta bundling appeals.",
    "source": "srp-d4341-vs-prophy memory + payer mix",
    "category": "insurance_narratives"
  },
  "nr2-practice-collections-trailing-production": {
    "title": "Nr2 Practice Collections Trailing Production",
    "detail": "When collections trail production in this office, triage order: (1) outstanding insurance claims by payer, (2) missing daysheet for current period, (3) EOB posting lag, (4) patient AR 90+. Do not use QuickBooks cash alone as dental collections.",
    "source": "collections-trailing-production-triage memory",
    "category": "operator_playbooks"
  },
  "nr2-practice-hal-pull-approved": {
    "title": "Nr2 Practice Hal Pull Approved",
    "detail": "Staff approved HAL practice source pull: SoftDent and QuickBooks into local import cache on boot and on demand. 100 generic narrative templates available; best match scored per claim for staff review.",
    "source": "hal-manager practiceSourcePull + hal_narrative_library",
    "category": "known_workflows"
  },
  "nr2-practice-remember-to-teach": {
    "title": "Nr2 Practice Remember To Teach",
    "detail": "When office policy or payer behavior changes, staff should tell HAL: Remember this: … — updates learned_memories.jsonl without a code deploy. Override older learned facts by saving a newer remember with the corrected policy.",
    "source": "staff-remember-learned-memories",
    "category": "operator_playbooks"
  },
  "nr2-practice-office-manager-steve": {
    "title": "Nr2 Practice Office Manager Steve",
    "detail": "Steve is the office manager for New Ridge Family Financial. Route import sync, integration health, daily closeout, month-end coordination, SideNotes hub issues, and cross-department office tasks to Steve. HAL may mention Steve by name for authorized internal staff workflows.",
    "source": "staff:remember (office manager)",
    "category": "operator_playbooks"
  },
  "nr2-practice-doctor-michael-reno": {
    "title": "Nr2 Practice Doctor Michael Reno",
    "detail": "Dr. Michael Reno is the only dentist and owner-doctor at New Ridge Family Financial. Route clinical sign-off on crowns, implants, SRP quads, and complex treatment plans to Dr. Reno. Officer W-2 and reasonable-compensation planning refer to Dr. Reno as the working owner-dentist.",
    "source": "staff:remember (provider roster)",
    "category": "operator_playbooks"
  },
  "nr2-practice-steve-morning-huddle": {
    "title": "Nr2 Practice Steve Morning Huddle",
    "detail": "Morning huddle at New Ridge: Steve (office manager) reviews schedule openings, hygiene recall gaps, outstanding narratives, and import health. Dr. Michael Reno confirms major treatment blocks. HAL daily closeout supports the checklist — staff act in SoftDent.",
    "source": "NR2 morning huddle playbook",
    "category": "operator_playbooks"
  },
  "nr2-practice-steve-billing-queue": {
    "title": "Nr2 Practice Steve Billing Queue",
    "detail": "Steve coordinates the billing queue at New Ridge Family Financial: denied claims, narrative drafts awaiting Dr. Reno sign-off, and EOB posting backlog. Billing staff execute; Steve prioritizes by balance and aging.",
    "source": "staff:remember (billing coordination)",
    "category": "operator_playbooks"
  },
  "nr2-practice-front-desk-checkin": {
    "title": "Nr2 Practice Front Desk Checkin",
    "detail": "Front desk check-in at New Ridge: verify insurance card and eligibility before seating, confirm fee estimate for uninsured portions, capture broken-appointment policy acknowledgment, and route complex benefits questions to Steve or billing.",
    "source": "NR2 front desk playbook",
    "category": "operator_playbooks"
  },
  "nr2-practice-hygiene-handoff": {
    "title": "Nr2 Practice Hygiene Handoff",
    "detail": "Hygiene operatory handoff at New Ridge: document probing and radiograph needs for Dr. Michael Reno exam. Flag same-day SRP candidates with perio charting before doctor enters. Use SideNotes for front-desk scheduling follow-ups Steve tracks.",
    "source": "NR2 hygiene handoff playbook",
    "category": "operator_playbooks"
  },
  "nr2-practice-new-patient-intake": {
    "title": "Nr2 Practice New Patient Intake",
    "detail": "New patient intake at New Ridge Family Financial: collect demographics and insurance, run eligibility, schedule comprehensive exam with Dr. Michael Reno, and note self-pay estimates in SoftDent. Steve ensures intake forms complete before first clinical visit.",
    "source": "NR2 new patient workflow",
    "category": "operator_playbooks"
  },
  "nr2-practice-cigna-prior-auth-majors": {
    "title": "Nr2 Practice Cigna Prior Auth Majors",
    "detail": "Cigna dental in this office often requires prior authorization before crowns, implants, and multi-quadrant SRP. Verify PA status in Cigna portal before scheduling major treatment with Dr. Michael Reno — do not reuse Delta narrative templates.",
    "source": "payer_reference cigna-dental + practice mix",
    "category": "insurance_narratives"
  },
  "nr2-practice-aetna-attachment-preference": {
    "title": "Nr2 Practice Aetna Attachment Preference",
    "detail": "Aetna dental claims in this office frequently need dated radiographs attached for major services. Include radiograph date and tooth number in narrative; Steve's billing queue flags Aetna code-16 denials for attachment sweep.",
    "source": "payer_reference aetna-dental + practice mix",
    "category": "insurance_narratives"
  },
  "nr2-practice-implant-dr-reno-signoff": {
    "title": "Nr2 Practice Implant Dr Reno Signoff",
    "detail": "Implant cases at New Ridge (D6010/D6058/D6065) require Dr. Michael Reno treatment plan sign-off, CBCT or panoramic reference, and medical necessity narrative before billing. Single-doctor practice — all surgical and restorative implant claims reference Dr. Reno.",
    "source": "implant narrative + provider roster",
    "category": "insurance_narratives"
  },
  "nr2-practice-softdent-claim-id-format": {
    "title": "Nr2 Practice Softdent Claim Id Format",
    "detail": "SoftDent claim IDs in this office export as CLM-YYYY-#### style rows (eval fixtures use CLM-2026-1001 pattern). HAL claim preflight and narrative tools key off ClaimId — verify export column alias map if imports show blank IDs.",
    "source": "validate-hal narrative route + import contract",
    "category": "softdent_exports"
  },
  "nr2-practice-qb-payroll-dr-reno": {
    "title": "Nr2 Practice Qb Payroll Dr Reno",
    "detail": "QuickBooks payroll for New Ridge maps Dr. Michael Reno as owner-dentist W-2 officer wages for S corp reasonable compensation planning. HAL Taxes page models officer W-2 separately from distributions — CPA confirms filed amounts.",
    "source": "tax_engine + provider roster",
    "category": "quickbooks_readonly"
  },
  "nr2-practice-hal-validation-baseline": {
    "title": "Nr2 Practice Hal Validation Baseline",
    "detail": "HAL validation baseline for New Ridge: validate-hal.mjs runs 100+ suites; pytest covers learning, portal ops, and tax citations. After memory corpus changes run python scripts/sync_hal_memo_index.py and re-run validation before deploy.",
    "source": "validate-hal.mjs + pytest",
    "category": "test_results"
  },
  "nr2-practice-hygiene-recall-interval": {
    "title": "Nr2 Practice Hygiene Recall Interval",
    "detail": "Hygiene recall at New Ridge Family Financial: prophy D1110 typically every six months unless perio maintenance D4910 applies after SRP. Front desk schedules next hygiene before patient leaves; Steve tracks recall gaps in daily closeout and SideNotes tasks.",
    "source": "NR2 hygiene recall playbook",
    "category": "operator_playbooks"
  },
  "nr2-practice-hygiene-perio-maintenance": {
    "title": "Nr2 Practice Hygiene Perio Maintenance",
    "detail": "After SRP at New Ridge, perio maintenance D4910 replaces routine prophy D1110 on insurance claims. Hygiene must chart probing at maintenance visits — Guardian and Delta deny D4910 without post-SRP charting. Dr. Michael Reno confirms active perio diagnosis when questioned.",
    "source": "SRP + perio maintenance playbook",
    "category": "insurance_narratives"
  },
  "nr2-practice-hygiene-bitewing-frequency": {
    "title": "Nr2 Practice Hygiene Bitewing Frequency",
    "detail": "Bitewing radiographs at New Ridge follow payer frequency rules — typically one set per year for adults unless clinical findings justify more. Document caries risk or recurrent decay in chart when billing D0274 outside standard interval; billing appeals need that note.",
    "source": "NR2 radiograph frequency playbook",
    "category": "operator_playbooks"
  },
  "nr2-practice-hygiene-fluoride-varnish": {
    "title": "Nr2 Practice Hygiene Fluoride Varnish",
    "detail": "Topical fluoride varnish D1206 at New Ridge: document medical necessity for adults when payer restricts age limits. Hygiene notes xerostomia, high caries risk, or root exposure — Dr. Michael Reno supports adult fluoride when charted clinically.",
    "source": "NR2 fluoride documentation",
    "category": "operator_playbooks"
  },
  "nr2-practice-hygiene-srp-same-day-exam": {
    "title": "Nr2 Practice Hygiene Srp Same Day Exam",
    "detail": "Same-day SRP at New Ridge requires Dr. Michael Reno exam (D0120 or D0150) and full perio charting before billing D4341/D4342. Hygiene completes probing and BOP documentation before doctor enters; Steve's billing queue rejects SRP claims missing quad charting.",
    "source": "NR2 SRP same-day workflow",
    "category": "operator_playbooks"
  },
  "nr2-practice-hygiene-broken-appointment": {
    "title": "Nr2 Practice Hygiene Broken Appointment",
    "detail": "Broken hygiene appointments at New Ridge: front desk logs cancel reason in SoftDent, offers reschedule within two weeks, and flags repeat no-shows to Steve. HAL may add office tasks — staff place confirmation calls; do not auto-charge fees without documented office policy.",
    "source": "NR2 broken appointment policy",
    "category": "operator_playbooks"
  },
  "nr2-practice-front-desk-checkout": {
    "title": "Nr2 Practice Front Desk Checkout",
    "detail": "Front desk checkout at New Ridge: collect estimated copay or self-pay balance, confirm next appointment is booked, provide post-op instructions for same-day treatment, and route outstanding insurance questions to Steve or billing before patient leaves.",
    "source": "NR2 front desk checkout",
    "category": "operator_playbooks"
  },
  "nr2-practice-front-desk-eligibility-270": {
    "title": "Nr2 Practice Front Desk Eligibility 270",
    "detail": "Eligibility at New Ridge check-in: run 270/271 or clearinghouse eligibility before seating for new plans and major treatment days. Front desk captures member ID and group number from card — Steve reviews failed eligibility responses before proceeding with elective treatment.",
    "source": "NR2 eligibility at check-in",
    "category": "operator_playbooks"
  },
  "nr2-practice-front-desk-balance-before-treatment": {
    "title": "Nr2 Practice Front Desk Balance Before Treatment",
    "detail": "Office policy at New Ridge: discuss patient portion estimate before starting elective treatment when balance or deductible applies. Front desk coordinates with Steve on payment arrangements; HAL never processes payments — SoftDent ledger is source of truth.",
    "source": "NR2 patient balance policy",
    "category": "operator_playbooks"
  },
  "nr2-practice-front-desk-phone-triage": {
    "title": "Nr2 Practice Front Desk Phone Triage",
    "detail": "Front desk phone triage at New Ridge: clinical emergencies same-day with Dr. Michael Reno schedule; billing and insurance questions to Steve or billing; HIPAA — verify patient identity before discussing account details. HAL assists staff drafts only — no outbound calls without co…",
    "source": "NR2 phone triage playbook",
    "category": "operator_playbooks"
  },
  "nr2-practice-front-desk-after-hours": {
    "title": "Nr2 Practice Front Desk After Hours",
    "detail": "After-hours dental emergencies at New Ridge route to on-call guidance for Dr. Michael Reno — single-doctor practice. Front desk voicemail instructs true emergencies to seek urgent care; next-business-day pain calls scheduled as limited D0140 problem-focused visits.",
    "source": "NR2 after-hours routing",
    "category": "operator_playbooks"
  },
  "nr2-practice-uhc-dental-narratives": {
    "title": "Nr2 Practice Uhc Dental Narratives",
    "detail": "UnitedHealthcare dental in this office uses UHC payer IDs on card — confirm PPO vs Medicare Advantage dental crossover before narrative. Code 16 and missing radiograph denials common on crowns; attach periapical and date of service in appeal pack Steve prioritizes.",
    "source": "payer_reference uhc-dental",
    "category": "insurance_narratives"
  },
  "nr2-practice-humana-dental-frequency": {
    "title": "Nr2 Practice Humana Dental Frequency",
    "detail": "Humana dental at New Ridge hits frequency limits on prophy and bitewings — verify benefit year reset date at eligibility. When billing major services same year as preventive maxed, document medical necessity separately from routine cleaning.",
    "source": "payer_reference humana-dental",
    "category": "insurance_narratives"
  },
  "nr2-practice-principal-dental-fee-schedule": {
    "title": "Nr2 Practice Principal Dental Fee Schedule",
    "detail": "Principal dental in this office adjudicates to contracted fee schedule — CO-45 contractual adjustments expected, not narrative appeals. Steve routes Principal underpayment review to fee schedule verification, not missing-info narrative team.",
    "source": "payer_reference principal-dental",
    "category": "insurance_narratives"
  },
  "nr2-practice-anthem-bcbs-crossover": {
    "title": "Nr2 Practice Anthem Bcbs Crossover",
    "detail": "Anthem and out-of-state BCBS plans at New Ridge require card payer ID verification — do not assume Kansas BCBS routing. Narrative and claims address differ by state affiliate; billing confirms electronic payer ID before resubmit.",
    "source": "payer_reference anthem-dental + bcbs-kansas",
    "category": "insurance_narratives"
  },
  "nr2-practice-geha-federal-dental": {
    "title": "Nr2 Practice Geha Federal Dental",
    "detail": "GEHA federal employee dental appears in Kansas patient mix — verify FEHB plan year and high-option vs standard benefits before major treatment estimate. Prior auth may apply on implants; Dr. Michael Reno signs treatment plan for GEHA major services.",
    "source": "payer_reference geha-dental",
    "category": "insurance_narratives"
  },
  "nr2-practice-aarp-delta-seniors": {
    "title": "Nr2 Practice Aarp Delta Seniors",
    "detail": "AARP Delta Dental plans at New Ridge often cover seniors with separate payer routing from commercial Delta PPO. Confirm AARP-branded ID card payer ID; code 16 denials use same narrative pack as nr2-practice-delta-code-16-playbook with card-specific routing.",
    "source": "payer_reference aarp-delta",
    "category": "insurance_narratives"
  },
  "nr2-practice-dentaquest-medicaid-mco": {
    "title": "Nr2 Practice Dentaquest Medicaid Mco",
    "detail": "DentaQuest and other Medicaid MCO dental plans in Kansas require separate workflow from commercial PPO — never reuse Delta or MetLife templates. Verify KanCare MCO assignment and prior auth portal before scheduling SRP or extractions with Dr. Michael Reno.",
    "source": "payer_reference dentaquest + kancare",
    "category": "insurance_narratives"
  },
  "nr2-practice-sunlife-dental-downgrade": {
    "title": "Nr2 Practice Sunlife Dental Downgrade",
    "detail": "Sun Life dental at New Ridge may apply alternate benefit on posterior composites — document extent of caries and cusp involvement like MetLife downgrade playbook. Billing attaches pre-op radiograph for appeal when Sun Life downgrades D2392 to amalgam alternate.",
    "source": "payer_reference sunlife-dental",
    "category": "insurance_narratives"
  },
  "nr2-practice-tax-quarterly-cpa-review": {
    "title": "Nr2 Practice Tax Quarterly Cpa Review",
    "detail": "New Ridge Family Financial quarterly tax rhythm: Steve coordinates book close with QuickBooks P&L import, Dr. Michael Reno reviews production vs collections, and CPA models officer W-2, K-1, and 1040-ES estimates. HAL Taxes page is planning only — not filed returns.",
    "source": "NR2 quarterly tax review",
    "category": "tax_accounting"
  },
  "nr2-practice-tax-kansas-pte-annual": {
    "title": "Nr2 Practice Tax Kansas Pte Annual",
    "detail": "Each fall CPA compares Kansas PTE tax election vs paying on Dr. Michael Reno's K-40 for New Ridge S corp. Entity-level PTE may help when owner is in higher Kansas bracket — decision documented before K-120S filing.",
    "source": "kansas-pte-tax-election + practice entity",
    "category": "tax_accounting"
  },
  "nr2-practice-tax-book-to-tax-bridge": {
    "title": "Nr2 Practice Tax Book To Tax Bridge",
    "detail": "Month-end book-to-tax bridge at New Ridge: QuickBooks P&L categories map to NR2 chart of accounts for CPA prep — dental supplies, lab, payroll, depreciation. Steve flags uncategorized transactions before quarter-end; HAL read-only never posts adjusting journal entries.",
    "source": "accounting_tools + month-end playbook",
    "category": "tax_accounting"
  },
  "nr2-practice-tax-section179-equipment": {
    "title": "Nr2 Practice Tax Section179 Equipment",
    "detail": "Capital equipment purchases at New Ridge (chairs, CBCT, scanner) route through CPA Section 179 or bonus depreciation analysis. Dr. Michael Reno approves major purchases; document business use percentage — HAL cites scorp-section-179-dental-equipment for planning questions.",
    "source": "scorp-section-179-dental-equipment + practice",
    "category": "tax_accounting"
  },
  "nr2-practice-tax-w2-distribution-ratio": {
    "title": "Nr2 Practice Tax W2 Distribution Ratio",
    "detail": "Annual reasonable compensation review for Dr. Michael Reno at New Ridge: CPA targets W-2 officer wages relative to S corp net income before distributions. Under-waged owner-dentist S corps are IRS exam targets — payroll reports and production data support the study Steve gathers…",
    "source": "scorp-reasonable-compensation-dental + provider roster",
    "category": "tax_accounting"
  },
  "nr2-practice-tax-estimated-payment-calendar": {
    "title": "Nr2 Practice Tax Estimated Payment Calendar",
    "detail": "Federal and Kansas estimated tax due dates for Dr. Michael Reno: April 15, June 15, September 15, January 15 (1040-ES schedule). Steve reminders on NR2 Taxes page checklist — coordinate amounts with CPA after each quarter QuickBooks close.",
    "source": "scorp-estimated-tax-1040es + kansas-estimated-tax",
    "category": "tax_accounting"
  },
  "nr2-practice-tax-k1-owner-deadline": {
    "title": "Nr2 Practice Tax K1 Owner Deadline",
    "detail": "New Ridge Form 1120-S and K-120S target March 15 calendar-year filing — K-1s to Dr. Michael Reno before owner 1040/K-40 prep. Extension via Form 7004 does not extend estimated tax due dates; CPA owns filing — HAL explains deadlines only.",
    "source": "scorp-1120s-deadline + kansas-k120s-return",
    "category": "tax_accounting"
  }
};
  let fullById = null;
  let fullLoadPromise = null;
  const syncedAt = "2026-07-09T17:13:47Z";
  const totalCount = 11011;
  const priorityCount = Object.keys(PRIORITY_BY_ID).length;
  const fullIndexUrl = "data/hal-memo-index.json";

  function titleFromId(id) {
    return String(id || "")
      .split("-")
      .filter(Boolean)
      .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
      .join(" ");
  }

  function lookup(id) {
    const key = String(id || "").trim();
    if (!key) return null;
    if (PRIORITY_BY_ID[key]) return PRIORITY_BY_ID[key];
    if (fullById && fullById[key]) return fullById[key];
    return null;
  }

  function loadFullIndex() {
    if (fullById) return Promise.resolve(fullById);
    if (fullLoadPromise) return fullLoadPromise;
    fullLoadPromise = fetch(fullIndexUrl)
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        fullById = (data && data.items) || {};
        return fullById;
      })
      .catch(() => {
        fullById = {};
        return fullById;
      });
    return fullLoadPromise;
  }

  function resolveCitations(ids) {
    return (ids || []).map((id) => {
      const key = String(id || "").trim();
      const row = lookup(key);
      if (!row) {
        return { id: key, title: titleFromId(key), detail: "", source: "", category: "" };
      }
      return {
        id: key,
        title: row.title || titleFromId(key),
        detail: row.detail || "",
        source: row.source || "",
        category: row.category || "",
      };
    });
  }

  return {
    syncedAt,
    count: totalCount,
    priorityCount,
    fullIndexUrl,
    PRIORITY_BY_ID,
    get BY_ID() { return fullById || PRIORITY_BY_ID; },
    titleFromId,
    lookup,
    loadFullIndex,
    resolveCitations,
  };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = HalMemoIndex;
}
if (typeof globalThis !== "undefined") {
  globalThis.HalMemoIndex = HalMemoIndex;
}
