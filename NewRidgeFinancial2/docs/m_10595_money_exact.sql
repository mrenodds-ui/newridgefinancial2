-- HAL-10595 / money-bridge-bijection — exact cent storage (dual-write)
-- Applied via softdent_visual_ledger_recon.ensure_recon_variance_history_schema
-- and scripts/migrate_history_to_exact.py
--
-- REAL visual_total/ledger_total/clamped_ledger_total/variance_dollars retained
-- for backward-compatible float consumers (DEPRECATED for exact arithmetic).
-- Prefer *_cents INTEGER / money_cents_exact for bijective money.
-- money_cents_exact mirrors ledger_total_cents (primary total_cents).
-- Do NOT backfill cents by copying REAL floats — recompute from Decimal sources.
-- No patient/account/PHI columns. triggers_gold_ingest always 0.

ALTER TABLE recon_variance_history ADD COLUMN visual_total_cents INTEGER;
ALTER TABLE recon_variance_history ADD COLUMN ledger_total_cents INTEGER;
ALTER TABLE recon_variance_history ADD COLUMN clamped_ledger_total_cents INTEGER;
ALTER TABLE recon_variance_history ADD COLUMN variance_cents INTEGER;
ALTER TABLE recon_variance_history ADD COLUMN money_cents_exact INTEGER;
