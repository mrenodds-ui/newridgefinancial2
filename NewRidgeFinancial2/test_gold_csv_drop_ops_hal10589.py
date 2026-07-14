"""HAL-10589 / OPS-10589 gold CSV drop facilitation & ingest verification."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from apex_backend import BUILD_ID
from softdent_gold_csv_drop_ops import (
    PACKAGE_BUILD_ID,
    checklist_post_ingest,
    checklist_pre_drop,
    format_gold_csv_drop_ops_reply,
    gold_csv_drop_ops_widget,
    gold_csv_drop_playbook,
    run_ops_10589_gold_csv_drop,
    verify_gold_csv_schema,
)
from softdent_treatment_planning import ensure_treatment_planning_schema
from softdent_odbc_extract import ensure_sd_schema
import sqlite3


_FIXTURE = """Insurance Company,Procedure Code,Submitted Fee,Allowed Amount,Paid Amount,Write Off,Patient Portion
DELTA DENTAL OF KS,D1110,140.00,112.00,84.00,28.00,28.00
DELTA DENTAL OF KS,D1110,140.00,112.00,90.00,22.00,22.00
DELTA DENTAL OF KS,D2740,1100.00,900.00,700.00,200.00,200.00
"""


def _empty_db(path: Path) -> None:
    conn = sqlite3.connect(str(path))
    try:
        ensure_sd_schema(conn)
        ensure_treatment_planning_schema(conn)
        conn.commit()
    finally:
        conn.close()


class GoldCsvDropOpsHal10589Tests(unittest.TestCase):
    def test_build_id_coupled(self) -> None:
        self.assertEqual(PACKAGE_BUILD_ID, "hal-10597")
        self.assertEqual(BUILD_ID, "hal-10608")

    def test_schema_verify_and_ingest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / "a.db"
            drop = root / "exports"
            drop.mkdir()
            _empty_db(db)
            pre = checklist_pre_drop(db_path=db, search_dir=drop)
            self.assertFalse(pre.get("readyForIngest"))
            self.assertEqual((pre.get("audit") or {}).get("gapCode"), "GOLD_CSV_MISSING")

            csv_path = drop / "insurance_payments_20260713.csv"
            csv_path.write_text(_FIXTURE, encoding="utf-8")
            schema = verify_gold_csv_schema(csv_path)
            self.assertTrue(schema.get("ok"))
            self.assertGreaterEqual(int(schema.get("dataRows") or 0), 3)

            result = run_ops_10589_gold_csv_drop(
                attempt_gui_export=False, db_path=db, search_dir=drop
            )
            self.assertTrue(result.get("ok"))
            post = result.get("post") or {}
            self.assertEqual((post.get("audit") or {}).get("gapCode"), "GOLD_OK")
            self.assertGreaterEqual(int((post.get("audit") or {}).get("paymentLines") or 0), 3)

    def test_bad_schema_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "insurance_payments_bad.csv"
            p.write_text("foo,bar\n1,2\n", encoding="utf-8")
            schema = verify_gold_csv_schema(p)
            self.assertFalse(schema.get("ok"))
            self.assertIn("insurance_company", schema.get("missingRequired") or [])

    def test_playbook_reply_widget(self) -> None:
        play = gold_csv_drop_playbook()
        self.assertIn("Insurance Income", play["softDentMenu"])
        self.assertIn("no menu item", play["softDentMenuDiscovered"].lower())
        self.assertEqual(play.get("outputMode"), "print_preview_only")
        self.assertIn("Print Preview", play.get("format") or "")
        self.assertIn("PageDown", play.get("visualRead") or "")
        self.assertFalse(play.get("format", "").lower().startswith("excel"))
        text = format_gold_csv_drop_ops_reply(
            {"post": checklist_post_ingest(db_path=Path("nope.db"))}
        )
        self.assertIn("HAL-10597", text)
        w = gold_csv_drop_ops_widget()
        self.assertEqual(w.get("packageBuildId"), "hal-10597")
        self.assertFalse(w.get("triggersGoldIngest"))


if __name__ == "__main__":
    unittest.main()
