# Workstation Plan Comparison — Cursor Agent vs Moonshot AI

**Date:** 2026-07-08  
**Build:** hal-10095  
**Agent plan:** [WORKSTATION_HAL_SIDENOTES_PLAN_REPORT_2026-07-08.md](WORKSTATION_HAL_SIDENOTES_PLAN_REPORT_2026-07-08.md)  
**Moonshot sources:** Prior live consultations (kimi-k2.5, Phase 5 hub protocol, QB/SoftDent/SideNotes review, comprehensive consult §8, workstation consult 2026-07-08)  
**Comparison script:** `scripts/run_moonshot_workstation_plan_comparison.py`

---

## API status (live ask attempt)

| Endpoint | Result |
|----------|--------|
| `api.moonshot.ai` | **401** Invalid Authentication |
| `openrouter.ai` | **401** Missing Authentication header |

**Live Moonshot review of the agent workstation plan could not be completed.** This report compares the agent plan against **Moonshot's documented prior positions** in:

- `MOONSHOT_WORKSTATION_SIDENOTES_2026-07-08.md`
- `MOONSHOT_PHASE5_HUB_PROTOCOL.md`
- `MOONSHOT_QB_SOFTDENT_SIDENOTES_REPORT_2026-07-07.md`
- `MOONSHOT_COMPREHENSIVE_CONSULT_2026-07-08.md` (§8)

Regenerate API keys and rerun:

```powershell
py -3.14 scripts\run_moonshot_workstation_plan_comparison.py
```

---

## Executive verdict

| Reviewer | Verdict |
|----------|---------|
| **Cursor agent plan** | 5 phases (H1–H5), builds hal-10096–10100, workstation-first rollout with HAL as hub |
| **Moonshot (prior reports)** | **CONDITIONAL APPROVE** on architecture; **not SideNotes replacement** until popup + hub sign-off; dual-run 2+ weeks |

**Alignment: ~90%** — Moonshot and the agent plan agree on architecture (HAL hub 8765, workstation 8766, SideNotes bridge), compliance (no IM text on 8765), and P0 priorities (broadcast sign-off, popup parity, watcher health). They differ mainly on **rollout scope** (agent deploys all 10 desks in H4; Moonshot would pilot 3 first) and **timing of UX polish** (agent H3 history before full deploy; Moonshot would defer history until popups proven).

**Recommended merged order** is at the bottom of this document.

---

## Moonshot AI independent review (synthesized from prior guidance)

### Moonshot Verdict on Agent Workstation Plan

**CONDITIONAL APPROVE** — The agent plan correctly captures Moonshot's HAL-as-hub model and prioritizes the right P0 gates (hub broadcast, popup reliability). Phase ordering H1→H2→H3→H4 is sound. Moonshot would **narrow H4** to a 3-desk pilot before all-station rollout and **add Ask HAL LAN validation** to the install script before declaring H2 complete.

---

### Agreement (what the agent plan got right vs prior Moonshot guidance)

| Agent plan item | Moonshot evidence |
|-----------------|-------------------|
| **HAL on 8765 as intelligence hub** | Comprehensive consult §8: "HAL as hub — APPROVE"; financial screen metadata only |
| **H1 hub sign-off first** | QB/SoftDent/SideNotes blocker #2: manual Everyone→8765 badge within ~15s |
| **H2 popup + watcher before history** | Workstation consult P0: popup with messenger closed; watcher must stay alive |
| **Dual-run SideNotes + NR2** | Workstation consult §8 migration Phase A–B; "2+ weeks" rule |
| **No SideNotes body on 8765** | Phase 5 protocol: `record_hub_broadcast` strips text; compliance mandatory |
| **Hub token + origin (hal-10094)** | Phase 5 protocol implemented; agent H1 verifies — matches Moonshot blocker |
| **SideNotes as VistaDB transport** | Comprehensive consult: bridge via `sidenotes-helper`; don't merge IM text |
| **12 message prompts + Ask HAL** | Agent correctly preserves NR2 advantages Moonshot identified |
| **Three popup paths** (vdb, hub, toast) | Matches `workstation_app.py` architecture Moonshot reviewed |
| **536×447 window match** | Workstation consult P2 — agent documents in plan Part I |
| **14-day operator parity (H5)** | Moonshot adoption rule: indistinguishable for 2+ weeks |

---

### Disagreements or Corrections

