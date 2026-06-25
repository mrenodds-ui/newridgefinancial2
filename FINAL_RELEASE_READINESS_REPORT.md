# Final Release Readiness Report

Generated: 2026-06-25 (UTC)

## Status

**Ready**

Sections 1–5 repair/audit work is complete and the critical business rules are covered by targeted tests, CI gates, and documentation. The prior backend-suite caveat (8 order-dependent HAL/SoftDent snapshot failures) was resolved in `f574342` (`test: stabilize SoftDent snapshot expectations`) by pinning dashboard-dependent assertions to a committed canonical fixture instead of the mutable `app/data/imports` snapshot. Full backend `pytest app/tests` and CI regression gates now pass on this workstation.

## Validation Summary

| Command | Result | Notes |
| --- | --- | --- |
| `git status --short` | **Pass** | Tracked tree clean at closeout start |
| `pytest app/tests -q` | **Pass** | **437 passed** (~17m 31s; after `f574342`) |
| `python scripts/run_ci_gates.py` | **Pass** | `overall_pass: true` (~3m 46s; after `f574342`) |
| `cd frontend && npm run typecheck` | **Pass** | |
| `cd frontend && npm run test` | **Pass** | 26 files, 125 tests (~14s) |
| `git diff --check` | **Pass** | |
| `bash -n scripts/run_frontend_model.sh` | **Pass** | |
| `bash -n scripts/run_backend_model.sh` | **Pass** | |
| PowerShell `-Help` / `-WhatIf` script checks | **Pass** | frontend/backend model scripts, `run_235b_isolated_section.ps1`, `stop_235b_evaluator_lane.ps1` |

### Backend-suite caveat (resolved)

The 8 HAL/SoftDent snapshot failures reported at initial closeout were order-dependent: tests read the mutable `app/data/imports/softdent` snapshot, which other tests in the same session could rewrite. Fixed in `f574342` via `canonical_softdent_dashboard` fixture and `app/tests/fixtures/softdent_dashboard_canonical.json`. No runtime or business-rule changes.

## Section Summary

### Section 1 — Backend financial pipeline / SoftDent A/R correctness

**Findings fixed**

- Dental A/R sourced only from explicit SoftDent A/R export (no `production - collections` synthesis)
- Widget feed derived from imported financial summary; misleading SUCCESS on empty imports reduced
- Widget update ingestion hardened (size limits, schema validation)

**Key commits**

- `f5b6b82` source dental A/R from SoftDent
- `3149d7e` remove legacy synthetic dental A/R
- `2181958` derive dashboard widgets from imported data
- `76a9dae` harden widget update ingestion
- `b20c926` HAL widget pipeline

**Validation**

- `app/tests/test_services_kpi_data.py`, `app/tests/test_endpoints.py`, `app/tests/test_widget_builder.py`, `app/tests/test_ci_softdent_ingest_check.py`

**Deferred**

- Widget feed disk-write failure rollback (no test; low operational risk)
- Widget ingest vs import-cache cross-check test (optional)

---

### Section 2 — Frontend dashboard/widget A/R rendering

**Findings fixed**

- Missing A/R shows **Unavailable**, not fake `$0`
- FinancialDashboard gates receivables widget values on `latestAr` availability
- SoftDent and A/R collection pages distinguish unavailable vs real zero

**Key commits**

- `e561af4` unavailable state for missing A/R
- `c4070c8` unavailable SoftDent A/R aging
- `ef3845f` gate receivables widget values on SoftDent A/R availability

**Validation**

- `frontend/src/__tests__/FinancialDashboard.widgets.test.tsx`
- `frontend/src/__tests__/ARCollectionsPage.test.tsx`
- `frontend/src/__tests__/SoftDentPage.test.tsx`
- Frontend typecheck + vitest: **pass**

**Deferred**

- MSW default `handlers.ts` always supplies `latestAr.available: true` (low; page-level tests cover null A/R)

---

### Section 3 — Local AI routing/runtime

**Findings fixed**

- Dual-lane routing: frontend `:11434` / backend `:11435`
- Second opinion uses backend lane
- LiteLLM aliases lane-split; dynamic URL resolution
- A/B eval routing lane-aware; shell/script defaults aligned
- 235B evaluator workflow isolated on `:11436`

**Key commits**

- `cb547e7` dual-lane local quantized AI routing
- `b2abdcc` second opinion through backend
- `c4d9717` … `84f398c` lane routing, scripts, tests

**Validation**

- `app/tests/test_model_routing.py`, `test_local_ai_config.py`, `test_litellm_config.py`, `test_second_opinion_routing.py`, `test_local_model_scripts.py`, `test_control_routes.py`
- Script syntax/help checks: **pass**

**Deferred**

- None blocking release for normal 24B/30B runtime

---

### Section 4 — Security/config/deployment hardening

**Findings fixed**

- Unset `APP_ENV` is production-like
- `WIDGET_API_KEY` required outside explicit dev/test
- `APP_AUTH_SESSION_SECRET` required outside dev/test
- `.env.example` safer defaults; eval artifacts gitignored
- LiteLLM proxy auth documented; startup warning without `LITELLM_MASTER_KEY`

