# Moonshot AI — Expert SE: Issues, Structure, First-Class Bar (CONSULT ONLY)

**Date:** 2026-07-13  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Status:** ok  
**Build:** hal-10576  
**Prior:** HAL-10587 TP estimate chips (`6cf8913`)  
**Script:** `scripts/run_moonshot_expert_se_first_class_program_consult.py`  
**Apply:** DO NOT APPLY until operator approves (`proceed`).

## Operator request (verbatim)

> as an expert software enginer ask moonshot ai what you need to know about this programs issues, recommendations and structure and anything else that woul make this a 1st class highly profienct profesional program

---

# Verdict
NR2 is architecturally sound on PHI containment and read-only honesty, but critically compromised by data famine (zero gold insurance payment lines) and build hygiene failure (11-version drift). The sophisticated InsCo×ADA probabilistic stack is operating on 2% usable catalog cells and unvalidated fallback assumptions, making it a liability rather than an asset until ground truth data flows.

## 0. Operator Intent (verbatim)
> "as an expert software enginer ask moonshot ai what you need to know about this programs issues, recommendations and structure and anything else that woul make this a 1st class highly profienct profesional program"

## 1. What Moonshot Needs To Know (discovery checklist — unknowns that matter)
- **Root cause of data famine**: Why is `sd_insurance_payment_lines=0`? Is this an ETL extraction failure, schema version mismatch, or truly zero payments recorded in SoftDent?
- **Test coverage depth**: What is the line-level code coverage % for the 276 modules? Are the 122 tests unit, integration, or end-to-end?
- **Excel export reliability**: How is the "desktop Excel/Print Preview" financial truth pipeline automated? Is it manual, scripted, or scheduled?
- **HAL performance under load**: What is the p99 latency for 24B inference with 550k transactions in the context window?
- **Version drift mechanism**: Why does `BUILD_ID` lag package IDs by 11 versions (hal-10576 vs 10587)? Is this a CI artifact tagging issue or deployment skew?
- **Exact usable validation**: Have the 46 "exact usable" cells been manually validated against actual EOBs/remittance, or are they statistical artifacts?
- **Disaster recovery**: What is the RTO/RPO for the local 32GB GPU HAL state if the workstation fails?
- **Empty vs $0 enforcement**: Is the `empty != $0` rule enforced programmatically in the UI layer, or is it a documentation-only policy?

## 2. Program Structure Diagnosis (data planes, HAL, SoftDent/QB, honesty)
**Data Planes**: Split-truth architecture with SoftDent ODBC (metadata) and Excel/Print Preview (financial ground truth). This creates a synchronization hazard where the probabilistic models (HAL-10582/83) consume ODBC-derived ledger episodes while the actual dollars live in Excel extracts.

**HAL Coupling**: Synchronous Bottle TLS loopback (single-threaded) pins the GPU-resident 24B model behind blocking HTTP calls. The 32GB AMD card is underutilized; inference should be async with request queuing.

**Honesty Gates**: Correctly implements read-only overlay (no SoftDent write-back) and distinguishes null from zero. However, the "insufficient" catalog tier (2111/2274 cells) risks presenting statistical noise as data without clear UI differentiation.

**Version Integrity**: Build system decoupled from package manifest. The 11-version drift indicates CI/CD hygiene failure that compromises rollback safety and reproducibility.

**Test Pyramid**: 0.44 tests/module indicates inverted pyramid (likely top-heavy integration tests). Financial probabilistic logic lacks unit-level safety nets.

## 3. Ranked Issues

| ID | Severity | Area | Issue | Evidence | Why it blocks 1st-class |
|---|---|---|---|---|---|
| **DATA-001** | **MUST** | Data Integrity | Gold payment lines empty | `sd_insurance_payment_lines=0` | Probabilistic models (10582/83) are unvalidated; staff sees fallback guesses masquerading as estimates |
| **VER-001** | **MUST** | Build Integrity | Version drift | BUILD_ID hal-10576 vs packages 10587 | Cannot reproduce builds, rollback integrity compromised, debugging ambiguity |
| **TEST-001** | **MUST** | Quality Assurance | Insufficient test density | 276 modules / 122 tests = 0.44 ratio | Financial logic changes risk undetected regression; no safety net for probabilistic $ calculations |
| **DATA-002** | **SHOULD** | Data Quality | Catalog sparsity | 46 exact usable / 2274 total (2%) | Staff sees "insufficient" badges 98% of time; UX investment (10587) yields minimal utility |
| **ARCH-001** | **SHOULD** | Scalability | Synchronous HAL blocking | Single-threaded Bottle, GPU-resident 24B | UI latency under load; HAL GPU underutilized due to blocking I/O |
| **HON-001** | **NICE** | Compliance | Empty/$0 distinction unverified | Rule documented but no enforcement proof | Risk of misleading financial displays if null renders as "$0.00" in edge cases |

