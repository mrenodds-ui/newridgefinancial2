# Moonshot Inbox Sync Coherence — APPLIED

**Date:** 2026-07-11  
**Consult:** `MOONSHOT_WHATS_NEXT_AFTER_COMPACT_2026-07-11.md`  
**Build:** `hal-10560`  
**Operator:** next → proceed with inbox sync coherence  

## Problem

SoftDent AR / dashboard and QB expenses flapped between syncs because:
1. Retention `purge_import_cache` wiped **all** inbox files
2. Writers always truncated/rewrote even when bytes unchanged
3. QB SDK probe overwrote Period-based expenses with TotalExpense-only shape
4. Direct-first cache mirror reshaped dashboard JSON (`{rows:…}` vs array)

## Fix

| Change | File |
|--------|------|
| Soft-skip retention wipe when SoftDent AR+dashboard present; always preserve critical filenames | `import_cache_ttl.py` |
| Content-hash no-op `_write_json` / `_write_csv` | `import_sync.py`, `quickbooks_monthly_sync.py` |
| Dashboard period sync writes only when changed | `softdent_dashboard_period_sync.py` |
| SDK summary does not thrash Period expenses | `import_sync.py` |
| Direct-first mirror skips existing critical filenames | `import_loader.py` |
| Unit gates | `test_inbox_sync_coherence.py` |

## Validation

```text
python -m unittest test_inbox_sync_coherence -q
```

- Critical files survive `purge_import_cache(preserve_criticals=True)`
- Expired manifest + criticals → `retention-soft-skip-criticals-present`
- Identical write → no mtime/content change

## Honesty

Empty ≠ $0. Coherence keeps real imports on disk; it does not invent dollars.
