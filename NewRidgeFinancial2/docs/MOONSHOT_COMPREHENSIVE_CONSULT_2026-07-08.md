# Moonshot AI Comprehensive Consultation

**Date:** 2026-07-08  
**Build:** hal-10085  
**Model:** Synthesized from prior Moonshot reports (kimi-k2.5/k2.6) + live codebase audit  
**Script:** `scripts/run_moonshot_comprehensive_consult.py`  
**Note:** Live Moonshot/OpenRouter API returned **401** (invalid/missing auth). Local Ollama `hal-chat:14b` fallback was too shallow for this scope. This document consolidates prior Moonshot consultations and a fresh repo audit to answer the operator's full question list.

**Reload:** `https://127.0.0.1:8765/?v=hal-10085&__nr2_purge=1`

---

# Verdict

**NR2 is at the Moonshot practical ceiling (hal-10085) for UI/HAL presentation.** The highest-value next work is **data depth** (SoftDent payments/claims/procedures, QuickBooks cold-cache UX), **claims narrative workflow** (wire clinical notes → HAL-assisted drafts), **repo hygiene** (archive `_legacy`, commit consultation scripts), and **operator polish** (desktop shortcuts, hub broadcast sign-off). Do not rewrite to React or add multi-tenant features.

**Top 3 priorities:** (1) Fix SoftDent payment/adjustment parsing + procedures export for narratives, (2) HAL narrative assist on Claims page using clinical notes + `hal-narrative-library.js`, (3) Refresh desktop shortcuts and run dual-server sign-off (8765 + 8766).

---

## 1. Repo Cleanup & Hygiene

### Safe to keep (production)

| Path | Role |
|------|------|
| `NewRidgeFinancial2/` | Active NR2 app (8765/8766) |
| `scripts/start_program.ps1`, `StartProgram.bat` | Canonical launchers |
| `app_data/` (gitignored) | Runtime imports, hub token, office channel |
| `.local_logs/` (gitignored) | Moonshot evals, sign-off logs, mockup gallery |
| `.tmp/` (gitignored) | Browser/workstation stdout/stderr |

### Candidates to archive or remove (P1 — not urgent)

| Item | Recommendation |
|------|----------------|
| `_legacy/` (~650 files) | **Archive** to a branch or zip outside repo; contains old FastAPI + full `insurance_narratives` workflow worth **porting**, not deleting blindly |
| `frontend/` + root `app/` | Parallel stacks superseded by NR2 `site/` — archive if no active CI depends on them |
| `NewRidgeFinancial2/sidenotes-helper/py32/` (~2,300 files) | Bundled 32-bit Python for VistaDB COM — **keep** for SideNotesIM; do not commit updates casually |
| Root eval scripts (`run_235b_eval*.py`, many `scripts/*eval*`) | Move to `scripts/archive/` or document as dev-only; several are gitignored already |
| `scripts/run_insurance_narrative_dry_run.py` | **Broken** — imports `_legacy/app/insurance_narratives`; fix path or delete after port |
| `StartNewRidgeFinancial2.bat` | Duplicate of `StartProgram.bat` — keep one canonical name |
| `scripts/run_moonshot_softdent_extract_analysis.py` | **Commit** — useful consultation runner |
| `scripts/run_moonshot_comprehensive_consult.py` | **Commit** — this consultation runner |

### Git / diff hygiene (P2)