## 4. Recommendations to Reach First-Class

| ID | Rank (MUST/SHOULD/NICE) | Recommendation | Why | Effort | Depends on |
|---|---|---|---|---|---|
| **FIX-001** | **MUST** | Audit and repair insurance payment line ETL | Gold data required to validate 10582/83 models; without it, the spine is fiction | Medium | SoftDent Collections/Daysheet export access |
| **FIX-002** | **MUST** | Implement BUILD_ID/package version coupling | Reproducible builds, rollback safety, debugging clarity | Low | CI/CD pipeline access |
| **FIX-003** | **MUST** | Achieve >80% line coverage on financial modules | Prevent regression in probabilistic logic; required for professional financial software | High | Test fixtures with sanitized SoftDent data |
| **ENH-001** | **SHOULD** | Async HAL invocation layer (ASGI/Quart) | Prevent Bottle blocking on 24B inference; improve throughput | Medium | Refactor of Apex JS shell and Bottle routes |
| **ENH-002** | **SHOULD** | Catalog cell validation protocol | Manually verify the 46 "exact usable" cells against actual EOBs to confirm model accuracy | Medium | Access to historical remittance data |
| **ENH-003** | **NICE** | Automated SoftDent Excel export scheduler | Remove manual step in financial truth pipeline; reduce sync hazard | Medium | Windows Task Scheduler or RPA integration |

## 5. Target Architecture Sketch (what “professional” looks like for NR2)
- **ASGI API Layer**: Quart or FastAPI with async HAL calls, request queuing, and health probes
- **Immutable Builds**: Docker containers or pinned Python envs with `BUILD_ID` derived from git tag (HAL-10587 → hal-10587)
- **Dual Data Validation**: SoftDent ODBC (metadata) + Excel extracts (financial truth) with checksum validation; reject imports if checksum mismatch
- **Local HAL with Queue**: GPU inference async with Redis/RabbitMQ job queue; 24B model state snapshotted to NAS hourly
- **Test Pyramid**: 80% unit (pytest), 15% integration (Bottle/HAL), 5% E2E (Apex shell)
- **Honesty Enforcement**: Type system distinguishes `NullDollar` from `ZeroDollar`; UI components render "—" vs "$0.00" based on type, not value

## 6. Suggested NEXT package (ONE) if operator says proceed
**HAL-10588 "Gold Data Pipeline Audit & Repair"**
Focus: Investigate `sd_insurance_payment_lines=0` root cause, implement automated SoftDent Collections/Daysheet Excel export ingestion, and validate the 46 exact usable cells against actual remittance data. Do not proceed with additional UX surfaces until gold data flows.

## 7. Acceptance criteria for “1st-class”
- [ ] `sd_insurance_payment_lines > 0` (actual gold data flowing and validated against 10+ historical remittances)
- [ ] `BUILD_ID` matches highest package ID with zero drift (hal-10588 → BUILD_ID hal-10588)
- [ ] Line coverage >80% for `softdent_insco_ada_*.py` and `softdent_treatment_planning.py`
- [ ] All financial displays programmatically enforce `empty != $0` (audit log proves no null rendered as $0.00 in last 30 days)
- [ ] HAL inference latency p95 <500ms under load of 10 concurrent requests
- [ ] Catalog exact usable cell count >200 (from current 46) or documented acceptance of statistical inference thresholds
- [ ] Automated daily SoftDent financial export with checksum verification

## 8. Executive Summary (7 bullets)
- NR2 has enterprise-grade probabilistic models (HAL-10580-10587) but feeds them zero ground truth data (`sd_insurance_payment_lines=0`).
- Version drift (11 builds behind) indicates CI/CD hygiene failure that compromises deployment safety.
- Test coverage (0.44 tests/module) is half the industry standard for financial software.
- Architecture correctly contains PHI locally but wastes GPU resources with synchronous blocking I/O.
- 98% of the insurance catalog is statistically insufficient, rendering the TP chip UX largely informational rather than actionable.
- The "empty != $0" honesty rule exists in documentation but lacks programmatic enforcement verification.
- Professional status requires gold data pipeline repair before any further algorithmic or UX investment.

## 9. Approval checklist
- [ ] Operator confirms **CONSULT-ONLY** (no code generated or applied)
- [ ] Data pipeline root cause analysis plan approved (why payment lines=0)
- [ ] Version drift remediation (FIX-002) approved
- [ ] Test coverage baseline measurement approved
- [ ] HAL-10588 scope (Gold Data Pipeline) approved as next package