# Moonshot MUST plan — compare report (CONSULT ONLY)

**Date:** 2026-07-13  
**Plan:** hal-10611 MUST (build skew + port-aware singleton + financial empty omit)  
**Moonshot coding:** [`MOONSHOT_MUST_PLAN_CODING_RESPONSE_2026-07-13.md`](MOONSHOT_MUST_PLAN_CODING_RESPONSE_2026-07-13.md)  
**Apply:** DO NOT APPLY until operator approves.

## Operator request (verbatim)

> now give plan to moonshot and ask for code and compare then report

## Verdict

**Moonshot accepted our plan** and returned surgical diffs that honor hard constraints (real PIDFILE, no psutil, no SoftDent invent, `status=="empty"`). Apply with **two corrections**: (1) clean the duplicate `bind_host` hunk in `browser_app.py`, (2) **do not exempt all `type=="status"`** from financial empty-omit or the main empty offenders stay.

## Constraint score (manual review)

| Check | Result | Detail |
|-------|--------|--------|
| Accept plan / hal-10611 | PASS | Verdict: Accept plan; bumps JSON + BUILD_ID + ASSET_V |
| Real PIDFILE `.nr2_browser_app.pid` | PASS | Explicitly kept; rejects invented path |
| No psutil | PASS | Uses `socket.bind` probe |
| No SoftDent invent scheduler | PASS | Explicitly out of scope / rejected |
| `status=="empty"` omit | PASS | Uses `w.get("status") == "empty"` |
| Compact pack wire | PASS | Extends `apply_collapse_empty_all(..., page=)` + call site |
| Unified diffs | PASS | Complete for 5 files |
| Financial omit effectiveness | **REVISE** | Exempt set includes `"status"` — keeps empty status chips (import-cache-kpi, gold ticket, etc.) |

**Score: 7/8 hard constraints; 1 apply revision required.**

## Plan vs Moonshot

| Topic | Cursor plan | Moonshot | Match |
|-------|-------------|----------|-------|
| Build | hal-10611 across apex / JS / `nr2-build.json` | Same | Yes |
| Singleton | Port-aware, real pidfile, stdlib only | `_port_available` + move call after bind_host | Yes (with hunk fix) |
| Listener PID rewrite after bind | Plan asked for rewrite when child ≠ parent | Response mostly bind-probe before claim; weaker on post-bind rewrite | Partial |
| Financial omit | Omit empty **analysis/gap/scatter/pipeline** surfaces; keep intentional strips | Filters `status=="empty"` but exempts `status`, `analysis`, `gap` types | Partial — **too broad exempt** |
| SoftDent A/R | OPS Excel/Print Preview | Agree out of scope | Yes |
| Tests | `test_hal10611_program_coherence.py` | Acknowledged; no full test body in response | Partial |

## Hard disagreements / apply fixes

1. **`exempt_if_empty` includes `"status"`** — defeats omit for empty status tiles that drive Financial clutter.  
   **Apply fix:** exempt only strip/command types (`financial-command-strip`, `executive-strip`, `import-freshness`, etc.). Omit empty `kpi` / chart / scatter / pipeline / bridge / non-strip status by id prefix or type allow-list for omit.

2. **`browser_app.py` diff duplicates `bind_host = ...`** — apply cleanly once, then call `ensure_singleton(bind_host, http_port)`.

3. **Post-bind pidfile rewrite** — Moonshot weak here; keep plan step to rewrite PIDFILE to listening process after server starts if parent/child split persists.

## What both agree NOT to do

- No `psutil`
- No `schedule_softdent_ar_refresh`
- No wrong pidfile under `data/`
- No `w.get("empty")` invent filter
- SoftDent A/R truth stays desktop OPS

## Recommended merge (if operator says proceed)

1. Take Moonshot diffs for `nr2-build.json`, `BUILD_ID`, `ASSET_V`, compact-pack `page=` wire.  
2. Fix singleton hunk (dedupe bind_host; keep socket probe).  
3. Narrow financial empty exempt set (reject blanket `"status"` exemption).  
4. Add tests + restart gates as in plan.  
5. SoftDent A/R: staff OPS only.

## Approval checklist

- [ ] Accept merge path above (plan scaffold + Moonshot diffs + two corrections)
- [ ] SoftDent A/R OPS acknowledged
- [ ] Proceed apply as **hal-10611**

## Sources

- Plan: `.cursor/plans/moonshot_program_must_plan_96cd9264.plan.md`
- Moonshot coding: `NewRidgeFinancial2/docs/MOONSHOT_MUST_PLAN_CODING_RESPONSE_2026-07-13.md`
- This report: `NewRidgeFinancial2/docs/MOONSHOT_MUST_PLAN_COMPARE_REPORT_2026-07-13.md`