- Branch is **10 commits ahead** of `origin/main` — push when ready for backup
- Regenerate **MOONSHOT_API_KEY** at [platform.moonshot.ai](https://platform.moonshot.ai) or fix **OPENROUTER_API_KEY** (401 on 2026-07-08)
- Run `RefreshDesktopShortcuts.bat` after build bumps so shortcut descriptions show `hal-10085`

### Do not delete

- `import-manifest.json`, `moonshot-site.manifest.json`, validators
- `docs/MOONSHOT_*.md` — consultation trail
- `workstation-deploy/`, `sidenotes-helper/deploy/` — station packages

---

## 2. Architecture, Runtime & Error Fixes

### Current architecture (correct)

```
StartProgram.bat → browser_app.py (8765) → nr2_http_server.py
  ├── import_sync.py ← C:\SoftDentFinancialExports
  ├── softdent_odbc_extract.py (sd_* tables, ODBC optional)
  ├── nr2_qb_reports.py (7 QB report APIs)
  └── hal_hub.py ← app_data/nr2/office/

StartWorkstation.bat → workstation_app.py (8766)
  ├── Same HTTP server, workstation mode
  ├── sidenotes-helper → SideNotesIM history.vdb (metadata only)
  └── POST /api/hub/notify → 8765 badge + hero mirror (hal-10085)
```

### Known runtime issues

| Issue | Fix |
|-------|-----|
| 8765 slow to respond on cold start | Normal — wait ~30s; check `.tmp/nr2-browser.err.log` |
| Moonshot API 401 | Refresh API keys; consultation scripts fall back to Ollama |
| `sd_payments` / `sd_adjustments` = 0 | Extend payment code detection in `softdent_odbc_extract.py` |
| ODBC lane idle | Set `SOFTDENT_ODBC_DSN` + query env vars; run schema discovery script |
| Operator sign-off live tests SKIP when servers down | Start both 8765 and 8766 before sign-off |
| ROCm / rocblaslt warnings | `ROCBLAS_TENSILE_LIBPATH` documented in `hal-models.json` |

### Post hal-10085 — no further UI tiers programmed

Validators: 103 HAL suites, pages pass, mockup parity 10/10. Focus shifts to **data + workflow**, not layout.

---

## 3. Claims Narratives from SoftDent Clinical Notes + HAL

### What exists today

| Layer | Module | Behavior |
|-------|--------|----------|
| Data source | `softdent_operational_pipeline.py` | Builds `softdent_clinical_notes_data.json` from daysheet transactions |
| Claims source | Same + `softdent_claims_export.csv` | Derived rows (max ~150), not live claim status |
| Template library | `hal-narrative-library.js` | 10 focus types (Medical Necessity, Denial Appeal, etc.) |
| Composer | `services.js` narratives.* | Local draft save; `HalNarrativeLibrary.selectBestNarrativeForClaim()` |
| Full workflow (legacy) | `_legacy/app/insurance_narratives/` | Packet → draft → checker → export — **not wired to NR2** |
| HAL chat | `hal-page-canvas.js`, Tier S3 citations | Can explain widgets; no dedicated "draft narrative for claim X" tool |

### Recommended workflow (P0)

1. **Enrich data** — Add procedures CSV + claim status export to import inbox (see SoftDent section). Narratives need: tooth/surface, CDT, date of service, clinical note text, payer, denial reason if appeal.
2. **Claims page action** — "Draft narrative" button on claim row → gathers claim + matched clinical note → HAL prompt with `hal-narrative-library` template + tone/length.
3. **HAL tool** — Add `draft_insurance_narrative` tool in `hal-models.json` that:
   - Reads claim row + clinical note JSON (no PHI in logs)
   - Applies library template
   - Returns editable draft in Claims/Narratives widget
4. **Human review gate** — Never auto-submit to payer; operator edits and copies to clearinghouse/SoftDent manually (read-only boundary preserved).
5. **Port legacy checker** — Bring `_legacy/app/insurance_narratives/review.py` rules (required fields, length limits) into a lightweight JS validator before export.

### HAL prompt pattern

```
Given claim {id}, payer {payer}, procedures {cdt_list}, and clinical note excerpt {note}:
Using focus "{focus_type}" and tone "{tone}", draft an insurance narrative.
Cite only provided clinical facts. Flag missing fields.
```

Use **local 8B for draft**, escalate to **14B or 24B** for denial appeals requiring reasoning.

---

## 4. SoftDent — Additional Data to Extract

**Full detail:** `docs/MOONSHOT_SOFTDENT_EXTRACT_REPORT_2026-07-08.md`

### Already flowing (primary lane: `C:\SoftDentFinancialExports`)

Daysheet JSONL, transactions, A/R aging, write-offs, register, dashboard bundle, claims CSV, clinical notes JSON, case acceptance, hygiene recall, new patients, treatment plan CSV, provider production, production-by-ADA.

### Highest-value additions

| Priority | Data | Source | Unlocks |
|----------|------|--------|---------|
| **P0** | Payments & adjustments | Fix code mapping in daysheet/register JSONL | Collections daily, adjustment log, collection lag |
| **P0** | Procedures detail CSV | SoftDent report export → inbox | Insurance narratives, production reconciliation |
| **P1** | Operatory schedule | Dedicated `operatory_schedule.json` export | Operatory grid widget |
| **P1** | Outstanding claims / claim status | Claims aging report or ODBC | Claims pipeline depth |
| **P1** | Patient ledger | Ledger CSV export | HAL ledger context |
| **P2** | ODBC full extract | SQL Server read-only DSN | Patients, appointments, deep claim rows |
| **P2** | Fee schedules, payment plans | Report profiles | Fee validation, financing view |

### ODBC setup (when ready)

1. Run `NewRidgeFinancial2/scripts/discover_softdent_odbc_schema.py`
2. Set `SOFTDENT_ODBC_DSN`, per-table `SOFTDENT_ODBC_*_QUERY`
3. Consent-gated `POST /api/admin/extract-softdent-odbc`
4. `import_sync.py` calls `ensure_softdent_odbc_fresh()` automatically

### Deprioritize

- `C:\Users\mreno\SoftDentBridge\exports` — stale June 2026 samples; production lane is `SoftDentFinancialExports`

---

## 5. QuickBooks — Capturing More Data

### Captured now

- Import manifest: revenue, P&L, expenses, categories, AR
- SDK probe summary staged to analytics
- **7 report APIs:** balance sheet, cash flow, net income, revenue by service, AP aging, AR aging, credit cards
- Monthly sync via `quickbooks_monthly_sync.py`
- QBO OAuth stub in `qb_connector.py` (needs `NR2_QBO_CLIENT_ID/SECRET`)

### How to capture more (ranked)

| Priority | Action | Module |
|----------|--------|--------|
| **P0** | Keep Desktop SDK probe on schedule; surface "Awaiting QuickBooks sync" empty states | `nr2-qb-reports.js`, mockup chrome |
| **P1** | Expand probe to pull **deposits, payments received, vendor bills** into analytics DB | `import_sync.py`, new table keys |
| **P1** | Cross-domain HAL briefing: SoftDent collections vs QB deposits (variance alert) | `hal-proactive.js`, `nr2_analytics.py` |
| **P2** | QBO Online OAuth for cloud backup lane (read-only) | `qb_connector.py` |
| **P2** | Journal entry push (consent-gated, already stubbed) | posting workflow |

### Moonshot conditional items still worth doing

- F5×5 reload test — no duplicate chart overlays
- Reconciliation table at 768px
- EBITDA tile placement vs mockup

---

## 6. HAL Programming Update

### Current contract

- `hal-agent-programming.js` — **auto-agent-v13** (answer first, cite evidence, one next step)
- Active lane: `hal-chat:8b` @ Ollama 11434
- 24 tools (grep, patch, validation, widget feed, etc.)
- Tier S3: presence orb, citation chips, hero mirror publish

### Recommended updates (P1)

| Update | Why |
|--------|-----|
| Add `draft_insurance_narrative` tool | Claims workflow (section 3) |
| Add `explain_claim_variance` tool | Cross SoftDent claims + QB AR |
| Wire narrative tool to `hal-narrative-library.js` | Consistent templates |
| Morning briefing: include payment/adjustment gaps when `sd_payments=0` | Actionable ops alert |
| Document hub token + origin lock in operator runbook | Security clarity |
| Bump agent contract to v14 when narrative tools land | Version discipline |

### Do not change

- Read-only SoftDent/QB boundary
- PHI sanitization for cloud lane (disabled by default)
- Consent gates on writeback/submit actuators

---

## 7. Desktop Icons & Program Launchers

### Already built

| Shortcut script | Target | Names on desktop |
|-----------------|--------|------------------|
| `scripts/Refresh-NR2-DesktopShortcut.ps1` | `StartProgram.bat` | **Start Program**, **New Ridge Financial** |
| `scripts/Refresh-NR2-WorkstationShortcut.ps1` | `StartWorkstation.bat` | **NR2 Workstation**, **Start Workstation** |
| Icon | `assets/nr2-icon.ico` | |
| Batch refresh | `RefreshDesktopShortcuts.bat` | Both shortcuts |

### Operator action (one-time after hal-10085)

```powershell
cd C:\NewRidgeFamilyFinancial
.\RefreshDesktopShortcuts.bat
```

This stamps shortcut descriptions with schema `hal-10085`. Scripts also scan for **legacy shortcuts** pointing at old ports (`127.0.0.1:1966`, old PS1 paths) and warn — delete those manually if found.

### Optional improvement (P2)

- Single "New Ridge Suite" folder on desktop with both shortcuts
- Pin Start Program to taskbar via script (requires shell API — not implemented)

---

## 8. Workstation ↔ SideNotes ↔ HAL Central Hub

### Roles

| Component | Port | Function |
|-----------|------|----------|
| **Financial + HAL** | 8765 | System of record UI, widget feeds, HAL chat, staff sidenotes (local), CPA export |
| **Office Workstation** | 8766 | Send Message (office channel), Ask HAL, SideNotesIM monitor |
| **SideNotesIM** | external | VistaDB `history.vdb` — message **text stays local** to IM |
| **sidenotes-helper** | helper process | Metadata-only extract → `sidenotes-inbox.json` |
| **hal_hub.py** | shared | Inbound queue, office channel, station registry, SAPI on hub PC |

### Compatibility model (HAL as hub)

```
8766 Workstation ──POST /api/hub/notify──► hal_hub.py ──► 8765 badge (metadata only)
8766 SideNotes helper ──metadata──► sidenotes-inbox.json ──► 8766 + 8765 monitors
8765 Financial ──POST hero-metrics──► hub ──► 8766 mirror strip (hal-10085)
8766 Everyone broadcast ──► 8765 OFFICE BROADCAST badge (no message body)
```

### Gaps to close (from Moonshot Phase 5 review)

| Item | Status | Action |
|------|--------|--------|
| Hub token header | Partially implemented | Verify `X-Hub-Token` on all hub routes; document in runbook |
| Origin lock 8766→8765 | Partially implemented | Confirm `_lan_hal_hub_access_ok()` covers notify |
| Manual broadcast test | Not recorded | Send "Everyone" on 8766 → badge on 8765 within 15s |
| SideNotes body on 8765 | **By design: no** | PHI/compliance — metadata only on financial screen |
| Workstation HAL parity | Good | Sync triggers, Ask HAL, hero mirror |

### Making workstation "compatible" with SideNotes

- Workstation **already** runs `sidenotes-hub.js` and helper watcher
- Financial app uses **staff sidenotes** (local SQLite/bridge), not IM text
- **Do not** merge IM message bodies onto 8765 — instead: HAL summarizes **office channel posts** (operator-typed, not patient PHI) and SideNotes **metadata** (sender, time, station)

---

## 9. Best Local AI Model for 16GB Radeon RX 9060 XT

**Hardware:** AMD Radeon RX 9060 XT, 16 GB VRAM, ROCm gfx1200, models at `D:\LocalAI\ActiveModels`

### Recommended layout (matches your current speed-first config)

| Role | Model | VRAM | When |
|------|-------|------|------|
| **Pinned chat (default)** | `hal-chat:8b` (DeepSeek-R1 8B) | ~5–6 GB | Staff HAL chat, quick answers |
| **Optional pinned helper** | `hal-helper:14b` (Qwen3 14B) | ~8–9 GB | Disable if using 8B-only (current) |
| **On-demand reasoning** | `mistral-small3.1:24b-fast` | ~14 GB | Denial appeals, complex tax questions — **evicts pinned models briefly** |
| **On-demand heavy** | `qwen3:30b` with think | ~16+ GB | Rare escalation only |
| **Avoid pinning** | 235B, 180B, 120B | OOM | Cloud/OpenRouter for those |

### Practical recommendation for solo practice

**Keep current single-lane 8B** for daily HAL (`Install-HAL-GPU-Chat-Lane.ps1 -UnpinHelper`).

For **claims narratives**, temporarily load **14B** or call **24B on demand** when drafting appeals — accept 10–20s latency.

Register warmup task so 8B is always hot:

```powershell
powershell -ExecutionPolicy Bypass -File .\NewRidgeFinancial2\model-automation\Register-HAL-Model-Automation.ps1
```

### Cloud fallback

When local model is insufficient, use **OpenRouter kimi-k2** or **Moonshot kimi-k2.6** for consultation/architecture (not PHI) — fix API key first.

---

## 10. Additional Suggestions

1. **Push `main` to origin** — 10 commits of Moonshot work un backed up remotely
2. **Monthly CPA export** — schedule Financial page CPA zip for accountant
3. **SoftDent refresh task health** — confirm daily + 45-min jobs in Task Scheduler
4. **Disaster recovery drill** — restore from `app_data/nr2/backups/` once per quarter (`docs/MOONSHOT_DISASTER_RECOVERY.md`)
5. **Mockup gallery** — keep `8799` mockup server for visual regression before build bumps
6. **Port insurance narrative workflow** from `_legacy` before archiving `_legacy/`
7. **Operator sign-off** — run with both servers up; record name in sign-off log
8. **Fix API keys** — regenerate Moonshot/OpenRouter for future live consultations
9. **Collection lag widget** — unlocks once payments land in `sd_payments`
10. **No React rewrite, no multi-tenant, no SoftDent writeback** — still correct non-goals

---

## Prioritized Roadmap (next 5 commits)

| # | Commit theme | Acceptance criteria |
|---|--------------|---------------------|
| **1** | SoftDent payment/adjustment fix | `sd_payments` > 0 after sync; collections daily widget shows data |
| **2** | Procedures export + import contract | `procedures.csv` in inbox; claims page shows procedure detail |
| **3** | HAL narrative draft on Claims page | Button → HAL draft using clinical notes + library template; operator edit only |
| **4** | Operatory export + empty state | `operatory_schedule.json` or visible empty copy; grid non-blank when data exists |
| **5** | Hub sign-off + desktop shortcuts | Manual 8766→8765 broadcast PASS; shortcuts show hal-10085; docs updated |

---

## Related documents

- `docs/MOONSHOT_SOFTDENT_EXTRACT_REPORT_2026-07-08.md`
- `docs/MOONSHOT_QB_SOFTDENT_SIDENOTES_REPORT_2026-07-07.md`
- `docs/MOONSHOT_FULLEST_EXTENT_COMPLETE_2026-07-09.md`
- `docs/MOONSHOT_PHASE5_HUB_PROTOCOL.md`
- `docs/OPERATOR_PILOT_RUNBOOK.md`

**Re-run live Moonshot consultation after fixing API keys:**

```powershell
py -3.14 scripts\run_moonshot_comprehensive_consult.py
```
