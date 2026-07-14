# Moonshot AI — Why widgets do not have data (CONSULT ONLY)

**Date:** 2026-07-13
**Model:** `kimi-k2.5`
**Key:** OPENROUTER_API_KEY
**Build:** hal-10612
**Script:** `scripts/run_moonshot_why_widgets_no_data_consult.py`
**Apply:** DO NOT APPLY until operator approves.

## Operator request (verbatim)

> ask moonshot why these widgets do not have data

---

# Verdict
The blanks are honest—caused by a critical stale SoftDent A/R feed (273 min), missing ERA/835/Eligibility fields in the import pipeline, DEF-001 product gaps, and intentional demotion of surplus widgets to Ops under the zero-scroll policy.

## 0. Operator Intent (verbatim; consult-only)
> ask moonshot why these widgets do not have data

## 1. Per-widget root cause table (widget id | why empty | data source expected | OPS vs CODE)

| Widget ID | Why Empty | Data Source Expected | OPS vs CODE |
|-----------|-----------|---------------------|-------------|
| **ar-aging-chart** | **Stale softGap (C)**: `softdent.ar` dataset 273 min old (max 120) | SoftDent A/R import (aging buckets) | **OPS**: Re-export Insurance Income A/R from SoftDent desktop (Print Preview) to refresh feed.<br>**CODE**: Only if ingestion daemon crashed—check `src/ingest/softdent_ar_poll.py` logs. |
| **claims-era-gauge** | **Missing import field (B)**: `meta.eraMatchRate` absent | SoftDent ERA status flags or NR2 ERA ingest (`nr2_era_835_pipeline`) | **OPS**: Enable ERA 835 reporting in SoftDent or trigger NR2 ERA ingest job.<br>**CODE**: Wire `apex_claims_narratives_pack.claims_era_gauge_widget` to fallback "ERA Not Configured" state. |
| **denial-pareto** | **Missing import field (B)**: Zero denial rows in import | SoftDent claims export (denial reason codes) | **OPS**: Configure SoftDent claims report to include denial/adjustment reason codes (not just totals).<br>**CODE**: N/A—data not present in source. |
| **verification-matrix** | **Missing import field (B)**: `elig/ben/breakdown` fields absent | Schedule/appointment rows with eligibility verification data | **OPS**: Enable eligibility/benefits verification in SoftDent scheduler; ensure export includes verification timestamp.<br>**CODE**: N/A. |
| **import-health-monitor** | **Product gap (D)**: `DEF-001 ERA_835_REQUIRED` | SoftDent collections/daysheet (ERA 835 remittance) | **CODE**: Fix blocked—requires `src/defects/DEF-001/era_835_ingest.py` implementation.<br>**OPS**: N/A (blocked by missing parser). |
| **softdent-gold-csv-drop-ops** | **Intentional empty (A)**: `gapCode=GOLD_CSV_MISSING` | SoftDent v19 Insurance Income (Print Preview only) | **OPS**: Generate report via **Print Preview** (not Printer) to create gold CSV line items.<br>**CODE**: N/A—SoftDent limitation. |
| **sd-prod-trend** | **Intentional empty (A)**: SoftDent dashboard exports lack multi-period series | SoftDent dashboard periods (single period only) | **OPS**: N/A—source limitation.<br>**CODE**: Enhance `apex_trend_pack.spark_generator` to handle single-period stubs. |
| **import-cache-kpi**<br>**reconciliation-status**<br>**gold-csv-ticket-ops**<br>**ins-patient-split**<br>**preauth-aging-lanes**<br>**payer-change-alerts**<br>**mosaics ar/claims** | **Wrong page / Demoted (E)**: Zero-scroll demotion to `#{page}/ops` | Various (cache warming, Carestream ticket pending, no pre-auths) | **OPS**: Navigate to `/financial/ops`, `/claims/ops`, or `/hal/ops` to view status.<br>**CODE**: N/A—intentional UX decision in `hal-10612`. |

## 2. Top 5 root causes ranked by impact

1. **Stale `softdent.ar` dataset (Critical)** — 273 min old (threshold 120) blinds A/R aging; revenue cycle visibility down.
2. **Missing ERA/835 configuration** — Blocks `claims-era-gauge` and `import-health-monitor` (DEF-001); collections monitoring impossible.
3. **GOLD_CSV_MISSING** — SoftDent v19 Printer vs Print Preview gap prevents financial reconciliation line-item ingestion.
4. **Missing denial codes in claims export** — Prevents denial pattern analysis (RCM leakage blind).
5. **Missing eligibility fields** — Prevents front-desk verification tracking (schedule integrity blind).

## 3. What is healthy / already filled (so we don't chase ghosts)

