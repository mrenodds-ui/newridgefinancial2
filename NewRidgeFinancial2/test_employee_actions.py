"""Tests for HAL employee tier actions."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path


class _FakeStore:
    def __init__(self) -> None:
        self._data: dict[str, str] = {}
        self.db_path = Path(tempfile.gettempdir()) / "nr2-employee-test.db"

    def get(self, key: str):
        return self._data.get(key)

    def set(self, key: str, value: str) -> None:
        self._data[key] = value


class EmployeeActionsTests(unittest.TestCase):
    def test_standing_policies_level_5(self) -> None:
        from employee_actions import get_standing_policies, standing_allows

        store = _FakeStore()
        pol = get_standing_policies(store, target_level=5)
        self.assertTrue(pol["ok"])
        self.assertEqual(pol["level"], 5)
        self.assertTrue(standing_allows("qbo-post", target_level=5, policies=pol["policies"]))
        self.assertTrue(standing_allows("softdent-writeback", target_level=5, policies=pol["policies"]))

    def test_work_log_append(self) -> None:
        from employee_actions import append_employee_work_log, list_employee_work_log

        store = _FakeStore()
        append_employee_work_log(store, action="test", summary="Unit test entry", level=5)
        log = list_employee_work_log(store, limit=5)
        self.assertTrue(log["ok"])
        self.assertEqual(log["count"], 1)
        self.assertEqual(log["items"][0]["action"], "test")

    def test_employee_status(self) -> None:
        from employee_actions import get_employee_status

        store = _FakeStore()
        st = get_employee_status(store, target_level=5)
        self.assertTrue(st["ok"])
        self.assertEqual(st["targetLevel"], 5)
        self.assertEqual(st["name"], "HAL")


if __name__ == "__main__":
    unittest.main()
