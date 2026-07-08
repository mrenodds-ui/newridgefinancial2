# Plan Comparison Report — Cursor Agent vs Moonshot AI

**Date:** 2026-07-08  
**Build:** hal-10085  
**Agent plan:** [MOONSHOT_DETAIL_PLAN_REPORT_2026-07-08.md](MOONSHOT_DETAIL_PLAN_REPORT_2026-07-08.md)  
**Moonshot sources:** Prior live consultations (kimi-k2.5 / codebase audit, 2026-07-07–08) — see note below  
**Comparison script:** `scripts/run_moonshot_plan_comparison.py`

---

## API status (live ask attempt)

| Endpoint | Result |
|----------|--------|
| `api.moonshot.ai` | **401** Invalid Authentication (`MOONSHOT_API_KEY` — 23 chars, likely stale) |
| `openrouter.ai` | **401** Missing Authentication header (`OPENROUTER_API_KEY` present but rejected in this shell) |

**Live Moonshot review of the agent plan could not be completed.** This report compares the agent plan against **Moonshot's documented prior positions** in:

- `MOONSHOT_SOFTDENT_EXTRACT_REPORT_2026-07-08.md`
- `MOONSHOT_QB_SOFTDENT_SIDENOTES_REPORT_2026-07-07.md`
- `MOONSHOT_FULLEST_EXTENT_REPORT_2026-07-08.md`
- `MOONSHOT_COMPREHENSIVE_CONSULT_2026-07-08.md`

Regenerate API keys and rerun `py -3.14 scripts/run_moonshot_plan_comparison.py` for a fresh kimi-k2.6 review.

---

## Executive verdict

| Reviewer | Verdict |
|----------|---------|
| **Cursor agent plan** | Post-ceiling roadmap: 10 commits (hal-10086–10095), Phases A–G, data + workflow first |
| **Moonshot (prior reports)** | **CONDITIONAL APPROVE** on direction; **not ready for daily use** until data contracts + hub sign-off; payment fix is **highest ROI** |

**Alignment: ~85%** — Moonshot and the agent plan agree on *what* matters (payments, operatory contract, hub test, QB empty states, no ODBC before bridge lane fixed). They differ mainly on *ordering* (agent adds repo hygiene + narrative UI earlier; Moonshot elevates operatory/hub blockers and widget wiring before ODBC).

**Recommended merged order** is at the bottom of this document.

---

## 1. Agreement — what the agent plan got right

Moonshot prior reports **support** these agent plan items:

| Agent plan item | Moonshot evidence |
|-----------------|-------------------|
| **Phase B — payment/adjustment fix (P0)** | SoftDent extract report Phase 1: "1 commit, highest ROI"; align `_is_payment()` with codes `2`, `51`, `52`; parse `register_for_period.jsonl` |
| **Phase C — procedures + operatory exports** | QB/SoftDent report blocker #1: "operatory data contract + dedicated export"; extract report lists `operatory_schedule.json`, `softdent_procedures_export.csv` |
| **Phase E — QB empty states + deposit variance** | QB report wants "Awaiting QuickBooks sync"; extract report Phase 5: HAL compare collections vs QB deposits |
| **Phase G — hub sign-off** | QB/SoftDent report blocker #2: origin + token + manual Everyone→8765 badge test within ~15s |
| **Phase F — ODBC optional / later** | Extract report ranks ODBC as Lane 3 after financial exports + daysheet fix; "not configured" is expected until operator setup |
| **Phase D — narratives from clinical notes** | Extract report lists `softdent_clinical_notes_data.json` + procedures CSV for narratives; fulle extent report cites data depth over chrome |
| **16 GB GPU — pin 8B, 24B on demand** | Consistent with `model-automation/README.md`; Moonshot never recommended pinning 30B+ on 16 GB |
| **No React, no writeback, no auto-submit** | All Moonshot docs preserve read-only boundary |
| **Deprioritize stale bridge** | Extract report: `SoftDentBridge\exports` is legacy; `SoftDentFinancialExports` is primary |

---

## 2. Disagreements or corrections

