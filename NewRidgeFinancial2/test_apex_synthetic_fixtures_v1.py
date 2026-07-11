"""Phase V1 — synthetic fixture validation (reconciliation math, ERA PHI-safe)."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

# Ensure fixtures package importable
_FIXTURES = Path(__file__).resolve().parent / "test" / "fixtures"
if str(_FIXTURES) not in sys.path:
    sys.path.insert(0, str(_FIXTURES))

from generate_synthetic_nr2 import (  # noqa: E402
    MOONSHOT_DOC_PAYROLL,
    MOONSHOT_DOC_PROD,
    QUIET_PAYROLL,
    QUIET_PROD,
    load_fixture,
    noisy_bundle,
    quiet_bundle,
    synthetic_era835_text,
    write_fixtures,
)

from apex_backend import BUILD_ID
from apex_era835_pack import ingest_era835_to_unified, parse_era835_text
from apex_reconciliation_pack import (
    GAP_RECON_VARIANCE,
    check_production_payroll_variance,
    run_reconciliation,
)
from apex_unified_db_pack import ingest_from_bundle, list_production_vs_payroll


class SyntheticFixturesPhaseV1Tests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = Path(self._tmpdir.name) / "nr2_unified_v1.db"
        self.fix_out = Path(self._tmpdir.name) / "fixtures"

    def tearDown(self) -> None:
        try:
            self._tmpdir.cleanup()
        except Exception:
            pass

    def test_build_id(self):
        self.assertEqual(BUILD_ID, "hal-10488")

    def test_write_and_load_fixtures(self):
        paths = write_fixtures(out_dir=self.fix_out)
        self.assertTrue(paths["quiet_mom.json"].is_file())
        self.assertTrue(paths["noisy_mom.json"].is_file())
        self.assertTrue(paths["synthetic.835"].is_file())
        quiet = json_load(paths["quiet_mom.json"])
        self.assertTrue(quiet.get("meta", {}).get("anonymized"))
        blob = str(quiet)
        self.assertNotIn("Doe", blob)
        self.assertNotIn("SSN", blob)

    def test_moonshot_doc_gap_math(self):
        gap = (MOONSHOT_DOC_PROD - MOONSHOT_DOC_PAYROLL) / MOONSHOT_DOC_PROD
        self.assertAlmostEqual(gap, 0.03, places=4)
        self.assertLess(gap, 0.05)

    def test_quiet_mom_no_false_positive(self):
        bundle = quiet_bundle()
        meta = bundle["meta"]["expected"]
        self.assertAlmostEqual(float(meta["production"]), QUIET_PROD)
        self.assertAlmostEqual(float(meta["payroll"]), QUIET_PAYROLL)
        self.assertLess(float(meta["payrollShare"]), 0.5)

        got = ingest_from_bundle(bundle, db_path=self.db_path)
        self.assertTrue(got.get("ok"))
        rows = list_production_vs_payroll(limit=5, db_path=self.db_path)
        self.assertTrue(rows)
        june = next((r for r in rows if r.get("period") == "2026-06"), rows[0])
        self.assertAlmostEqual(float(june.get("totalProduction") or 0), QUIET_PROD, delta=1.0)
        self.assertAlmostEqual(float(june.get("totalPayroll") or 0), QUIET_PAYROLL, delta=1.0)

        finding = check_production_payroll_variance("2026-06", db_path=self.db_path)
        self.assertFalse(finding.get("alert"), msg=str(finding))
        scan = run_reconciliation(
            period="2026-06",
            classify_only=True,
            explain=False,
            db_path=self.db_path,
        )
        prod_alerts = [
            a
            for a in (scan.get("alerts") or [])
            if a.get("kind") == "production_vs_payroll" and a.get("gapCode") == GAP_RECON_VARIANCE
        ]
        self.assertEqual(prod_alerts, [], msg=str(scan.get("alerts")))

    def test_noisy_mom_detects_variance(self):
        bundle = noisy_bundle()
        ingest_from_bundle(bundle, db_path=self.db_path)
        finding = check_production_payroll_variance("2026-06", db_path=self.db_path)
        self.assertTrue(finding.get("alert"))
        self.assertEqual(finding.get("gapCode"), GAP_RECON_VARIANCE)
        self.assertIn("production_mom_variance", finding.get("reasons") or [])

    def test_era835_no_phi(self):
        text = synthetic_era835_text()
        self.assertNotIn("NM1*QC", text)
        parsed = parse_era835_text(text)
        self.assertTrue(parsed.get("ok"))
        blob = str(parsed)
        self.assertNotIn("DOE", blob.upper())
        result = ingest_era835_to_unified(
            content=text, filename="synthetic.835", db_path=self.db_path
        )
        self.assertTrue(result.get("ok"))
        self.assertFalse(result.get("softDentWriteBack"))


def json_load(path: Path) -> dict:
    import json

    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    # Materialize fixtures next to generator for discoverability
    write_fixtures()
    unittest.main()