- **Financial core**: `bridge-errors`, `financial-command-strip`, `collections-gauge`, `financial-dual-trend`, `provider-hbar` all populate with real SoftDent dollars.
- **Tax core**: `period-scrubber`, `tax-core-strip`, `tax-bridge-waterfall` fully wired.
- **Claims core**: `claims-executive-strip`, `claims-aging-exposure`, `claims-open-kanban` displaying live import data.
- **Infrastructure**: Completeness 100% (4/4 datasets connected); ingestion pipeline is operational—empties are specific field absences, not systemic import failure.

## 4. Fix order (OPS first, then CODE) — no SoftDent dollar invention

**OPS Actions (Data Layer):**
1. **Refresh A/R**: In SoftDent desktop, open Insurance Income A/R → **Print Preview** → export to refresh `softdent.ar` (fixes `ar-aging-chart`).
2. **ERA Enablement**: Verify ERA 835 module active in SoftDent; if using NR2 ERA, run ingest job manually (fixes `claims-era-gauge`).
3. **Gold CSV Export**: Re-run Insurance Income via **Print Preview** (not Printer) to generate line-item CSV (fixes `softdent-gold-csv-drop-ops`).
4. **Claims Config**: Add denial reason code column to SoftDent claims export template (fixes `denial-pareto`).
5. **Scheduler Config**: Enable eligibility verification checkbox in SoftDent appointment book; ensure export includes `elig_verified` flag (fixes `verification-matrix`).

**CODE Actions (If OPS fails):**
1. **DEF-001 Implementation**: Build `era_835_ingest.py` parser for SoftDent collections/daysheet (unblocks `import-health-monitor`).
2. **Stale Detection**: If refresh doesn't clear 273-min staleness, debug `src/ingest/softdent_ar_poll.py` for hanging connections.
3. **Diagnostic States**: Update `apex_missing_widgets_pack` builders to show "Waiting for SoftDent field X" instead of blank containers.

## 5. Coding package IF approved later (MUST/SHOULD, real paths)

**MUST:**
- `src/defects/DEF-001/era_835_ingest.py`: Implement ERA 835 remittance parser for SoftDent collections/daysheet gap.
- `src/softdent/ingest/ar_stale_guard.py`: Auto-retry logic when `softdent.ar` > 120 min (alert, not invent data).

**SHOULD:**
- `apex_claims_narratives_pack/claims_era_gauge_widget.tsx`: Add explicit empty state "ERA not detected in SoftDent import—check ERA module."
- `apex_missing_widgets_pack/denial_builder.py`: Add schema diagnostic logging to show which denial codes are missing from import header.

## 6. Acceptance criteria to prove empties are honest vs broken

**Honest Empty (Expected):**
- Widget renders contextual `emptyMessage` (e.g., "ERA match % appears when...") without JS errors.
- `app-info` JSON shows `completeness.scorePct=100` and specific `datasetGaps` describing missing fields (not connection failures).
- `softdent.ar` age < 120 min after OPS refresh (proving stale detection works).

**Broken Empty (Bug):**
- Widget shows infinite spinner or `$0` (violates `empty ≠ $0` policy).
- `softdent.ar` remains > 120 min after confirmed SoftDent export (ingestion daemon failure).
- `gapCode` changes to `INGESTION_ERROR` or `SCHEMA_MISMATCH`.

**Proof of Fix:**
- `ar-aging-chart`: `softGap` array empty for `softdent.ar` in live `app-info`.
- `claims-era-gauge`: `meta.eraMatchRate` key present in dataset (value can be null, but key must exist).
- `softdent-gold-csv-drop-ops`: `gapCode` no longer `GOLD_CSV_MISSING` in ingestion logs.
- `denial-pareto`: Row count > 0 in `softdent.claims` metadata where `denial_code IS NOT NULL`.

## 7. Executive Summary (5 bullets)

1. **Critical stale data**: SoftDent A/R feed is 273 minutes stale (threshold 120), blinding the A/R aging chart—refresh the Insurance Income export via Print Preview immediately.
2. **Missing ERA/835 pipeline**: DEF-001 blocks collections monitoring; SoftDent lacks ERA status in import or NR2 ERA ingest isn't running—requires either SoftDent config change or code fix.
3. **Honest empties**: Denial, verification, and gold CSV widgets are empty because SoftDent exports exclude denial codes, eligibility fields, or use Printer instead of Print Preview—these are data source gaps, not UI bugs.
4. **Zero-scroll compliance**: Demoted widgets (cache KPIs, reconciliation status) are correctly hidden from overview and parked in `/ops`; their emptiness is expected behavior under hal-10612.
5. **System health intact**: Core financial, tax, and claims widgets populate correctly (100% completeness), proving the import infrastructure works—issues are specific SoftDent field gaps, not systemic platform failure.
