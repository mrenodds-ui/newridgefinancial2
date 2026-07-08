# Moonshot Plan Review — Summary Report

**Date:** 2026-07-07  
**Reviewer:** kimi-k2.5 (Moonshot API)  
**Plan reviewed:** [MOONSHOT_IMPLEMENTATION_PLAN_2026-07-07.md](./MOONSHOT_IMPLEMENTATION_PLAN_2026-07-07.md)  
**Full Moonshot response:** `.local_logs/moonshot_financial_eval/MOONSHOT_PLAN_REVIEW_2026-07-07.md`

---

## Verdict

**AGREE WITH MODIFICATIONS**

Moonshot accepts the plan’s direction (mockup-as-spec, validator gates, page-scoped phases, Workstation deferred) but wants **reordering and extra gates** before Phases 1, 4, and 5.

---

## Alignment matrix

| Plan element | Moonshot | Engineering note |
|--------------|----------|------------------|
| Phase 1 QuickBooks first | **Disagrees** — prefers Phase 3 (HAL/`app.js`) first | Valid if `app.js` ms-hal-* changes touch shared scroll/nav; grep `app.js` before deciding |
| Phase 2 SoftDent funnel + operatory | Agrees | Add data contract for operatory export fields before coding |
| Phase 3 HAL + command chips | Agrees — but should run **earlier** | Renamed to “Phase 0” in Moonshot’s recommendation |
| Phase 4 Chart bridge | **Conditional** — spike required first | Canvas vs inline SVG coexistence unproven; risk is real |
| Phase 5 SideNotes hub | **Conditional** — protocol doc first | Loopback POST exists elsewhere; need origin/token pattern |
| Phase 6 Workstation CSS | Agrees (optional) | No change |
| Validator gates every phase | Strongly agrees | Keep as-is |
| Mockup gallery acceptance | Strongly agrees | Keep as-is |

---

## Moonshot’s recommended order

```
Phase 0 (was 3)  HAL cleanup + app.js selector stabilization  →  hal-10057
Phase 1          QuickBooks mockup parity                     →  hal-10055
Phase 2          SoftDent funnel + operatory                  →  hal-10056
Phase 4          Charts — ONLY after feasibility spike
Phase 5          SideNotes hub — ONLY after protocol doc
Phase 6          Workstation CSS (optional)
```

**First approval:** Phase 0/3 (HAL cleanup), not Phase 1.

---

## Required modifications (Moonshot)

1. **Run HAL/`app.js` cleanup before QB/SoftDent** — or explicitly freeze `app.js` during Phases 1–2.
2. **Phase 4 spike** — prototype `NR2Charts` inside a PageCanvas host before full bridge.
3. **Phase 5 protocol** — document 8766→8765 POST (origin, auth, offline behavior).
4. **Phase 1.4 schema split** — Moonshot asks for `localStorage` migration; **codebase check:** no widget layout in `localStorage` found — still update HAL/sub-nav references when splitting `quickbooksExpenseBreakdown`.
5. **Phase 2.2 API contract** — define operatory data shape from SoftDent export before UI.
6. **Feature flag for command chips** — e.g. `NR2_FLAGS.hal_commands` for gradual rollout.
7. **Extend audit script before Phase 1** — add QB class assertions as baseline, not after.

---

## Risks Moonshot says we understated

| Risk | Plan rating | Moonshot rating |
|------|-------------|-----------------|
| HAL rename / `app.js` selector breaks sub-nav | Low | **Medium** |
| Canvas + SVG chart collision (Phase 4) | Low | **High** |
| SideNotes hub CSRF (Phase 5) | (not listed) | **Medium** |
| QB widget key split | Medium | Medium (localStorage concern overstated for NR2) |
| Mockup vs empty/error states | (not listed) | Low–Medium |

---

## Revised approval recommendation

| Item | Moonshot | Suggested operator action |
|------|----------|---------------------------|
| **Approve now** | Phase 0 (HAL cleanup) | ☐ Yes — implement first |
| **Approve after Phase 0** | Phase 1 QuickBooks | ☐ Yes |
| **Approve with data spec** | Phase 2 SoftDent | ☐ Yes after operatory field list |
| **Defer** | Phase 4 Charts | Until spike passes |
| **Defer** | Phase 5 SideNotes hub | Until protocol doc |
| **Optional** | Phase 6 Workstation | ☐ Only if requested |

---

## Bottom line

Moonshot **does not disagree** with *what* to build — it disagrees with **when**. Stabilize HAL/shared runtime first, then QuickBooks and SoftDent visual parity, then charts and cross-port SideNotes only after technical spikes and security notes.

**Consensus first slice:** Phase 0 — HAL cleanup (`app.js` + `hal-page.js` ms-hal-* purge, validator green) → then Phase 1 QuickBooks.
