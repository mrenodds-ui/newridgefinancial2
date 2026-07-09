"""Clearinghouse 271 adapter and live client tests."""

from __future__ import annotations

import json
import os
import unittest
from unittest.mock import patch

from clearinghouse_271_mapper import map_dentalxchange_eligibility_response, map_optum_eligibility_response
from clearinghouse_eligibility_adapter import clearinghouse_status, fetch_eligibility_271, normalize_eligibility_request
from clearinghouse_live_clients import fetch_change_healthcare_271, fetch_dentalxchange_271
from clearinghouse_http import redact_member_id

OPTUM_SAMPLE = {
    "tradingPartnerServiceId": "DELTA",
    "payer": {"name": "Delta Dental"},
    "planInformation": {"groupDescription": "Delta PPO Premier"},
    "planStatus": {"status": "Active Coverage"},
    "benefitsInformation": [
        {"name": "Deductible", "benefitAmount": "50", "coverageLevel": "Individual"},
        {"name": "Annual Maximum Remaining", "benefitAmount": "1200"},
        {"name": "Basic Coinsurance", "benefitAmount": "80"},
        {"name": "Major Coinsurance", "benefitAmount": "50"},
    ],
}

DXC_SAMPLE = {
    "payerName": "MetLife Dental",
    "payerId": "65978",
    "planName": "MetLife PDP Plus",
    "deductibleRemaining": 25,
    "annualMaxRemaining": 900,
    "benefits": [
        {"name": "Preventive", "amount": 100},
        {"name": "Basic restorative", "amount": 80},
    ],
}


class MapperTests(unittest.TestCase):
    def test_redact_member_id(self) -> None:
        self.assertEqual(redact_member_id("ABC123456789"), "***6789")
        self.assertEqual(redact_member_id("***4821"), "***4821")

    def test_map_optum_response(self) -> None:
        entry = map_optum_eligibility_response(
            OPTUM_SAMPLE,
            {"payerName": "Delta Dental", "memberId": "ABC123456789", "subscriberLastName": "Doe"},
        )
        self.assertEqual(entry["payerName"], "Delta Dental")
        self.assertEqual(entry["memberIdRedacted"], "***6789")
        self.assertEqual(entry["deductibleRemaining"], 50)
        self.assertEqual(entry["annualMaxRemaining"], 1200)

    def test_map_dxc_response(self) -> None:
        entry = map_dentalxchange_eligibility_response(
            DXC_SAMPLE,
            {"payerName": "MetLife Dental", "memberId": "MEM99998888"},
        )
        self.assertEqual(entry["annualMaxRemaining"], 900)
        self.assertEqual(entry["memberIdRedacted"], "***8888")


class ClearinghouseAdapterTests(unittest.TestCase):
    def test_normalize_requires_payer(self) -> None:
        with self.assertRaises(ValueError):
            normalize_eligibility_request({})

    def test_not_configured_without_env(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("CLEARINGHOUSE_MOCK", None)
            os.environ.pop("DENTALXCHANGE_API_KEY", None)
            result = fetch_eligibility_271({"payerName": "Delta Dental"})
        self.assertFalse(result.get("ok"))
        self.assertEqual(result.get("error"), "clearinghouse_not_configured")

    def test_mock_271_caches_entry(self) -> None:
        with patch.dict(os.environ, {"CLEARINGHOUSE_MOCK": "1"}, clear=False):
            result = fetch_eligibility_271(
                {
                    "payerName": "Mock Payer 271 Test",
                    "memberIdRedacted": "***9999",
                }
            )
        self.assertTrue(result.get("ok"))
        self.assertEqual(result.get("vendor"), "mock")
        self.assertTrue(result.get("entry"))

    def test_clearinghouse_status_shape(self) -> None:
        status = clearinghouse_status()
        self.assertIn("vendors", status)
        self.assertIn("requiredLiveFields", status)


class LiveClientTests(unittest.TestCase):
    def test_optum_live_success(self) -> None:
        req = {
            "payerName": "Delta Dental",
            "payerId": "DELTA",
            "memberId": "1234567890",
            "providerNpi": "1234567890",
            "subscriberLastName": "Doe",
        }

        def fake_http(*, method, url, headers=None, body=None, timeout=45.0):
            if url.endswith("/token") or "/apip/auth/v2/token" in url:
                return 200, {"access_token": "tok", "expires_in": 3600}, None
            return 200, OPTUM_SAMPLE, None

        with patch.dict(
            os.environ,
            {
                "CHANGE_HEALTHCARE_CLIENT_ID": "id",
                "CHANGE_HEALTHCARE_CLIENT_SECRET": "secret",
                "CLEARINGHOUSE_MOCK": "0",
            },
            clear=False,
        ):
            with patch("clearinghouse_live_clients.http_json", side_effect=fake_http):
                result = fetch_change_healthcare_271(req)
        self.assertTrue(result.get("ok"))
        self.assertEqual(result.get("vendor"), "change_healthcare")
        self.assertEqual(result["entry"]["memberIdRedacted"], "***7890")

    def test_dxc_live_success(self) -> None:
        req = {
            "payerName": "MetLife Dental",
            "payerId": "65978",
            "memberId": "MEM1234",
            "providerNpi": "1234567890",
        }

        with patch.dict(
            os.environ,
            {"DENTALXCHANGE_API_KEY": "key", "DENTALXCHANGE_API_SECRET": "sec", "CLEARINGHOUSE_MOCK": "0"},
            clear=False,
        ):
            with patch("clearinghouse_live_clients.http_json", return_value=(200, DXC_SAMPLE, None)):
                result = fetch_dentalxchange_271(req)
        self.assertTrue(result.get("ok"))
        self.assertEqual(result.get("vendor"), "dentalxchange")

    def test_live_missing_member_id(self) -> None:
        with patch.dict(os.environ, {"CHANGE_HEALTHCARE_CLIENT_ID": "id", "CHANGE_HEALTHCARE_CLIENT_SECRET": "sec"}, clear=False):
            result = fetch_change_healthcare_271({"payerName": "Delta", "payerId": "1", "providerNpi": "1234567890"})
        self.assertFalse(result.get("ok"))
        self.assertEqual(result.get("error"), "memberId_required_for_live_271")


if __name__ == "__main__":
    unittest.main()