| Topic | Agent plan | Moonshot position | Resolution |
|-------|------------|-------------------|------------|
| **First commit** | Phase A: repo hygiene, push origin (hal-10086) | Moonshot never prioritized git push; wants **payment fix or operatory contract** first | **Split A:** push origin is 30 min operator task; **first code commit = payment fix** (Moonshot wins on engineering priority) |
| **Widget wiring before ODBC** | Agent Phase B then C; Phase F ODBC late | Moonshot extract **Phase 2** explicitly: wire analytics DB → widgets when `sd_*` empty | **Add hal-10087b:** point widgets at `daysheet_totals` / `transactions` as fallback — agent plan mentions this implicitly in B but Moonshot makes it explicit as separate commit |
| **Narrative UI timing** | Phase D (commits 5–7) before hub sign-off | Moonshot **blockers** are operatory + hub before "daily operator use" — narratives not in blocker list | **Hub + operatory empty state before or parallel to narrative UI**, not after |
| **10-commit scope** | hal-10086 through hal-10095 | Moonshot extract roadmap is **5 phases**, not 10 builds | Agent plan is finer-grained; acceptable if each commit stays small |
| **Legacy archive** | Phase A archive `_legacy` | Moonshot silent; extract report doesn't require delete | **Port `insurance_narratives` first** — Moonshot would flag deleting before port |
| **QB F5 overlay test** | Phase E | Moonshot QB report: manual F5×5 **before ship** — earlier than agent Phase E | **Move to Phase A sign-off checklist**, not a dedicated commit |
| **Conditional approve status** | Agent assumes hal-10085 shippable for presentation | Moonshot still says **CONDITIONAL APPROVE** for daily ops (data + hub) | Presentation shipped; **daily ops not signed off** until merged roadmap done |

---

## 3. Missing items — agent plan omitted

Moonshot prior reports add these (not explicit in agent plan):

| Missing item | Moonshot source | Suggested add |
|--------------|-----------------|---------------|
| **Wire analytics DB when sd_* empty** | Extract Phase 2 | Commit hal-10087b between payment fix and procedures |
| **Funnel math validation** | QB/SoftDent operator checklist: Accepted ≤ Presented | Add to `validate-hal.mjs` or sign-off script |
| **Pixel parity vs mockup gallery** | Operator checklist item 1 | Sign-off before declaring data phase complete |
| **`softdent_claim_status_export.csv`** | Extract file contracts | Add to Phase C alongside procedures |
| **`softdent_patient_ledger_export.csv`** | Extract Phase 4 | Phase C or D for narrative/ledger context |
| **EOD A/R cross-check** | Extract Lane 6 | P2 — stage EOD txt to inbox |
| **Clarify hub token in protocol doc** | QB/SoftDent note on `_lan_hal_hub_access_ok()` | Phase G doc-only task |
| **Regenerate MOONSHOT_API_KEY** | Documented 401 | Operator env — blocks future live consults |

---

## 4. Priority reconciliation table

| Rank | Agent plan (Phase / build) | Moonshot rank | Moonshot note |
|------|----------------------------|---------------|---------------|
| 1 | B — payment/adjustment fix (hal-10087) | **1** | Extract report Phase 1 — highest ROI |
| 2 | *implicit* widget DB fallback | **2** | Extract Phase 2 — agent should name explicitly |
| 3 | C2 — operatory contract + export (hal-10089) | **3** | QB/SoftDent blocker #1 |
| 4 | G — hub sign-off (hal-10094) | **4** | QB/SoftDent blocker #2 |
| 5 | E1 — QB empty states (hal-10093) | **5** | QB conditional approve item |
| 6 | C1 — procedures export (hal-10088) | **6** | Needed for narratives; Moonshot file contracts |
| 7 | D — HAL narrative workflow (hal-10090–92) | **7** | After data; Moonshot doesn't block on this for "daily use" |
| 8 | E2–E4 — QB deposit variance | **8** | Extract Phase 5 |
| 9 | A — repo hygiene / push (hal-10086) | **9** | Operator hygiene; parallel not blocking |
| 10 | F — ODBC (hal-10095) | **10** | Extract Phase 3 — after operator DSN setup |

---

## 5. Side-by-side: next 5 commits

| # | Cursor agent plan | Moonshot-aligned merged plan |
|---|-------------------|------------------------------|
| **1** | hal-10086 — repo hygiene, shortcuts, push | **hal-10087** — payment/adjustment fix (`softdent_odbc_extract.py`, register JSONL) |
| **2** | hal-10087 — payment fix | **hal-10087b** — wire analytics DB → widgets when `sd_*` empty |
| **3** | hal-10088 — procedures export | **hal-10089** — operatory schedule contract + empty state UX |
| **4** | hal-10089 — operatory export | **hal-10094** — hub token doc + manual broadcast sign-off |
| **5** | hal-10090 — narrative review port | **hal-10088** — procedures + claim status exports → claims widget |

**Then:** hal-10093 (QB empty states) → hal-10090–92 (narratives) → hal-10086 (hygiene push) → hal-10095 (ODBC when operator ready).