**Key commits**

- `d9d6d79` harden security defaults
- `5a10aa4` ignore local eval artifacts
- `e294c1f` document production security contracts

**Validation**

- `app/tests/test_endpoints.py` (widget auth, session secret validation)
- `docs/API.md`, `README.md`, `.env.example`

**Deferred**

- None from Section 4 Medium/Low scope

---

### Section 5 — Tests/docs/release readiness

**Findings fixed**

- CI gate pytest wrappers added and wired in GitHub Actions
- `docs/API.md` security contracts documented
- README production env checklist documented
- Receivables widgets cannot be `SUCCESS` without explicit SoftDent A/R

**Key commits**

- `a1fcfc8` wire CI regression gates
- `e294c1f` document production security contracts
- `f291048` downgrade receivables widgets without A/R

**Validation**

- `app/tests/test_ci_route_wiring.py`, `test_ci_softdent_ingest_check.py`
- `python scripts/run_ci_gates.py`: **pass**
- `.github/workflows/test.yml` `ci-gates` job

**Deferred**

- Root `test:all` orchestration script (low)

## Critical Business Rules Verified

| Rule | Evidence |
| --- | --- |
| Dental A/R only from explicit SoftDent A/R export | `test_services_kpi_data.py`, `test_endpoints.py` (`latestAr` null paths), `f5b6b82` / `3149d7e` |
| Missing A/R unavailable/null, not synthetic or fake `$0` | Backend widget builder tests; frontend `ARCollectionsPage`, `SoftDentPage`, `FinancialDashboard.widgets` tests |
| No demo KPIs in unavailable SoftDent paths | Endpoint + widget builder tests with missing `latestAr` |
| Widgets cannot imply healthy receivables without A/R | `f291048`, `test_widget_builder.py`, `test_endpoints.py` widget-update gating |
| Frontend distinguishes real zero vs unavailable | Frontend widget/page tests |
| Frontend lane `:11434` → `mistral-small3.1:24b` | `test_local_ai_config.py`, `test_model_routing.py`, scripts |
| Backend lane `:11435` → `qwen3:30b` | Same |
| Second opinion uses backend lane | `test_second_opinion_routing.py` |
| LiteLLM aliases lane-split | `test_litellm_config.py` |
| A/B eval routing lane-aware | `test_local_model_ab_eval.py` |
| Evaluator `:11436` / `qwen3:235b` isolated | Docs + `run_235b_eval_section.py --isolated`; not in normal aliases |
| Lane-distinct test mocks | `lane_routing_test_helpers.py`, `84f398c` |
| Unset `APP_ENV` production-like | `test_endpoints.py`, `app/config_runtime.py` |
| `WIDGET_API_KEY` outside dev/test | `test_endpoints.py` widget auth tests |
| `APP_AUTH_SESSION_SECRET` outside dev/test | `test_endpoints.py` `validate_auth_configuration_*` |
| LiteLLM exposure documented + warns | `scripts/start_litellm_proxy.ps1`, `docs/API.md`, `README.md` |
| Eval artifacts gitignored | `.gitignore`, `5a10aa4` |
| CI gates wired | `a1fcfc8`, `.github/workflows/test.yml`, `run_ci_gates.py` pass |
| Production/security docs | `e294c1f` |
| Section 5 receivables widget gap fixed | `f291048` |

## Security/Config Readiness

Production/staging checklist (see `README.md` and `docs/API.md`):

- `APP_ENV=production` (unset is production-like)
- `APP_AUTH_USERS_JSON` (generated per environment; no example hashes)
- `APP_AUTH_SESSION_SECRET` (required in production-like envs)
- `WIDGET_API_KEY` (required for widget updates outside dev/test localhost)
- `LITELLM_MASTER_KEY` when proxy is used beyond localhost
- Local AI lane URLs/models: `AI_*` / `OLLAMA_*` defaults documented in `.env.example`

235B eval artifacts (`235b_*`, legacy eval runners) are gitignored and should not be committed unless sanitized.

## Local AI Runtime Readiness

| Lane | Port | Default model | Use |
| --- | --- | --- | --- |
| Frontend | `:11434` | `mistral-small3.1:24b` | User-facing chat |
| Backend | `:11435` | `qwen3:30b` | HAL server tasks, second opinion |
| Evaluator (isolated) | `:11436` | `qwen3:235b` | Offline section audits only |

Normal runtime must **not** depend on `:11436`. Long-running lane scripts are foreground processes (`run_frontend_model.ps1`, `run_backend_model.ps1`).

## Remaining Deferred Items

Non-blocking, intentional or environmental:

1. **Widget feed disk-write failure** path still logs-and-continues (no rollback test).
2. **MSW default `latestAr.available: true`** in `handlers.ts` (page tests cover null A/R).
3. **No single root `test:all` script** chaining backend pytest + frontend vitest + CI gates (documented separately in README/regression docs).

## Recommended Next Product Work

- Insurance narrative case-packet builder
- AI citation/source audit layer
- Optional heavy second-opinion model bakeoff
- Financial page UX improvements
