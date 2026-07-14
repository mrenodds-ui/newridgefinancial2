"""Moonshot Collections Excel-temp reliability (hal-10576)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from apex_backend import BUILD_ID
from nr2_browser_security import system_status_path
from nr2_hal_gateway import try_local_policy_reply
from softdent_excel_temp import (
    ERROR_TEMP_FILE_LOCKED,
    call_with_excel_temp_retry,
    collections_export_health,
    copy_file_with_retry,
    is_excel_temp_lock_error,
)


class CollectionsExcelTempReliabilityHal10576Tests(unittest.TestCase):
    def test_build_id(self) -> None:
        self.assertEqual(BUILD_ID, "hal-10576")

    def test_health_path_is_system_telemetry(self) -> None:
        self.assertTrue(system_status_path("/api/apex/hal/collections-export/health"))

    def test_lock_error_detection(self) -> None:
        self.assertTrue(is_excel_temp_lock_error(PermissionError(13, "Permission denied")))
        err = OSError(13, "Permission denied")
        err.winerror = 32  # type: ignore[attr-defined]
        self.assertTrue(is_excel_temp_lock_error(err))
        self.assertFalse(is_excel_temp_lock_error(ValueError("nope")))

    def test_retry_succeeds_after_lock(self) -> None:
        calls = {"n": 0}

        def flaky() -> str:
            calls["n"] += 1
            if calls["n"] < 3:
                raise PermissionError(13, "Permission denied")
            return "ok"

        with mock.patch("softdent_excel_temp.time.sleep", return_value=None):
            out = call_with_excel_temp_retry(flaky, delays_sec=(0.0, 0.0, 0.0))
        self.assertEqual(out, "ok")
        self.assertEqual(calls["n"], 3)

    def test_retry_exhausted_raises_temp_lock(self) -> None:
        def always_locked() -> None:
            raise PermissionError(13, "Permission denied")

        with mock.patch("softdent_excel_temp.time.sleep", return_value=None):
            with self.assertRaises(PermissionError):
                call_with_excel_temp_retry(always_locked, delays_sec=(0.0, 0.0))

    def test_copy_file_with_retry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "a.xls"
            dest = root / "b.xls"
            src.write_bytes(b"fake-xls")
            with mock.patch("softdent_excel_temp.time.sleep", return_value=None):
                out = copy_file_with_retry(src, dest, delays_sec=(0.0,))
            self.assertTrue(out.is_file())
            self.assertEqual(out.read_bytes(), b"fake-xls")

    def test_health_no_exports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            health = collections_export_health(dest_root=Path(tmp), temp_dir=Path(tmp))
        self.assertTrue(health.get("ok"))
        self.assertFalse(health.get("collectionsExportReady"))
        self.assertEqual(health.get("errorCode"), "no_exports")
        self.assertFalse(health.get("writeBack"))
        self.assertEqual(health.get("honesty"), "empty_not_zero")
        self.assertIn("ERA-835", str(health.get("hint") or ""))

    def test_health_ready_when_readable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "collections_sample.xls").write_bytes(b"xls")
            health = collections_export_health(dest_root=root, temp_dir=root)
        self.assertTrue(health.get("collectionsExportReady"))
        self.assertIsNone(health.get("errorCode"))

    def test_health_reports_locked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "COL2607.XLS"
            target.write_bytes(b"xls")
            with mock.patch(
                "softdent_excel_temp.open_path_probe",
                side_effect=PermissionError(13, "Permission denied"),
            ):
                with mock.patch("softdent_excel_temp.time.sleep", return_value=None):
                    health = collections_export_health(dest_root=root, temp_dir=root)
        self.assertFalse(health.get("collectionsExportReady"))
        self.assertEqual(health.get("errorCode"), ERROR_TEMP_FILE_LOCKED)

    def test_hal_policy(self) -> None:
        with mock.patch(
            "softdent_excel_temp.collections_export_health",
            return_value={
                "collectionsExportReady": False,
                "errorCode": ERROR_TEMP_FILE_LOCKED,
                "hint": "locked",
            },
        ):
            reply = try_local_policy_reply("excel temp locked collections export health")
        self.assertIsNotNone(reply)
        assert reply is not None
        self.assertEqual(reply.get("intent"), "policy:collections-excel-temp")
        self.assertIn("temp_file_locked", str(reply.get("text") or ""))


if __name__ == "__main__":
    unittest.main()
