# Import Health + CPA Tax/EBITDA UX — Applied

**Date:** 2026-07-10  
**Build:** **hal-10350**  
**Consult:** `MOONSHOT_IMPORT_HEALTH_CPA_TAX_CONSULT_2026-07-10.md`  
**Status:** All NR2 code recommendations complete. July SoftDent collections still need a SoftDent UI Register export.

## Operator unblock (C0 data)

1. SoftDent → **Reports → Accounting → Register for a Period**  
   Range: **07/01/2026 → today** → save CSV to `C:\SoftDentReportExports`
2. Optional: Daysheet + Trans for a Period (same range)
3. In Apex Taxes: **Refresh SoftDent period imports** (C0 widget) or ask HAL: “Refresh SoftDent period imports”

Automation confirms: `missingPeriods` still lists **2026-07** until that Register file exists. SoftDent CLI auto-export remains disabled (no vendor command).

## In-app complete (C0–C4)

- C0 honesty + operatory date filter + period refresh path  
- C1 EBITDA scrubber  
- C2 workpapers + citation drill-down  
- C3 scenarios + FILED↔library  
- C4 variance, voice-to-slider, A/R outlook  