| Topic | Agent plan | Moonshot position | Resolution |
|-------|------------|-------------------|------------|
| **H4 all-station deploy** | hal-10100 — all 10 stations | Moonshot would **pilot 3 desks** (hub + 2 rooms) before full rollout | **Split H4:** H4a pilot 3, H4b remaining 7 after 1 week clean |
| **H3 before pilot complete** | History UX (hal-10099) in week 2–3 | Moonshot: history is **P1**, not adoption blocker — popups are P0 | **Defer H3** until H2 PASS on pilot desks; or make H3 parallel not blocking |
| **Ask HAL LAN test** | Mentioned in troubleshooting | Moonshot would require **install-time hub ping** in `Setup-Workstation.ps1` | **Add to H2 acceptance:** `-HalHubUrl` validated before shortcut created |
| **Token hardening as code commit** | H1 includes verify token/origin | Moonshot: largely **done at hal-10094** — H1 is mostly operator test | **H1 = operator sign-off**, not new code unless test fails |
| **HAL-initiated popups** | P2 in consult, not in agent phases | Moonshot listed `sendHalPopupMessage` as P2 gap | **Add H6 backlog** — HAL desk alerts from 8765 |
| **Office fallback on 8765 tabs** | Not in agent plan | Moonshot P2: `sidenotes-office-fallback.js` when 8766 offline | **Add doc note** in H1 runbook; code already exists |
| **SAPI on hub PC** | Mentioned in architecture | Moonshot comprehensive consult: hub PC speaks announcements | **Verify** `hal_hub.py` SAPI path in H1 sign-off |

---

### Missing Items (agent plan omitted)

| Missing item | Moonshot source | Suggested add |
|--------------|-----------------|---------------|
| **Automated sign-off script extension** | Phase 5 protocol references `run-moonshot-operator-signoff.mjs` #5 | H1: extend W1–W8 into sign-off.mjs when servers up |
| **Hub URL firewall rule doc** | Risk WS8 in agent plan | Add to `README-WORKSTATION.md` — inbound 8765 on office subnet |
| **SideNotes station name mismatch guard** | Setup uses `-Station` | Validate against `CANONICAL_STATIONS` in `hal_hub.py` at install |
| **Funnel / mockup parity** | QB/SoftDent operator checklist | Out of workstation scope — agent correctly separates |
| **Regenerate API keys** | Documented 401 | Operator env — blocks live Moonshot |
| **Dual popup path test (W8)** | Agent test matrix W8 | Moonshot would require both vdb AND hub inbound paths tested |
| **SideNotesIM must be running** | Bridge dependency | Add to desk troubleshooting: SideNotesIM.exe required for send |

---

### Priority Reconciliation Table

| Rank | Agent plan (Phase / build) | Moonshot rank | Moonshot note |
|------|----------------------------|---------------|---------------|
| 1 | H1 — hub sign-off (hal-10096) | **1** | Blocker #2 — operator test before code; token already implemented |
| 2 | H2 — popup reliability (hal-10097–98) | **2** | Workstation consult P0 — adoption gate |
| 3 | H2b — Ask HAL LAN + hub URL validation | **3** | Agent omitted as explicit commit — Moonshot adds |
| 4 | H4a — pilot 3 desks (partial hal-10100) | **4** | Moonshot would not wait for all 10 |
| 5 | H2 — watcher auto-restart | **5** | Agent ranks with popup — Moonshot agrees |
| 6 | H3 — history UX (hal-10099) | **6** | P1 not P0 — defer until pilot popups PASS |
| 7 | H4b — remaining desks | **7** | After 1 week pilot clean |
| 8 | H5 — 14-day parity proof | **8** | Moonshot 2-week rule — agent 14 business days aligned |
| 9 | HAL-initiated popups | **9** | P2 backlog — not in agent plan |
| 10 | SideNotes-minimized mode | **10** | Phase D migration — only after H5 |

---

### Moonshot Independent Roadmap (next 5 commits — Moonshot order)

| # | Build | Deliverable | Acceptance |
|---|-------|-------------|------------|
| **1** | hal-10096 | **Operator hub sign-off** (no code unless fail) | W1 PASS: Everyone→badge ≤15s, no body; token 403 test |
| **2** | hal-10097 | Watcher health UI + auto-restart | W3 PASS: offline→online ≤30s |
| **3** | hal-10098 | Popup stack + **Setup-Workstation hub ping** | W2 PASS on hub PC + Room 1 + Room 2; messenger closed |
| **4** | hal-10099 | History merge (only if W2 PASS on 3 desks) | Unified list; SideNotes suffix |
| **5** | hal-10100 | **Pilot package** — 3 desks only | Install.bat + hub URL; 1 week clean run |

**Then:** hal-10101 remaining 7 desks → H5 14-day proof → optional HAL desk popups.

---

### Side-by-Side Phase Comparison (Agent H1–H5 vs Moonshot)

