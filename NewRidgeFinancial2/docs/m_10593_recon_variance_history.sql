-- HAL-10593 / HON-003 — recon_variance_history (PHI-safe aggregates only)
-- HAL-10594 / sql-null-honesty — record_fingerprint (inputs-only) + money_scale
-- Applied via softdent_visual_ledger_recon.ensure_recon_variance_history_schema
-- No patient/account/PHI columns. triggers_gold_ingest always 0.
--
-- Money honesty notes (HAL-10594):
--   visual_total / ledger_total / clamped_ledger_total are REAL (JSON float
--   bridge via money_to_api) — approximate for external consumers.
--   variance_dollars is derived from Decimal cent math before serialization.
--   Internal compare uses Decimal; do not re-derive MATCH from these floats alone.
--   record_fingerprint = SHA-256 of inputs only (period/visual/ledger/scope/build/scale);
--   UNIQUE INDEX prevents silent overwrite on collision.

CREATE TABLE IF NOT EXISTS recon_variance_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    period_start TEXT,
    period_end TEXT,
    visual_total REAL,
    ledger_total REAL,
    clamped_ledger_total REAL,
    variance_dollars REAL,
    top_carrier_code TEXT,
    scope_mismatch INTEGER NOT NULL DEFAULT 0,
    result_code TEXT,
    created_at TEXT NOT NULL,
    package_build_id TEXT,
    triggers_gold_ingest INTEGER NOT NULL DEFAULT 0,
    record_fingerprint TEXT,
    money_scale TEXT DEFAULT '0.01'
);

CREATE INDEX IF NOT EXISTS idx_recon_variance_history_created
    ON recon_variance_history(created_at DESC);

CREATE UNIQUE INDEX IF NOT EXISTS idx_recon_variance_history_record_fp
    ON recon_variance_history(record_fingerprint)
    WHERE record_fingerprint IS NOT NULL;
