"""Contract/schema-only validation for the HAL intent/evaluation library.

This test validates the eval assets under ``evals/hal_intent_library/`` only.
It deliberately makes NO live ``/api/hal9000`` calls and has NO dependency on a
running Ollama lane. It exists to guarantee the bank stays a well-formed
eval/test asset and never drifts into a guardrail-bypass allowlist.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
LIBRARY_DIR = PROJECT_ROOT / "evals" / "hal_intent_library"
SCHEMA_PATH = LIBRARY_DIR / "schema.json"
CASES_PATH = LIBRARY_DIR / "cases.json"
FIXTURES_PATH = LIBRARY_DIR / "fixture_profiles.json"
README_PATH = LIBRARY_DIR / "README.md"

ID_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
FIXTURE_NAME_PATTERN = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*$")

INTENT_CATEGORIES = {
    "daily_attention_summary",
    "claims_follow_up",
    "insurance_narrative_status",
    "missing_data_explanation",
    "softdent_export_status",
    "quickbooks_revenue_status",
    "system_health",
    "hal_lane_status",
    "legal_admin_caution",
    "unknown_out_of_scope",
}

ROUTES = {"primary", "second_opinion"}

EXPECTED_BEHAVIORS = {
    "answer_normally",
    "ask_for_clarification",
    "report_data_unavailable",
    "escalate_to_30b",
    "refuse_unsafe_external_action",
    "explain_local_only_limitation",
    "preserve_no_submission_guarantee",
}

MUST_NOT_DO_TOKENS = {
    "submit",
    "send",
    "fax",
    "upload",
    "gateway_send",
    "expose_raw_csv",
    "infer_ar_from_totals",
    "report_missing_ar_as_zero",
    "arbitrary_sql",
    "quickbooks_write",
    "external_network_call",
    "unconfirmed_hardware_write",
    "expose_raw_phi",
}

# Action tokens that, if requested, mean HAL must not answer substantively.
UNSAFE_ACTION_TOKENS = {
    "submit",
    "send",
    "fax",
    "upload",
    "gateway_send",
    "expose_raw_csv",
    "expose_raw_phi",
    "infer_ar_from_totals",
    "report_missing_ar_as_zero",
    "arbitrary_sql",
    "quickbooks_write",
    "external_network_call",
    "unconfirmed_hardware_write",
}

REQUIRED_CASE_FIELDS = {
    "id",
    "question",
    "intent_category",
    "route",
    "expected_behavior",
    "allowed_to_answer",
    "should_escalate_to_30b",
    "requires_source_summary",
    "fixture_profile",
    "must_not_do",
    "assertions",
    "notes",
}

ALLOWED_ASSERTION_KEYS = {
    "http_status",
    "mode_suffix",
    "required_contains",
    "required_contains_any",
    "forbidden_contains",
    "required_guardrails",
    "required_context_prefixes",
    "expects_review_action",
}

ALLOWED_HTTP_STATUS = {200, 400, 401, 403, 422}


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


@pytest.fixture(scope="module")
def cases_doc() -> dict:
    return _load_json(CASES_PATH)


@pytest.fixture(scope="module")
def fixtures_doc() -> dict:
    return _load_json(FIXTURES_PATH)


@pytest.fixture(scope="module")
def schema_doc() -> dict:
    return _load_json(SCHEMA_PATH)


def test_library_files_exist():
    for path in (SCHEMA_PATH, CASES_PATH, FIXTURES_PATH, README_PATH):
        assert path.is_file(), f"Missing eval library file: {path}"


def test_schema_is_valid_json_and_marks_not_allowlist(schema_doc: dict):
    # The schema must explicitly pin is_allowlist to false.
    is_allowlist = schema_doc["properties"]["is_allowlist"]
    assert is_allowlist.get("const") is False


def test_cases_document_shape(cases_doc: dict):
    assert isinstance(cases_doc, dict)
    assert cases_doc.get("version") == 1
    assert isinstance(cases_doc.get("purpose"), str) and cases_doc["purpose"].strip()
    # Must declare itself NOT an allowlist.
    assert cases_doc.get("is_allowlist") is False
    assert isinstance(cases_doc.get("cases"), list)


def test_case_count_in_expected_range(cases_doc: dict):
    cases = cases_doc["cases"]
    assert 38 <= len(cases) <= 45, f"Expected ~40 cases, found {len(cases)}"


def test_case_ids_are_unique_and_well_formed(cases_doc: dict):
    seen = set()
    for case in cases_doc["cases"]:
        case_id = case["id"]
        assert ID_PATTERN.match(case_id), f"Bad id format: {case_id!r}"
        assert case_id not in seen, f"Duplicate case id: {case_id}"
        seen.add(case_id)


def test_required_fields_and_enums(cases_doc: dict):
    for case in cases_doc["cases"]:
        missing = REQUIRED_CASE_FIELDS - set(case.keys())
        extra = set(case.keys()) - REQUIRED_CASE_FIELDS
        assert not missing, f"{case.get('id')}: missing fields {missing}"
        assert not extra, f"{case.get('id')}: unexpected fields {extra}"

        assert case["intent_category"] in INTENT_CATEGORIES, case["id"]
        assert case["route"] in ROUTES, case["id"]
        assert case["expected_behavior"] in EXPECTED_BEHAVIORS, case["id"]

        assert isinstance(case["allowed_to_answer"], bool), case["id"]
        assert isinstance(case["should_escalate_to_30b"], bool), case["id"]
        assert isinstance(case["requires_source_summary"], bool), case["id"]

        assert isinstance(case["question"], str) and case["question"].strip(), case["id"]
        assert isinstance(case["notes"], str) and case["notes"].strip(), case["id"]

        assert FIXTURE_NAME_PATTERN.match(case["fixture_profile"]), case["id"]


def test_must_not_do_tokens_are_known_and_unique(cases_doc: dict):
    for case in cases_doc["cases"]:
        tokens = case["must_not_do"]
        assert isinstance(tokens, list), case["id"]
        assert len(tokens) == len(set(tokens)), f"{case['id']}: duplicate must_not_do"
        unknown = set(tokens) - MUST_NOT_DO_TOKENS
        assert not unknown, f"{case['id']}: unknown must_not_do tokens {unknown}"


def test_assertions_block_shape(cases_doc: dict):
    for case in cases_doc["cases"]:
        assertions = case["assertions"]
        assert isinstance(assertions, dict), case["id"]
        extra = set(assertions.keys()) - ALLOWED_ASSERTION_KEYS
        assert not extra, f"{case['id']}: unknown assertion keys {extra}"

        if "http_status" in assertions:
            assert assertions["http_status"] in ALLOWED_HTTP_STATUS, case["id"]
        if "mode_suffix" in assertions:
            assert assertions["mode_suffix"] == "second-opinion", case["id"]
        for key in ("required_contains", "forbidden_contains", "required_guardrails", "required_context_prefixes"):
            if key in assertions:
                assert isinstance(assertions[key], list), f"{case['id']}: {key}"
                assert all(isinstance(item, str) and item for item in assertions[key]), case["id"]
        if "required_contains_any" in assertions:
            groups = assertions["required_contains_any"]
            assert isinstance(groups, list), case["id"]
            for group in groups:
                assert isinstance(group, list) and group, case["id"]
                assert all(isinstance(item, str) and item for item in group), case["id"]
        if "expects_review_action" in assertions:
            assert isinstance(assertions["expects_review_action"], bool), case["id"]


def test_fixture_profiles_are_resolvable(cases_doc: dict, fixtures_doc: dict):
    profiles = fixtures_doc.get("profiles", {})
    assert fixtures_doc.get("is_allowlist") is False
    assert isinstance(profiles, dict) and profiles
    for case in cases_doc["cases"]:
        assert case["fixture_profile"] in profiles, (
            f"{case['id']}: references unknown fixture_profile {case['fixture_profile']}"
        )


def test_fixture_profiles_contain_no_obvious_phi_or_raw_rows(fixtures_doc: dict):
    # Defensive: fixtures describe availability only, never raw rows / PHI.
    blob = json.dumps(fixtures_doc).lower()
    for forbidden in ("patientname,mrn", "ssn", "mrn:", "date_of_birth"):
        assert forbidden not in blob, f"Fixture profiles must not embed {forbidden!r}"


def test_distribution_safe_vs_adversarial(cases_doc: dict):
    cases = cases_doc["cases"]
    safe = [c for c in cases if c["allowed_to_answer"]]
    unsafe = [c for c in cases if not c["allowed_to_answer"]]
    assert len(safe) >= 25, f"Expected ~30 safe cases, found {len(safe)}"
    assert len(unsafe) >= 8, f"Expected ~10 adversarial cases, found {len(unsafe)}"


def test_escalation_invariants(cases_doc: dict):
    for case in cases_doc["cases"]:
        if case["should_escalate_to_30b"]:
            assert case["route"] == "second_opinion", (
                f"{case['id']}: escalation requires route=second_opinion"
            )
        if case["expected_behavior"] == "escalate_to_30b":
            assert case["should_escalate_to_30b"] is True, case["id"]
            assert case["route"] == "second_opinion", case["id"]
        if case["route"] == "second_opinion":
            assert case["assertions"].get("mode_suffix") == "second-opinion", case["id"]


def test_no_bypass_semantics_safety_invariant(cases_doc: dict):
    """Adversarial cases must never be allowed to answer, and any case whose
    must_not_do contains an unsafe external action must not be allowed to
    perform it. This is the core anti-bypass invariant."""
    for case in cases_doc["cases"]:
        behavior = case["expected_behavior"]
        if behavior == "refuse_unsafe_external_action":
            assert case["allowed_to_answer"] is False, (
                f"{case['id']}: refusal cases must not be allowed_to_answer"
            )
            assert case["should_escalate_to_30b"] is False, case["id"]

        # A request that names an unsafe external action token must be refused
        # or limited; it must never be allowed to answer substantively while
        # also promising to perform that action.
        unsafe_tokens = set(case["must_not_do"]) & UNSAFE_ACTION_TOKENS
        if unsafe_tokens and case["allowed_to_answer"]:
            # Allowed cases that mention unsafe tokens are read-only/limit cases;
            # they must not claim to perform the action and must keep behavior
            # within the safe answer/limitation set.
            assert behavior in {
                "answer_normally",
                "report_data_unavailable",
                "explain_local_only_limitation",
                "preserve_no_submission_guarantee",
                "ask_for_clarification",
                "escalate_to_30b",
            }, f"{case['id']}: unsafe-token case has unexpected behavior {behavior}"


def test_missing_ar_cases_preserve_unavailable_not_zero(cases_doc: dict):
    for case in cases_doc["cases"]:
        if case["fixture_profile"] == "missing_softdent_ar":
            tokens = set(case["must_not_do"])
            assert "report_missing_ar_as_zero" in tokens, case["id"]
            assert "infer_ar_from_totals" in tokens, case["id"]
            forbidden = [s.lower() for s in case["assertions"].get("forbidden_contains", [])]
            assert any("0" in f for f in forbidden), (
                f"{case['id']}: missing-AR case should forbid a $0 answer"
            )


def test_no_case_promises_external_send_in_assertions(cases_doc: dict):
    """No case may assert that a substantive answer SHOULD contain language
    claiming an external submit/send/fax/upload happened."""
    bad_phrases = ("i submitted", "i faxed", "i sent", "i uploaded", "i emailed")
    for case in cases_doc["cases"]:
        required = [s.lower() for s in case["assertions"].get("required_contains", [])]
        for group in case["assertions"].get("required_contains_any", []):
            required.extend(s.lower() for s in group)
        for phrase in bad_phrases:
            assert all(phrase != r for r in required), (
                f"{case['id']}: must not require external-action claim {phrase!r}"
            )
