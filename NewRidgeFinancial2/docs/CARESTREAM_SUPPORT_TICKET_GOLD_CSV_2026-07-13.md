# Carestream SoftDent Support Ticket — Line-item Insurance Payment CSV

**Status:** SUBMIT PACK READY — awaiting staff portal submit + case number  
**Date:** 2026-07-13 (refreshed with 32B program fixes OPS close-out)  
**Practice:** New Ridge Family Dental  
**SoftDent:** CS SoftDent Software **v19.1.4**  
**Product need:** Line-item insurance payment export for analytics ingest (not Print Preview totals)  
**Submit pack:** `C:\SoftDentFinancialExports\CARESTREAM_GOLD_CSV_TICKET_PACK_2026-07-13\`  
**Support hub:** https://www.carestreamdental.com/en-us/support/  
**Customer portal:** https://www.carestreamdental.com/en-us/portal/portal-home/  
**SoftDent phone:** (866) 435-7473  
**OPS log:** `docs/MOONSHOT_OPS_CARESTREAM_TICKET_SUBMIT_2026-07-13.md`  
**carestreamCaseNumber:** _(pending staff)_  
**NR2 honesty:** gapCode stays `GOLD_CSV_MISSING` / `paymentLines=0` until a real CSV lands — empty ≠ $0; no invented payment lines.  
**Note:** `support.carestreamdental.com` does not resolve (DNS NXDOMAIN).

---

## Subject

SoftDent v19.1.4 — Insurance Income / Payment reports have no Excel export; need line-item Insurance Payment Analysis CSV (InsCo × ADA × Paid)

---

## Body (copy/paste)

We run SoftDent **v19.1.4**. We need a **line-item** export of insurance payments for practice analytics (one row per procedure/payment allocation), not report summary totals.

### What we already tried (confirmed live)

On this install, **Output Options shows only Printer + Print Preview** (Excel control missing / unavailable) for:

1. Reports → Practice Management → Insurance Reports → **Insurance Income**
2. Reports → Practice Management → Production Reports → **Payment Allocation**
3. Reports → Practice Management → Insurance Reports → **Contractual Plan Analysis**
4. Reports → Accounting → **Insurance Payment Distribution**

There is **no** menu item named “Insurance Payment Analysis” on v19.1.4.

Print Preview last-page visual aggregate for Insurance Income (period shown 07/13/26–07/13/26 on one run) was approximately **TOTAL PAYMENTS $641,566.92** / **TOTAL ADJUSTMENTS $7,274.69**. We treat that as visual truth only — we **cannot** invent line items from that total.

### What we need from Carestream

Please provide one of:

**A. Product export path** that writes a **CSV/Excel with line items** (InsCo, ADA/CDT, Paid, dates, claim/check if available) for insurance payments over a selectable date range (prefer last 24 months), **or**

**B. Documented read-only SQL/ODBC query** against SoftDent tables that yields the same line items (table/column names for this version), **or**

**C. Enabling Excel output** on Insurance Income / Payment Allocation / equivalent report if it is a license/module/security setting.

### Required CSV columns (minimum)

| Column (any of these header aliases OK) | Required |
|-----------------------------------------|----------|
| Insurance Company / InsCo / Payer / Carrier | **Yes** |
| Procedure Code / ADA Code / CDT / ProcCode | **Yes** |
| Paid Amount / Ins Paid / PaymentAmount | **Yes** |
| Submitted Fee / Allowed / Write-Off / Patient Portion | Recommended |
| Claim Number / Check or EFT # / Payment Date | Recommended |

Drop/save target on our side: `C:\SoftDentFinancialExports\insurance_payments_YYYYMMDD.csv`

We will **not** use Printer output. Print Preview alone cannot populate our line database.

### Environment notes

- SoftDent launched via **CS SoftDent Software.lnk** (`-sus`)
- Financial analytics host has ODBC drivers installed, but **no SoftDent SQL DSN is configured yet** — we can set up a read-only DSN if Carestream documents the correct instance/tables
- Sensei DataSync mirror path historically used for other extracts; we still need **InsCo×ADA paid lines**, which Sensei/day-sheet lanes do not supply as gold payment lines

Thank you — please advise the supported path for v19.1.4 line-item insurance payment export.

---

## Staff checklist after Carestream replies

1. [ ] Save reply / export instructions in this folder
2. [ ] Land file as `C:\SoftDentFinancialExports\insurance_payments_YYYYMMDD.csv`
3. [ ] Confirm headers include InsCo + ADA + Paid (line items, not one total row)
4. [ ] Run Apex Sync or `POST /api/apex/gold-era-settlement/run`
5. [ ] Confirm settlement matrix fills and gapCode leaves `GOLD_CSV_MISSING`

### Staff path until then

1. Open Carestream customer portal (link above)
2. Submit using this ticket body; record **carestreamCaseNumber** here when assigned
3. Pack folder already staged — attach screenshots from the pack if portal asks
4. HAL: ask “gold csv drop ops” for live gapCode / pack path reminder
