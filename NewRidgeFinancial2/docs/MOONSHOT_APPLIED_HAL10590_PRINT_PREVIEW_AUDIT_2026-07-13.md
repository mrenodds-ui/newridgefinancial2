# HAL-10590 / OPS-10590 — SoftDent Print Preview Visual-Audit Protocol (applied)

**Date:** 2026-07-13  
**Prior consult:** `MOONSHOT_WHATS_NEXT_AFTER_HAL10589_2026-07-13.md`  
**Operator:** `proceed`  
**BUILD_ID:** `hal-10590`

## What shipped

| Piece | Location |
|-------|----------|
| Audit module | `softdent_print_preview_audit.py` — PHI-safe schema, JSONL append, status |
| Widget | `softdent-print-preview-audit` |
| API | `GET /api/apex/print-preview-audit/status`, `POST .../record`, `POST .../run` |
| HAL | `policy:print-preview-audit` |
| Sync | `import_sync.py` → status snapshot (`triggersGoldIngest=false`) |
| Playbook extension | `gold_csv_drop_playbook()["whenPrintPreviewOnly"]` |
| Tests | `test_print_preview_audit_hal10590.py` |
| Log | `C:\SoftDentFinancialExports\print_preview_audit_log.jsonl` |

## Behavior

- Staff records **last-page aggregate** Insurance Income (or related report type) after Print Preview → PageDown → last page.  
- Confirmation: *This is a visual audit only; no payment lines will be created.*  
- `sourceTag=print_preview_visual`; `triggersGoldIngest=false`.  
- Live `gapCode` remains `GOLD_CSV_MISSING`; `paymentLines` stays `0` (empty ≠ $0).  
- Rejects missing totals and obvious PHI (patient/account/DOB) in notes.

## Honesty

No SoftDent write-back. Visual audit ≠ gold CSV ingest. Excel still unavailable for Insurance Income on SoftDent v19.1.4.
