# MOONSHOT APPLIED — 32B program fixes (2026-07-13)

Shippable slice from the 32B diagnosis. Keeps hard `hal-local:32b` only. Does **not** invent Carestream Gold payment lines.

## Shipped

### A — Import/cache progress UX
- Warming-bridge status widget renders a visible **fill % bar** (`showFillProgress` / `fillProgress`).
- Meta + HAL header show warming / Sync %, not console-only.
- Sync trigger returns `fillProgress` and audits as kind `sync`.
- Financial + HAL mosaics surface **Import cache KPIs** (live / stale / warming / fillFailures).

### B — SoftDent × QB reconciliation
- `ensure_reconciliation_env()` defaults `NR2_RECONCILIATION=1` when unset.
- `reconciliation_surface_widget()` always shown on Financial/HAL; when imports are not fresh, message stays honest pending (empty ≠ $0).
- No fake unified SoftDent/QB schema.

### SoftDent Excel ↔ QB field mapping gaps (honest note)

| SoftDent (desktop Excel / exports) | Approx QB / NR2 target | Gap |
|------------------------------------|------------------------|-----|
| Trans for a Period / account tx CSV | deposit / collections mirrors | Date/code/amount join only; patient keys often diverge |
| PRODBYADA / production dashboard | `v_production_vs_payroll` | SoftDent production ≠ QB payroll dollars; ratio threshold only |
| Collections / daysheet | `v_collection_vs_ap` | payer “Insurance” generic vs QB AR/AP categories |
| A/R aging buckets | QB AR aging (if exported) | bucket labels may not align 1:1 |
| Insurance Income Print Preview totals | Gold/`sd_insurance_payment_lines` | **No Excel** on v19.1.4 — Carestream CSV still missing |

### C — Bridge errors rollup
- Compact **Bridge errors** widget rolls up blocking import diagnostics, quarantine count, widget fill failures, last Sync error.
- Fail-open: clean = ok message; never invent `$0` success from empty data.

### D — Audit + import scrub
- `nr2_audit_log.FINANCIAL_MUTATION_ACTIONS` adds `financial_override`, `consent_action`, `sync`, `claim_action`, `hal_outbound_consent`.
- HTTP `_audit_mutation` maps consent/outbound/claim paths into those kinds.
- `import_sync._scrub_void_and_dupe_ledgers` drops void markers + exact fingerprint dupes; summary on `filterSummary` / diagnostics.

### E — Gold CSV OPS (non-invent)
- Ticket doc refreshed: pack path, portal, pending `carestreamCaseNumber`, drop → Sync → settlement.
- HAL `policy:gold-csv-drop-ops` uses extended staff reply (`gold_csv_ops_staff_reply`).
- Mosaic **Carestream Gold CSV ticket** chip; gapCode stays `GOLD_CSV_MISSING` until file arrives.

## Explicitly not done
- Cloud / non-32B HAL fallback
- Invented Insurance Income line items
- Full SoftDent/Carestream/QB schema unification
- HAL chat IndexedDB persistence across browser restarts

## Validation
- `python -m unittest test_32b_program_fixes.py`
- Manual: restart app → Sync shows progress → Financial shows recon / bridge errors / cache KPIs → Gold chip empty-not-invented
