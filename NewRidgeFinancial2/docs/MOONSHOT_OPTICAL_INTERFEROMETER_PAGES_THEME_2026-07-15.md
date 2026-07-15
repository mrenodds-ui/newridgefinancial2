# Moonshot AI — Widget Workability + Full Pages/Subpages (CONSULT ONLY)

**Date:** 2026-07-15
**Model:** `kimi-k2.5`
**Key:** OPENROUTER_API_KEY
**Script:** `scripts/run_moonshot_interferometer_pages_theme_consult.py`
**Apply:** DO NOT APPLY production cutover until operator approves.

## Operator request (verbatim)

> ask moonshot ai if all these widgets will work and have him create pages and subpages with all that is required of this program. tell him to follow the same theme as the main page

---

# Verdict (schema nr2-12010-pages)

## 0. Operator Intent (verbatim)
> ask moonshot ai if all these widgets will work and have him create pages and subpages with all that is required of this program. tell him to follow the same theme as the main page

## 1. Main-page widget workability matrix (table)

| Widget | Status | API / Data Bind | Honesty & RBAC Constraints |
|--------|--------|----------------|---------------------------|
| **SoftDent Emitter** (Left-Bottom, white pulse λ≈450nm) | **BINDABLE** | `SoftDent ledger` (read-only), `POST /api/apex/softdent/refresh-period` | **Honesty:** Beam dims (secondary filament flicker) if AR stale; displays "∅" never "$0". **RBAC:** All roles view; `office_manager`/`admin` control Period Wheel. |
| **QuickBooks Emitter** (Right-Bottom, gold λ≈590nm) | **BINDABLE** | `POST /api/apex/sync/qb-payroll-ap-export`, QB connection status | **Honesty:** Shows last sync timestamp; amber warning if >24hrs. **RBAC:** `office_manager`/`admin` execute export; `dentist` view-only. |
| **Tax Prism** (Upper-Right, violet λ≈400nm) | **BINDABLE** | `POST /api/apex/tax/calculate-planning` | **Honesty:** Displays confidence interval % alongside values. **RBAC:** `admin`, `office_manager` only. |
| **HAL Core** (Center, interference nexus) | **BINDABLE** | `POST /api/apex/hal/reconciliation`, `POST /api/apex/hal/board-actions` | **Honesty:** Pattern shows "destructive interference" (red fringes) if reconciliation gaps detected. **RBAC:** All roles observe; `admin` triggers board-actions. |
| **Master Pulse / SYNC** | **BINDABLE** | `POST /api/apex/sync/trigger` | **Honesty:** Disabled (beam collimator locks) if `GET /api/import-readiness` returns false. **RBAC:** `office_manager`, `admin`. |
| **Period Wheel** | **BINDABLE** | `POST /api/apex/softdent/refresh-period` | **Honesty:** Visual gear-lock indicator when SoftDent period closed (no write-back enforced). **RBAC:** `office_manager`, `admin`. |
| **RECONCILE Trigger** | **BINDABLE** | `POST /api/apex/hal/reconciliation` | **Honesty:** Inactive (grayscale) if no dirty records detected by HAL pre-scan. **RBAC:** `office_manager`, `admin`. |
| **RBAC Role Indicator** | **BINDABLE** | Session auth context (`front_desk`, `hygienist`, `office_manager`, `dentist`, `admin`) | **Honesty:** Cryptographic badge; cannot be client-side spoofed. Displays as "Operator Class" in HUD. |
| **SCRAM** (Emergency Cutoff) | **NEEDS SUBPAGE** | *No API defined for emergency halt* | Currently ornamental safety cap. Relocate to `/office-manager/scram` pending `POST /api/apex/emergency-halt` specification. |
| **Film Strip** (ERA/Claims microfiche) | **NEEDS SUBPAGE** | SoftDent Claims / ERA (read-only) | Too heavy for main viewport. Relocate to `/claims/era` as "Microfiche Viewer". |
| **Alignment Lasers** (Sync health) | **BINDABLE** | `GET /api/import-readiness` | Visualizes as green coherent beams (λ≈532nm) when systems aligned; red scatter if import blocked. **RBAC:** All roles. |

## 2. Gaps / deferred to subpages

**Moved OFF main bench to preserve vacuum clarity:**

