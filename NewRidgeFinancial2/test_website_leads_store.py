"""Tests for website appointment lead store + Gravity Forms normalization."""

from __future__ import annotations

import os
import sqlite3
import unittest

from website_leads_store import (
    format_lead_sidenote,
    init_website_leads_schema,
    insert_website_lead,
    list_website_leads,
    mark_website_lead_handled,
    normalize_gravity_forms_payload,
    webhook_secret_valid,
)


class WebsiteLeadsStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        init_website_leads_schema(self.conn)

    def tearDown(self) -> None:
        self.conn.close()
        os.environ.pop("NR2_WEBSITE_WEBHOOK_SECRET", None)

    def test_normalize_labeled_fields(self) -> None:
        n = normalize_gravity_forms_payload(
            {
                "entry_id": "42",
                "form_id": "1",
                "Your Name": "Jane Doe",
                "Your E-mail Address": "jane@example.com",
                "Your Phone Number": "316-555-0100",
                "I am interested in": ["Scheduling Appointment", "Teeth Whitening"],
                "Best Time for Appointment": "Morning",
                "Preferred Day of Week": "T, Th",
                "How did you hear about us?": "Friend/Family",
                "Comments/Questions": "New patient",
            }
        )
        self.assertEqual(n["name"], "Jane Doe")
        self.assertEqual(n["email"], "jane@example.com")
        self.assertIn("Teeth Whitening", n["interests"])
        self.assertEqual(n["external_id"], "42")

    def test_insert_idempotent_and_sidenote_text(self) -> None:
        n = normalize_gravity_forms_payload(
            {
                "entry_id": "99",
                "Your Name": "Sam Patient",
                "Your E-mail Address": "sam@example.com",
                "Your Phone Number": "3165550199",
            }
        )
        first = insert_website_lead(self.conn, normalized=n)
        self.conn.commit()
        self.assertFalse(first["duplicate"])
        second = insert_website_lead(self.conn, normalized=n)
        self.assertTrue(second["duplicate"])
        self.assertEqual(first["id"], second["id"])
        note = format_lead_sidenote(first)
        self.assertIn("WEB APPT REQUEST", note)
        self.assertIn("Sam Patient", note)

    def test_list_and_handle(self) -> None:
        n = normalize_gravity_forms_payload({"Your Name": "A", "Your E-mail Address": "a@b.co"})
        lead = insert_website_lead(self.conn, normalized=n)
        self.conn.commit()
        open_items = list_website_leads(self.conn, status="open")
        self.assertEqual(len(open_items), 1)
        result = mark_website_lead_handled(self.conn, lead["id"])
        self.conn.commit()
        self.assertTrue(result["ok"])
        self.assertEqual(list_website_leads(self.conn, status="open"), [])

    def test_webhook_secret(self) -> None:
        os.environ.pop("NR2_WEBSITE_WEBHOOK_SECRET", None)
        self.assertTrue(webhook_secret_valid(None))
        os.environ["NR2_WEBSITE_WEBHOOK_SECRET"] = "s3cret"
        self.assertFalse(webhook_secret_valid(""))
        self.assertFalse(webhook_secret_valid("wrong"))
        self.assertTrue(webhook_secret_valid("s3cret"))


if __name__ == "__main__":
    unittest.main()
