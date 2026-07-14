"""Tests for SoftDent PRODBYADA.xls → production_by_ada ingest (non-Gold)."""

from __future__ import annotations

import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from softdent_prodbyada_xls_ingest import (
    ingest_prodbyada_xls,
    parse_prodbyada_xls,
)

_LIVE = Path(r"D:\PRODBYADA.xls")
_EXPORT = Path(r"C:\SoftDentFinancialExports\production_by_ada_20250713_20260713.xls")


def _fixture_xls() -> Path | None:
    for p in (_LIVE, _EXPORT):
        if p.is_file():
            return p
    return None


@unittest.skipUnless(_fixture_xls() is not None, "PRODBYADA.xls fixture not on disk")
class ProdByAdaXlsIngestTests(unittest.TestCase):
    def test_parse_and_ingest_does_not_touch_payment_lines(self) -> None:
        src = _fixture_xls()
        assert src is not None
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            xls = root / "PRODBYADA.xls"
            shutil.copy2(src, xls)
            db = root / "analytics.db"
            sqlite3.connect(str(db)).close()

            parsed = parse_prodbyada_xls(xls)
            self.assertEqual(parsed.get("periodStart"), "2025-07-13")
            self.assertEqual(parsed.get("periodEnd"), "2026-07-13")
            self.assertGreaterEqual(int(parsed.get("rowCount") or 0), 10)
            self.assertTrue(parsed.get("groupRollups"))

            result = ingest_prodbyada_xls(xls, db_path=db, copy_to_exports=False)
            self.assertTrue(result.get("ok"))
            self.assertFalse(result.get("inventedGold"))
            self.assertFalse(result.get("writesPaymentLines"))
            self.assertGreaterEqual(int(result.get("rowsIngested") or 0), 10)

            con = sqlite3.connect(str(db))
            try:
                n = con.execute(
                    "SELECT COUNT(*) FROM production_by_ada "
                    "WHERE source_file LIKE 'softdent_prodbyada_xls:%'"
                ).fetchone()[0]
                self.assertGreaterEqual(n, 10)
                # Ensure gold table not invented by this ingest
                ensure = con.execute(
                    "SELECT name FROM sqlite_master WHERE name='sd_insurance_payment_lines'"
                ).fetchone()
                self.assertIsNone(ensure)
            finally:
                con.close()


if __name__ == "__main__":
    unittest.main()
