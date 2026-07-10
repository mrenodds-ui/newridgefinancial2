# Moonshot AI — Widget Ideas vs NR2-Apex Schema (CONSULT ONLY)

**Date:** 2026-07-10  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Endpoint:** https://api.moonshot.ai/v1/chat/completions  
**Status:** ok  
**Build reviewed:** hal-10240  
**Script:** `scripts/run_moonshot_widget_ideas_consult.py`  
**Apply:** DO NOT APPLY until operator validates.

## Operator request (verbatim)

> ask moonshot ai about these widget ideas - Personal Finance & Mobile Home Screen WidgetsThese smartphone widgets leverage deep AI connections to link directly to your bank accounts and forecast cash flow.Origin: Best for full-context financial reasoning across spending, taxes, and retirement tracking. Its interactive UI functions like a true financial command center. Check out the platform directly at Origin.Copilot Money: Features advanced lock screen spending summaries and automated transactional categorization. Built seamlessly with local AI processing on Apple devices. Find download options on Copilot Money.Monarch Money: Provides real-time budget progress metrics directly on your home screen. It utilizes predictive algorithms to alert you of upcoming bills before they happen. Learn more at Monarch Money.PocketGuard: Employs an automated “In My Pocket” algorithmic summary. It instantly factors in recurring bills to show disposable daily cash. Get started with PocketGuard.2. Embeddable Web & Fintech WidgetsIf you are looking to install high-tech widgets onto a website, blog, or application dashboard, these tools deploy with single-line JavaScript code.TradingView Widgets: High-velocity interactive charting tools that allow web visitors to map technical indicators instantly. Explore configurations via TradingView Widgets.Investing.com Tools: Offers an auto-refresh economic calendar widget that updates within one second of global events. Grab the raw embed code at Investing.com Webmaster Tools.theFinancials Custom Widgets: High-frequency streaming data modules covering Treasuries, Swaps, SOFR, and indices. They update up to every 7 minutes. Review documentation at theFinancials.Chimney Widgets: Highly interactive, responsive lead-generation calculators built to run natively inside bank-grade apps. View deployment templates at Chimney.io.How to Choose Your SetupFeature FocusSuggested TechnologyDeployment TypePersonal Wealth AutopilotOrigin / Copilot MoneyiOS / Android App WidgetLive Multi-Asset StreamingTradingView / theFinancialsHTML / JS SnippetInstant Real-Time CalendarsInvesting.comWeb Component and can he use any of these in the current schema with a pages to boost visual information.

---

# Verdict

## 0. Operator Intent (quote; confirm consult-only)

> *"ask moonshot ai about these widget ideas - Personal Finance & Mobile Home Screen Widgets... Embeddable Web & Fintech Widgets... can he use any of these in the current schema with a pages to boost visual information."*

**Confirmed:** This is a **consult-only** evaluation. No code changes, embeds, or schema modifications will be applied to the live `hal-10240` build. The following assesses whether the listed commercial products (mobile apps and third-party JS widgets) can be utilized within the NR2-Apex bridge architecture.

---

## 1. Product-by-Product Fit Matrix

| Product | Fit | Why | Risk | Borrowable Idea for NR2 |
|---------|-----|-----|------|-------------------------|
| **Origin** | **NO** | Mobile-native app requiring Plaid/Yodlee bank OAuth; designed for consumer retirement/tax tracking, not practice A/R. | PHI leakage via bank aggregators; OAuth scope creep; projection algorithms invent forward-looking dollars not in SoftDent/QB. | "Command Center" density — arrange existing KPIs in a tactical grid (C2-style) on the Financial page. |
| **Copilot Money** | **NO** | iOS lock-screen widget; Apple Secure Enclave local AI; requires consumer credit card/bank linking. | Platform mismatch (iOS vs Windows desktop); NR2 has no lock-screen context. | "At-a-glance" summary tile concept — a single mosaic instrument showing "Last 24h Changes" populated by HAL from import diffs. |
| **Monarch Money** | **PARTIAL** | Predictive bill alerts are conceptually adaptable to practice obligations, but requires training on bank transaction history. | Bank API dependency; prediction models may hallucinate obligations not in QB payables. | "Obligation Horizon" progress bars — visualize tax quarters or claims aging as filling bars rather than static numbers. |
| **PocketGuard** | **PARTIAL** | "In My Pocket" disposable cash algorithm assumes personal spending patterns; not applicable to business overhead. | Daily disposable cash is meaningless for accrual-based dental practices; risk of inventing spendable dollars. | "Net Collectible" headline — single-number calculation: `(A/R Outstanding - Expected Denials) - Overhead Burn`. |
| **TradingView Widgets** | **NO** | Trading/forex technical analysis with high-velocity ticks; requires market data subscriptions. | CSP violation (external JS); irrelevant asset class (dental practices do not chart EUR/USD or S&P futures); offline breakage. | None — technical candlestick charts are anti-pattern for practice financials. |
| **Investing.com Tools** | **NO** | Global macro economic calendar (Fed speeches, NFP, etc.); 1-second refresh. | CSP violation; streaming external data leaks IP/usage patterns; zero relevance to insurance claim lag or patient collections. | None — macro events do not impact daily dental operations. |
| **theFinancials Custom Widgets** | **NO** | Institutional capital markets data (SOFR, Treasuries, Swaps); 7-minute refresh. | Licensing cost; CSP; Treasuries rates do not explain A/R aging; violates "no invented market context" rule. | None — swaps and SOFR are noise to practice cash flow. |
| **Chimney Widgets** | **PARTIAL** | Calculator widgets designed for mortgage/lead-gen in bank apps; responsive UI pattern is sound. | Lead-gen focus mismatch (NR2 has no mortgages); external JS embed violates CSP; PHI risk if patient data entered into third-party calculator. | Interactive calculator **instrument pattern** — locally-hosted JS calculators for Treatment Plan estimates or Insurance Coverage math (no external POST). |