1. **SCRAM Protocol** → `/office-manager/scram`  
   *Gap:* No emergency stop API exists. Widget on main would be "dishonest" (inert decoration). Defer until backend provides halt endpoint.

2. **Film Strip / ERA Viewer** → `/claims` or `/claims/era`  
   *Gap:* High data density violates "readable type" on main. Requires dedicated viewport with pagination.

3. **Deep AR Grids** (aging buckets >90 days) → `/ar`  
   *Gap:* Main bench shows only pulse summary (total AR). Detail grids deferred.

4. **Narrative Editor & Quarantine Release** → `/narratives`  
   *Gap:* Requires text input surfaces and quarantine workflow (generate, edit, release). Too heavy for optical main.

5. **Document Thumbnails** → `/documents`  
   *Gap:* Film strip metaphor extends to full vault here.

6. **SoftDent Write-back Controls** → **CUT**  
   *Gap:* Backend prohibits write-back. Any "edit" widget would be non-functional (dishonest). Remove entirely; read-only indicators only.

## 3. Full page + subpage tree (sitemap)

```
NR2-OPTICAL-BENCH (nr2-12010-pages)
├── /financial          (Main Bench - nr2-12009-interference layout)
│   └── [Emitters: SoftDent-L, QB-R, Tax-UR, HAL-Center]
├── /softdent           (SoftDent Workbench)
│   ├── /softdent/ledger    (AR Deep Dive - optional anchor)
│   └── /softdent/patients  (Read-only roster)
├── /quickbooks         (QuickBooks Workbench)
│   └── /quickbooks/history (Export logs)
├── /ar                 (AR Observatory)
│   └── /ar/aging       (90/120+ day fringes)
├── /claims             (Claims Kanban)
│   ├── /claims/era     (Film Strip / Microfiche Viewer)
│   └── /claims/pending (Submission queue)
├── /taxes              (Tax Prism Lab)
│   └── /taxes/scenarios (What-if calculations)
├── /narratives         (Narrative Forge)
│   └── /narratives/quarantine (Quarantine Vault)
├── /documents          (Document Vault)
│   └── /documents/library-connection (Link to /library)
├── /library            (Reference Library)
│   └── /library/templates (Narrative templates)
├── /office-manager     (Control Room)
│   ├── /office-manager/rbac (User/Role management)
│   └── /office-manager/scram (Emergency Protocols - pending API)
├── /hal                (HAL Diagnostics)
│   └── /hal/logs       (Reconciliation audit trail)
└── /content            (Sync Health / Beam Alignment Station)
    └── /content/import-readiness (Detailed alignment status)
```

## 4. Per-page briefs (widgets, binds, theme notes)

### /financial (Main Bench)
- **Purpose:** Executive interference pattern—single glance financial health.
- **Widgets:** SoftDent Emitter, QB Emitter, Tax Prism, HAL Core, Master Pulse, Period Wheel, Reconcile Trigger, RBAC Badge, Alignment Lasers.
- **Binds:** All APIs listed in §1 matrix.
- **RBAC:** Universal access with feature gating (buttons disable, never hide).
- **Theme:** Vacuum black #000000; three primary beams converging on HAL center; z-depth layering ensures no emitter occlusion.

### /softdent (SoftDent Workbench)
- **Purpose:** Deep inspection of SoftDent read-only streams without write-back violation.
- **Widgets:** Large-format Period Wheel, AR Pulse Timeline, Patient Roster (read-only), Ledger Grid (empty=∅), Stale Beam Indicator.
- **Binds:** `refresh-period`, ledger read API.
- **RBAC:** `office_manager`, `admin` full; `dentist` view; `front_desk` limited to roster.
- **Theme:** White/blue emission (450nm) bathes left side; "Vacuum Honesty" shader grays out unwritable fields.

### /quickbooks (QuickBooks Workbench)
- **Purpose:** Payroll/AP export control and QB sync health.
- **Widgets:** Gold Beam Status, Export Trigger, Payroll Journal Preview, Connection Health Meter.
- **Binds:** `qb-payroll-ap-export`, sync trigger.
- **RBAC:** `office_manager`, `admin` only.
- **Theme:** Amber/gold housing (590nm) on right flank; rolling phase texture on data tables.

