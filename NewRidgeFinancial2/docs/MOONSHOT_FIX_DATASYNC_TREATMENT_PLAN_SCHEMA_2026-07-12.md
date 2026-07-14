# Fix — SoftDent DataSync importer schema crash (2026-07-12)

**Symptom:** Daily / 45-minute SoftDent refresh failed twice with:
`sqlite3.OperationalError: table treatment_plan_summary has no column named provider_id`

**Root cause:** `softdent_datasync_financial_importer.py` inserted `provider_id` / `provider_name` into live `treatment_plan_summary`, which only has the older column set (no provider fields).

**Fix:** Schema-tolerant insert — `filter_existing_columns()` keeps only columns present on the live SQLite table before `INSERT OR REPLACE`.

**File:** `C:\New folder\ops\softdent\datasync\softdent_datasync_financial_importer.py`

**Validation:**
```text
python ops\softdent\datasync\softdent_datasync_financial_importer.py --apply
→ EXIT=0 (Mode: APPLY; treatment plan / payment plan import succeeds)
```

## Still open (Moonshot OPS — unchanged)

July Collections/Register export is still missing. SoftDent is open, but inbox has no `07/01/2026→today` Register/Collections CSV. This fix unblocks the refresh pipeline; it does **not** invent July Ins/Patient dollars.