---

## 2. What Can Be Used In Current Schema (concrete)

**Nothing from the list can be embedded as a third-party JS snippet or mobile app.** However, the following **concepts** can be adapted into native Apex instruments using existing SoftDent/QB import data:

*   **Monarch-style "Progress Bars"** → Replace static "Claims Open" number with a segmented bar showing volume moving through 0-30, 31-60, 61-90, 90+ buckets.
*   **PocketGuard-style "Net Position"** → Add a calculated field to the Financial page mosaic: `Collections MTD - (QB Overhead MTD)` = "Net Operating Position."
*   **Origin-style "Command Center Density"** → Resize existing financial widgets to a compact 4×4 grid (reduced padding, smaller typography) to mimic the "full-context" density of tactical displays.
*   **Chimney-style "Interactive Calculators"** → Build local HTML forms (no external POST) within the "Office Mgr" page to model "What-if" treatment plan costs using practice fee schedules from SoftDent imports.

---

## 3. What Must NOT Be Embedded (and why)

| Prohibition | Reason |
|-------------|--------|
| **Bank-linking OAuth flows** (Origin, Copilot, Monarch, PocketGuard) | NR2 is **not** a consumer wealth app. Practice books live in QuickBooks Desktop (imported), not Plaid-connected checking accounts. OAuth scopes would require PCI/PHI compliance audits impossible on localhost. |
| **Market data widgets** (TradingView, Investing.com, theFinancials) | Dental practices do not trade forex or monitor SOFR. These widgets violate Content Security Policy (CSP), break offline functionality, and introduce irrelevant noise that distracts from A/R and claims metrics. |
| **Third-party JS calculators** (Chimney embeds) | External `<script>` tags bypass the `hal-10240` CSP. Patient data entered into Chimney calculators would constitute a PHI breach (Business Associate Agreement required). |
| **Mobile-only lock screen widgets** (Copilot) | NR2 runs on Windows desktop as a Bottle HTTPS localhost app; iOS widgets cannot be rendered in a Chrome/Electron shell. |
| **Predictive algorithms with external training** (Origin, Monarch) | These services train on aggregated consumer spending datasets. Their projections **invent dollar amounts** not present in SoftDent/QB imports, violating the NR2 rule: *"prefer import-backed data; never invent financial dollar amounts."* |

---

## 4. Recommended Visual Boosts Per Apex Page