### /ar (AR Observatory)
- **Purpose:** Accounts Receivable aging and honesty visualization.
- **Widgets:** Aging Fringes (30/60/90/120+ buckets), SoftDent Stale Warning, Collections Pulse.
- **Binds:** SoftDent AR read-only.
- **RBAC:** `office_manager`, `admin`, `dentist` (view own production AR only).
- **Theme:** Interferometric "fringes" represent aging buckets; destructive interference (dark bands) = high risk accounts.

### /claims (Claims Kanban)
- **Purpose:** Claims lifecycle management and ERA viewing.
- **Widgets:** Kanban Board (Pending/Sent/Paid/Denied), **Film Strip** (ERA microfiche viewer), Claim Detail Cards.
- **Binds:** Claims read, ERA read.
- **RBAC:** `office_manager`, `admin`, `front_desk` (limited).
- **Theme:** Cyan beam accents; film strip widget uses horizontal scroll with "sprocket hole" optical motif.

### /taxes (Tax Prism Lab)
- **Purpose:** Tax planning calculations and scenario modeling.
- **Widgets:** Prism Refractor (scenario selector), Calculation Output Grid, Confidence Spectrum.
- **Binds:** `tax/calculate-planning`.
- **RBAC:** `admin`, `office_manager`.
- **Theme:** Violet/indigo upper-right motif extended to full page; spectral dispersion visualizes tax brackets.

### /narratives (Narrative Forge)
- **Purpose:** Insurance narrative generation and editing.
- **Widgets:** Text Forge (editor), AI Generate Trigger, **Quarantine Vault** toggle.
- **Binds:** Narrative generate API, quarantine release API.
- **RBAC:** `dentist`, `admin`, `office_manager`; `hygienist` (own narratives only).
- **Theme:** Monospace "terminal green" text on black; quarantine items appear behind "frosted glass" optical barrier.

### /documents (Document Vault)
- **Purpose:** Document storage and retrieval.
- **Widgets:** Vault Grid, Tagging Laser (filter beam), Preview Aperture.
- **Binds:** Document storage API (implied, not listed in provided APIs—mark as deferred if unavailable).
- **RBAC:** All roles (document-level ACL).
- **Theme:** Silver/gray neutral beams; film strip integration for multi-page preview.

### /library (Reference Library)
- **Purpose:** Template and reference material repository.
- **Widgets:** Card Catalog Search, Template Emitter, Preview Pane.
- **Binds:** Static content (no live financial APIs).
- **RBAC:** Universal read; `admin` write.
- **Theme:** Warm white reading light aesthetic against vacuum black.

### /office-manager (Control Room)
- **Purpose:** RBAC management and emergency protocols.
- **Widgets:** User Matrix, Role Assignment Beams, **SCRAM Panel** (inactive until API ready), Audit Log.
- **Binds:** RBAC admin APIs (implied), SCRAM (pending).
- **RBAC:** `admin` only; `office_manager` limited subset.
- **Theme:** Red safety lighting; SCRAM button under physical "break glass" UI metaphor.

### /hal (HAL Diagnostics)
- **Purpose:** AI core introspection and reconciliation audits.
- **Widgets:** Interference Pattern Visualizer (history), Board Actions Log, Confidence Heatmap.
- **Binds:** `hal/board-actions`, reconciliation logs.
- **RBAC:** `admin` full; `office_manager` view logs.
- **Theme:** Central HAL motif expanded to fill viewport; spectral analysis UI.

### /content (Sync Health / Beam Alignment Station)
- **Purpose:** Import readiness and system alignment details.
- **Widgets:** **Alignment Lasers** (expanded view), Import Readiness Dashboard, Sync Logs.
- **Binds:** `import-readiness`, sync trigger.
- **RBAC:** `admin`, `office_manager`.
- **Theme:** Green coherent beam visualizations; "photon counter" metaphor for record counts.

## 5. Navigation / shell chrome (same theme)

**Beam Transit Protocol:**
- **Persistent HUD:** Top 48px "Vacuum Bar"—vacuum black with subtle interference fringe texture.
  - Left: RBAC Role Indicator (cryptographic badge).
  - Center: Mini-HAL status (monochromatic when on subpage).
  - Right: "Return to Main Bench" button (appears as "Home Beam" collimator).