---

## 6. Moonshot independent roadmap (from prior reports, not live review)

Moonshot's **Integration Roadmap** (SoftDent extract report) in original order:

1. Fix payment/adjustment gap  
2. Wire analytics DB → widgets  
3. ODBC foundation (operator setup)  
4. Operatory + ledger exports  
5. HAL cross-domain briefings (SoftDent vs QB)

Moonshot's **daily-use blockers** (QB/SoftDent/SideNotes report):

1. Operatory data contract + dedicated export  
2. Hub security + manual broadcast test  
3. Operator sign-off checklist (mockup parity, F5, hub latency)

**Synthesis:** Moonshot treats **operatory + hub** as ship gates and **payments** as first data fix. The agent plan matches on payments but schedules **repo hygiene first** and **hub sign-off late** — Moonshot would pull hub/operatory earlier.

---

## 7. Risk flags — Moonshot would escalate

| Risk | Agent plan | Moonshot |
|------|------------|----------|
| Narrative hallucination | Phase D with review.js | Moonshot would require **review before save** — agent agrees; Moonshot would **block Phase D** until procedures CSV exists |
| ODBC before bridge fixed | Phase F last | Moonshot agrees — don't ODBC until payment lane works |
| Daily ops claim at hal-10085 | Implied complete for UI | Moonshot: **CONDITIONAL APPROVE** — data/hub still open |
| Hub spoofing | Phase G | Moonshot wanted token + origin **before daily use** — partially implemented; test not recorded |
| Stale API keys | Mentioned in Phase A | Blocks live Moonshot consult — **operator action** |

---

## 8. Domain-by-domain scorecard

| Domain | Agent plan grade | Moonshot grade | Gap |
|--------|------------------|----------------|-----|
| SoftDent data | A — thorough phases B, C, F | A — same priorities | Agent should add explicit Phase 2 widget wiring |
| Claims narratives | A — full HAL workflow | B+ — data first, UI second | Align order with Moonshot |
| QuickBooks | B+ — Phase E late | B — empty states are ship gate | Move E1 earlier |
| Hub / Workstation | B — Phase G late | A− — blockers #2 | Elevate G in sequence |
| Repo hygiene | A — Phase A | C — not Moonshot focus | Keep parallel, not first code commit |
| GPU / models | A | A | Aligned |
| ODBC | A — correctly optional | A | Aligned |

---

## 9. Final recommendation (merged)

**For the operator:** Accept the agent detail plan as the **implementation spec**, but **reorder the first five code commits** to match Moonshot's proven priorities:

1. Payment/adjustment fix  
2. Analytics DB → widget fallback  
3. Operatory contract + empty state  
4. Hub broadcast sign-off + protocol doc  
5. Procedures + claim status exports  

Run **repo push, shortcut refresh, and F5/hub checks** in parallel this week — not as a blocking "Phase A" before data.

**Claims narrative HAL workflow** (agent Phase D) remains high value but Moonshot would not count it toward "daily operator ready" until operatory and hub blockers close.

**Regenerate Moonshot/OpenRouter API keys** and rerun `scripts/run_moonshot_plan_comparison.py` to replace this synthesis with a live kimi-k2.6 critique.

---

## 10. Action items

| Owner | Action |
|-------|--------|
| Operator | Fix `MOONSHOT_API_KEY` / `OPENROUTER_API_KEY`; rerun comparison script |
| Operator | `RefreshDesktopShortcuts.bat`; push `main` to origin |
| Developer | Next commit: **hal-10087 payment fix** (not hal-10086 hygiene-only) |
| Developer | Add **hal-10087b** widget wiring commit (Moonshot Phase 2) |
| Developer | Record hub broadcast test in sign-off log |
| Both | Run operator sign-off with 8765 + 8766 up |

---

## Appendix — document map

| Document | Role in comparison |
|----------|-------------------|
| `MOONSHOT_DETAIL_PLAN_REPORT_2026-07-08.md` | Agent 10-commit plan (baseline) |
| `MOONSHOT_SOFTDENT_EXTRACT_REPORT_2026-07-08.md` | Moonshot data roadmap Phases 1–5 |
| `MOONSHOT_QB_SOFTDENT_SIDENOTES_REPORT_2026-07-07.md` | Moonshot blockers + conditional approve |
| `MOONSHOT_PLAN_REVIEW_2026-07-08.md` | Failed live API placeholder |
| `scripts/run_moonshot_plan_comparison.py` | Live comparison runner |

---

**End of comparison report.**