| Apex Page | Current State | Visual Boost (Inspired By) | Implementation (Native) |
|-----------|---------------|---------------------------|-------------------------|
| **Financial** | 10 fixed mosaic tiles (prod, coll, A/R, etc.) | **Origin "Command Center" density** + **Copilot "Lock Screen" brevity** | Compact grid layout; add "Morning Brief" tile (HAL-generated delta from yesterday's imports). |
| **Taxes** | Static tax estimates and disclaimers | **Monarch "Upcoming Bills" timeline** | Horizontal timeline instrument showing Q1-Q4 estimate due dates with progress bars filling based on QB net income accrued to date. |
| **A/R** | Aging chart + outstanding list | **PocketGuard "Single Number" clarity** | Large "Net Collectible" headline tile above the chart: `(Total A/R - 90+ Vintage) - Known Bad Debt Reserve`. |
| **Claims** | Counts of open/denied/aging | **Monarch "Budget Progress" bars** | Stacked bar instrument: claims volume visualized as flow from "Open → Submitted → Pending → Paid/Denied." |
| **Office Mgr** | Static links/docs | **Chimney "Calculator" interactivity** | Local JS calculator for "Patient Responsibility Estimator" using imported fee schedules and insurance matrices (no external API). |
| **HAL** | Chat + 4 mosaic summaries | **Copilot "Automated Categorization"** | Button to auto-tag uncategorized QB transactions using local Ollama inference on memo/description fields. |

---

## 5. New Instrument Ideas (Apex-native, import-backed)

These instruments capture the **UX value** of the evaluated products without requiring bank OAuth, market data subscriptions, or external JS.

### 1. `liquidity-pulse` (Financial Page)
**Inspired by:** Origin forecasting + PocketGuard daily summary  
**Payload:**
```json
{
  "instrument": "liquidity-pulse",
  "projection_days": 30,
  "projected_cash": 45230.00,
  "confidence": "medium",
  "based_on": ["qb_check_register", "softdent_collections_90d_history"],
  "known_payables": 12400.00,
  "hal_narrative": "Based on historical collection velocity, expect $45K liquid by Aug 15. Note: $12.4K in scheduled payables."
}
```
**Rule:** Projection uses only historical collections lag (SoftDent) and scheduled QB bills. **No bank balance API calls.**

### 2. `collectible-remainder` (A/R Page)
**Inspired by:** PocketGuard "In My Pocket"  
**Payload:**
```json
{
  "instrument": "collectible-remainder",
  "gross_ar": 89000.00,
  "expected_denials": 12300.00,
  "overhead_burn_daily": 2400.00,
  "net_collectible": 76700.00,
  "days_of_operating_cash": 31.9
}
```

### 3. `claims-velocity-funnel` (Claims Page)
**Inspired by:** Monarch progress bars  
**Payload:**
```json
{
  "instrument": "claims-velocity-funnel",
  "stages": [
    {"stage": "open", "count": 45, "avg_age_days": 12},
    {"stage": "submitted", "count": 120, "avg_age_days": 8},
    {"stage": "pending", "count": 34, "avg_age_days": 22},
    {"stage": "paid_last_7d", "count": 89, "avg_payment_lag_days": 14}
  ],
  "carrier_velocity": [
    {"carrier": "Delta Dental", "avg_days": 12},
    {"carrier": "MetLife", "avg_days": 23}
  ]
}
```

### 4. `obligation-countdown` (Taxes Page)
**Inspired by:** Monarch bill alerts  
**Payload:**
```json
{
  "instrument": "obligation-countdown",
  "next_deadline": "2026-09-15",
  "days_remaining": 67,
  "estimated_liability": 15400.00,
  "safe_harbor_110_prior_year": 14000.00,
  "safe_harbor_met": false,
  "quarter": "Q3"
}
```

### 5. `ar-heatmap-grid` (A/R Page)
**Inspired by:** TradingView density (sans candles)  
**Payload:**
```json
{
  "instrument": "ar-heatmap-grid",
  "grid": [
    {"patient_id": "P-1024", "balance": 1200.00, "age_bucket": "61-90", "last_contact": "2026-06-01", "risk_score": "high"},
    {"patient_id": "P-2048", "balance": 450.00, "age_bucket": "0-30", "last_contact": "2026-07-09", "risk_score": "low"}
  ],
  "filters": ["age_bucket", "last_contact", "balance_threshold"]
}
```
**Note:** Color-coding based on practice-defined rules, not external market indicators.

---

## 6. Implementation Phases (optional; DO NOT APPLY until operator validates)

If the operator approves the visual boosts above:

1. **Phase V1:** CSS-only density adjustments (Financial page mosaic compaction) — zero backend risk.
2. **Phase V2:** New backend endpoints in `apex_backend.py` to calculate `liquidity-pulse` and `collectible-remainder` from existing import caches — no new data sources.
3. **Phase V3:** Frontend instrument components for `claims-velocity-funnel` and `ar-heatmap-grid` — vanilla JS, no external dependencies.
4. **Phase V4:** HAL integration for automated transaction categorization (local Ollama inference) — runs offline, no API keys.

**Do not proceed** to embedding TradingView, Chimney JS, or bank OAuth without architectural epoch change and compliance review.

---

## 7. Risks & Alternatives

| Risk | Mitigation |
|------|------------|
| **PHI Leakage** | Never embed third-party JS that could access DOM patient data. Use local HAL/Ollama for AI features (offline). |
| **CSP Violations** | `hal-10240` enforces strict script sources. All "widget" concepts must be rebuilt as native Apex instruments. |
| **Invented Dollars** | Reject any product requiring "forecasting" not based on imported SoftDent/QB history. |
| **Offline Breakage** | Investing.com and theFinancials require persistent internet. NR2 must function during ISP outages (local HAL, local Bottle server). |
| **Licensing Bloat** | TradingView/theFinancials require paid market data licenses. Use static, import-derived visualizations instead. |

**Alternative:** If the operator desires "rich charting," upgrade the existing `apex-chart-widget.js` to use **Chart.js** (locally hosted) with SoftDent production data, rather than importing TradingView candlesticks.