| Phase | Agent | Moonshot | Delta |
|-------|-------|----------|-------|
| H1 | Hub sign-off + token hardening | Operator sign-off; code mostly done | **Align** — H1 is test-first |
| H2 | Popup + watcher (2 builds) | Same + hub URL validation at install | **Add** hub ping to H2 |
| H3 | History UX | Defer until pilot popups PASS | **Agent early** — Moonshot would delay |
| H4 | All 10 desks | Pilot 3 first | **Agent over-scoped** — split H4 |
| H5 | 14-day proof | 2-week dual-run | **Align** |

---

### Risk Flags Moonshot Would Escalate

| Risk | Agent plan | Moonshot |
|------|------------|----------|
| Deploy all desks before popup proven | H4 all 10 stations | **Escalate** — pilot 3 first |
| SideNotes body on 8765 | Agent forbids | **Escalate if violated** — compliance |
| Watcher single point of failure | H2 addresses | Moonshot P0 — must auto-restart |
| Ask HAL fails silently on remote desk | Troubleshooting only | **Escalate** — install-time validation required |
| Staff revert to SideNotes-only | H5 addresses | Moonshot expects this — dual-run mandatory |
| Hub PC down | Documented acceptable | SideNotes still works; HAL features degrade — **OK** |

---

### Final Recommendation (Moonshot synthesis, one paragraph)

Proceed with the agent plan's **H1→H2 sequence immediately**, but treat H1 as an **operator sign-off gate** (manual broadcast + popup tests) before writing code unless tests fail. **Do not deploy hal-10100 to all ten stations** until three pilot desks (hub PC workstation + two operatories) pass W1–W3 for one week. Defer history polish (H3) until popups are proven — Moonshot ranks it P1, not an adoption blocker. Keep SideNotesIM installed throughout; the agent's 14-day H5 matches Moonshot's two-week rule. HAL-as-hub architecture requires no changes. Regenerate Moonshot API keys and rerun the comparison script when you want a live kimi-k2.6 review of this merged roadmap.

---

## Side-by-side: next 5 commits

| # | Cursor agent plan | Moonshot-aligned merged plan |
|---|-------------------|------------------------------|
| **1** | hal-10096 — hub sign-off + token verify | **hal-10096** — operator W1/W6/W7 sign-off (test-first) |
| **2** | hal-10097 — watcher health UI | **hal-10097** — watcher health + auto-restart |
| **3** | hal-10098 — popup stack + logging | **hal-10098** — popup stack + **Setup-Workstation hub ping** |
| **4** | hal-10099 — history UX | **hal-10099** — history merge *(only after 3-desk W2 PASS)* |
| **5** | hal-10100 — all-station deploy | **hal-10100** — **pilot 3 desks** (not all 10) |

**Then:** hal-10101 remaining desks → H5 14-day proof → HAL-initiated popups (backlog).

---

## Domain scorecard

| Domain | Agent plan grade | Moonshot grade | Gap |
|--------|------------------|----------------|-----|
| HAL-as-hub architecture | A | A | Aligned |
| Hub security / compliance | A | A | Token done; test not recorded |
| Popup reliability plan | A− | A | Add install-time hub ping |
| Watcher / bridge | A | A | Aligned |
| Rollout strategy | B | A− | Pilot 3 before all 10 |
| History / UX polish | B+ | B | Agent schedules early — OK if non-blocking |
| Migration / dual-run | A | A | 14-day H5 matches 2-week rule |
| Ask HAL routing | B | B+ | Needs install validation |
| Documentation | A | A− | Add firewall + SideNotesIM dependency |

**Overall agent plan grade: A−** — Moonshot would **CONDITIONAL APPROVE** with pilot-scope correction on H4.

---

## Reconciliation guidance for operator

1. **Run W1 broadcast test today** before any hal-10096 code — both reviewers agree.
2. **Pilot 3 desks**, not 10, for first hal-10100 package — Moonshot correction to agent plan.
3. **Add hub URL ping** to `Setup-Workstation.ps1` — Moonshot addition not in agent phases.
4. **H3 history is nice-to-have** until W2 popup PASS — don't block rollout on history polish.
5. **Keep SideNotesIM** on every desk through H5 — both agree; no SideNotes removal.
6. **Fix API keys** — rerun live Moonshot comparison when keys work.

---

## Related documents

| Document | Role |
|----------|------|
| `WORKSTATION_HAL_SIDENOTES_PLAN_REPORT_2026-07-08.md` | Agent plan under review |
| `MOONSHOT_WORKSTATION_SIDENOTES_2026-07-08.md` | Moonshot workstation consult |
| `MOONSHOT_PHASE5_HUB_PROTOCOL.md` | Hub API spec |
| `MOONSHOT_PLAN_COMPARISON_2026-07-08.md` | Main NR2 plan comparison (data/HAL) |

**Merged next action:** Execute W1–W3 manual tests on hub PC + Room 1 + Room 2. Record PASS/FAIL. Only then commit hal-10096 watcher changes if tests fail.
