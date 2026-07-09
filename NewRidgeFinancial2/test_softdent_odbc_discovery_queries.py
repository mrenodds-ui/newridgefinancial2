"""Unit tests for SoftDent ODBC discovery query builder + extract fallback."""

from __future__ import annotations

import importlib.util
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from softdent_odbc_extract import (
    ensure_sd_schema,
    export_sd_claims_to_inbox_csv,
    load_discovery_suggested_env,
    resolve_odbc_query_map,
)

_DISCOVERY_PATH = Path(__file__).resolve().parent / "scripts" / "discover_softdent_odbc_schema.py"


def _load_discovery_module():
    spec = importlib.util.spec_from_file_location("discover_softdent_odbc_schema", _DISCOVERY_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


class DiscoveryQueryBuilderTests(unittest.TestCase):
    def test_build_claims_query_from_columns(self) -> None:
        disc = _load_discovery_module()
        build_query_from_columns = disc.build_query_from_columns
        suggest_queries_from_discovery = disc.suggest_queries_from_discovery

        cols = ["ClaimID", "PatientName", "InsCo", "ServiceDate", "ClaimAmount", "Status"]
        sql = build_query_from_columns("sd_claims", "Claims", cols)
        self.assertIsNotNone(sql)
        assert sql is not None
        self.assertIn("[ClaimID] AS claim_id", sql)
        self.assertIn("[InsCo] AS payer", sql)
        self.assertIn("FROM [Claims]", sql)
        self.assertIn("DATEADD(month, -24", sql)

        suggested, meta = suggest_queries_from_discovery(
            {"sd_claims": ["Claims", "ClaimHistory"]},
            {"Claims": cols},
        )
        self.assertEqual(meta["sd_claims"]["source"], "columns")
        self.assertIn("SOFTDENT_ODBC_CLAIMS_QUERY", suggested)
        self.assertIn("InsCo", suggested["SOFTDENT_ODBC_CLAIMS_QUERY"])

    def test_build_claims_query_requires_claim_id_and_payer(self) -> None:
        disc = _load_discovery_module()
        self.assertIsNone(
            disc.build_query_from_columns("sd_claims", "Claims", ["ClaimID", "ServiceDate"])
        )


class DiscoveryExtractFallbackTests(unittest.TestCase):
    def test_resolve_odbc_query_map_fills_from_discovery(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            discovery = Path(tmp) / "softdent_schema_discovery.json"
            discovery.write_text(
                json.dumps(
                    {
                        "ok": True,
                        "suggestedEnv": {
                            "SOFTDENT_ODBC_CLAIMS_QUERY": (
                                "SELECT [ClaimID] AS claim_id, [Payer] AS payer FROM [Claims]"
                            )
                        },
                    }
                ),
                encoding="utf-8",
            )
            cleared = {
                key: ""
                for key in list(os.environ)
                if key.startswith("SOFTDENT_ODBC_") and key.endswith("_QUERY")
            }
            cleared["NR2_SOFTDENT_USE_DISCOVERY_QUERIES"] = "1"
            with patch.dict(os.environ, cleared, clear=False), patch(
                "softdent_odbc_extract.discovery_output_path", return_value=discovery
            ):
                query_map = resolve_odbc_query_map()
                self.assertTrue(query_map.get("sd_claims"))
                self.assertIn("claim_id", query_map["sd_claims"])
                loaded = load_discovery_suggested_env()
                self.assertIn("SOFTDENT_ODBC_CLAIMS_QUERY", loaded)

    def test_export_sd_claims_named_payers_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)
            db = dest / "sd.sqlite"
            conn = sqlite3.connect(db)
            ensure_sd_schema(conn)
            conn.execute(
                """
                INSERT INTO sd_claims
                (claim_id, patient_name, payer, service_date, claim_amount, claim_status, practice_id, extracted_at)
                VALUES
                ('1', 'A', 'Insurance', '2026-06-01', 10, 'Ready', '', 't'),
                ('2', 'B', 'Delta Dental', '2026-06-02', 20, 'Denied', '', 't')
                """
            )
            conn.commit()
            result = export_sd_claims_to_inbox_csv(conn, destination=dest)
            conn.close()
            self.assertTrue(result["ok"])
            self.assertEqual(result["written"], 1)
            text = (dest / "softdent_claims_export.csv").read_text(encoding="utf-8")
            self.assertIn("Delta Dental", text)
            data_lines = [ln for ln in text.splitlines()[1:] if ln.strip()]
            self.assertEqual(len(data_lines), 1)
            self.assertNotIn(",Insurance,", f",{data_lines[0]},")


if __name__ == "__main__":
    unittest.main()