- **Subpage Entry:** Clicking any main-bench emitter "opens the beam path"—page transition uses optical blur/diffraction animation maintaining color coherence (SoftDent=white/blue, QB=gold, etc.).
- **Honesty Lock:** If `import-readiness` fails, all transit to financial-critical pages blocked by "Beam Scatter" error state (red interference pattern overlay).
- **Typography:** 
  - Data: `Roboto Mono` (legible, fixed-width for financial alignment).
  - Labels: `Inter` (clean sans, high contrast against #000).
- **Z-Index Rules:** 
  - Emitters always top-layer (z:1000).
  - Modals appear as "Lens Filters" (glassmorphism with optical aberration).

## 6. Implementation order (phased)

**Phase 1: Main Bench Honesty (Week 1)**
- Wire all BINDABLE widgets from §1.
- Implement `import-readiness` gating for Master Pulse.
- Apply "dim filament" shader for SoftDent stale states.
- **Schema target:** nr2-12010-pages-alpha

**Phase 2: Critical Sub-benches (Weeks 2-3)**
- Build `/softdent` (read-only ledger) and `/hal` (diagnostics).
- Connect Period Wheel deep-link from main to subpage.
- **Deferred:** SCRAM (pending API).

**Phase 3: Financial Flow (Weeks 4-5)**
- Build `/quickbooks` and `/ar`.
- Implement QB payroll export with gold beam confirmation pulse.
- AR aging "fringe" visualization.

**Phase 4: Compliance & Productivity (Weeks 6-7)**
- Build `/claims` (with Film Strip migration) and `/taxes`.
- Build `/narratives` with Quarantine Vault.

**Phase 5: Administration (Week 8)**
- Build `/office-manager` (RBAC matrix).
- Build `/documents` and `/library`.
- Placeholder SCRAM panel (disabled pending backend).

**Phase 6: Polish (Week 9)**
- Navigation transitions (Beam Transit).
- Alignment Lasers full integration on `/content`.
- Final vacuum honesty audit (empty≠$0 verification).

## 7. Schema bump justification

**nr2-12009-interference → nr2-12010-pages**

The bump from `interference` (layout geometry) to `pages` (surface architecture) signifies:
1. **Widget Audit Completion:** 8 of 11 widgets validated as bindable; 3 honestly deferred.
2. **Program Surface Completeness:** All 12 required Apex page IDs mapped to optical theme.
3. **Navigation Topology Defined:** "Beam Transit" protocol ensures theme continuity across sub-benches.
4. **Honesty Enforcement:** SoftDent write-back permanently excluded; empty-state handling specified.
5. **RBAC Integration:** Role-based feature gating specified per surface.

## 8. Executive Summary (7 bullets)

- **All critical main-bench widgets bindable** to existing APIs; only SCRAM (no API) and Film Strip (density) require relocation.
- **12-page optical tree defined** covering financial, operational, and administrative surfaces while preserving vacuum-black interferometer aesthetic.
- **SoftDent remains strictly read-only** with visual "dim beam" honesty indicator for stale data; no write-back widgets permitted.
- **Navigation uses "Beam Transit" metaphor**—emitters open coherent paths to subpages without breaking optical theme.
- **SCRAM emergency control deferred** to Office Manager subpage pending `emergency-halt` API specification; prevents ornamental dishonesty on main bench.
- **Film Strip (ERA viewer) migrated** to Claims subpage, maintaining main bench cleanliness for executive overview.
- **Schema nr2-12010-pages** represents complete program architecture ready for phased implementation.

## 9. Approval checklist

- [ ] **Widget Audit:** All 11 widgets reviewed; BINDABLE/NEEDS SUBPAGE/CUT statuses accepted.
- [ ] **API Coverage:** All provided endpoints mapped to specific widgets; no orphaned controls.
- [ ] **Page Tree:** 12 required Apex IDs accounted for in sitemap.
- [ ] **Theme Continuity:** Vacuum black, beam optics, and HAL presence approved for all subpages.
- [ ] **Honesty Constraints:** SoftDent write-back absent; empty-state "∅" convention accepted.
- [ ] **RBAC Matrix:** Role access per page matches operational security requirements.
- [ ] **Implementation Order:** Phased approach feasible with current runtime build (nr2-11000-clean).
- [ ] **Schema Stamp:** nr2-12010-pages locked for development reference.
