from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

from app import ai_local_config as config
from app.tests.lane_routing_test_helpers import (
    BACKEND_LANE_URL,
    EVALUATOR_LANE_URL,
    FAST_REVIEW_LANE_URL,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PACKET_DIR = PROJECT_ROOT / "evals" / "insurance_narrative_packets"
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "run_fast_review_bakeoff.py"
GITIGNORE_PATH = PROJECT_ROOT / ".gitignore"


def _load_harness():
    spec = importlib.util.spec_from_file_location("run_fast_review_bakeoff", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def _clear_ai_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "AI_FRONTEND_BASE_URL",
        "AI_BACKEND_BASE_URL",
        "AI_FRONTEND_MODEL",
        "AI_BACKEND_MODEL",
        "AI_FAST_REVIEW_BASE_URL",
        "AI_FAST_REVIEW_MODEL",
        "OLLAMA_BASE_URL",
        "OLLAMA_FRONTEND_BASE_URL",
        "OLLAMA_BACKEND_BASE_URL",
        "OLLAMA_FAST_REVIEW_BASE_URL",
        "OLLAMA_FAST_REVIEW_MODEL",
    ):
        monkeypatch.delenv(name, raising=False)


# --- PHI safety -----------------------------------------------------------------

_PHONE_RE = re.compile(r"\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b")
_SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_STREET_RE = re.compile(r"\b\d{1,6}\s+\w+\s+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr)\b", re.IGNORECASE)
_DOB_RE = re.compile(r"\b(?:DOB|date of birth)\b", re.IGNORECASE)
_MEMBER_ID_RE = re.compile(r"\b(?:member\s*id|subscriber\s*id|policy\s*number)\b", re.IGNORECASE)


def test_sample_packets_exist() -> None:
    packet_files = sorted(PACKET_DIR.glob("*.json"))
    names = {path.name for path in packet_files}
    assert "sample_crown_denial.json" in names
    assert "sample_missing_ar.json" in names


@pytest.mark.parametrize("packet_path", sorted(PACKET_DIR.glob("*.json")), ids=lambda p: p.name)
def test_packets_contain_no_obvious_phi(packet_path: Path) -> None:
    text = packet_path.read_text(encoding="utf-8")
    assert not _PHONE_RE.search(text), f"{packet_path.name} contains a phone-number-like pattern"
    assert not _SSN_RE.search(text), f"{packet_path.name} contains an SSN-like pattern"
    assert not _EMAIL_RE.search(text), f"{packet_path.name} contains an email-like pattern"
    assert not _STREET_RE.search(text), f"{packet_path.name} contains a street-address-like pattern"
    assert not _DOB_RE.search(text), f"{packet_path.name} references a date of birth"
    assert not _MEMBER_ID_RE.search(text), f"{packet_path.name} references a member/subscriber/policy id"


@pytest.mark.parametrize("packet_path", sorted(PACKET_DIR.glob("*.json")), ids=lambda p: p.name)
def test_packets_marked_deidentified(packet_path: Path) -> None:
    harness = _load_harness()
    packet = harness.load_json_file(packet_path)
    assert packet.get("deidentified") is True, f"{packet_path.name} must set deidentified: true"


# --- Lane resolution ------------------------------------------------------------

def test_harness_resolves_chat_second_opinion_to_backend_lane(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_BACKEND_BASE_URL", BACKEND_LANE_URL)
    harness = _load_harness()
    config_payload = config.load_local_model_profile_config()

    target = harness.resolve_bakeoff_target(config_payload, "chat_second_opinion")
    assert target["base_url"] == BACKEND_LANE_URL
    assert ":11435" in target["base_url"]
    assert ":11437" not in target["base_url"]
    assert target["model"] == config.DEFAULT_BACKEND_MODEL


def test_harness_resolves_fast_review_to_fast_lane(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_FAST_REVIEW_BASE_URL", FAST_REVIEW_LANE_URL)
    harness = _load_harness()
    config_payload = config.load_local_model_profile_config()

    target = harness.resolve_bakeoff_target(config_payload, "fast_review")
    assert target["base_url"] == FAST_REVIEW_LANE_URL
    assert ":11437" in target["base_url"]
    assert ":11435" not in target["base_url"]
    assert target["model"] == config.DEFAULT_FAST_REVIEW_MODEL


def test_harness_never_resolves_profiles_to_evaluator_lane(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_BACKEND_BASE_URL", BACKEND_LANE_URL)
    monkeypatch.setenv("AI_FAST_REVIEW_BASE_URL", FAST_REVIEW_LANE_URL)
    harness = _load_harness()
    config_payload = config.load_local_model_profile_config()

    for profile_alias in ("chat_second_opinion", "fast_review"):
        target = harness.resolve_bakeoff_target(config_payload, profile_alias)
        assert ":11436" not in target["base_url"]
        assert target["base_url"] != EVALUATOR_LANE_URL


def test_assert_not_evaluator_lane_raises_for_11436() -> None:
    harness = _load_harness()
    with pytest.raises(harness.BakeoffLaneError):
        harness.assert_not_evaluator_lane("fast_review", EVALUATOR_LANE_URL)


# --- Report / artifact ----------------------------------------------------------

def test_default_report_output_is_gitignored() -> None:
    harness = _load_harness()
    gitignore = GITIGNORE_PATH.read_text(encoding="utf-8")
    assert harness.DEFAULT_OUTPUT in gitignore


def test_unavailable_lane_recorded_not_treated_as_success() -> None:
    harness = _load_harness()
    packets = harness.load_packets(PACKET_DIR)
    assert packets, "expected at least one de-identified packet"

    targets = [
        {"profile": "fast_review", "base_url": FAST_REVIEW_LANE_URL, "model": "qwen3-coder:30b"},
    ]
    lane_availability = {"fast_review": {"available": False, "error": "connection refused"}}

    report = harness.build_report(
        packets=packets,
        targets=targets,
        lane_availability=lane_availability,
        results=[
            {
                "packet_id": packets[0].get("id"),
                "profile": "fast_review",
                "status": "lane_unavailable",
                "error": "connection refused",
            }
        ],
        dry_run=False,
    )

    profile_entry = report["profiles"][0]
    assert profile_entry["lane_available"] is False
    assert profile_entry["lane_error"] == "connection refused"
    statuses = {result["status"] for result in report["results"]}
    assert statuses == {"lane_unavailable"}
    assert "ok" not in statuses


def test_score_review_output_is_deterministic_and_model_free() -> None:
    harness = _load_harness()
    packet = harness.load_json_file(PACKET_DIR / "sample_missing_ar.json")

    good_output = (
        '{"missing_data": ["accounts receivable export", "outstanding claims export"], '
        '"citations": ["116780.00", "107015.00"], "contradictions": [], '
        '"invented_facts": [], "recommended_action": "Request the A/R aging export."}'
    )
    scores = harness.score_review_output(packet, good_output)

    assert scores["json_structured"]["parsed"] is True
    assert scores["json_structured"]["has_all_required_keys"] is True
    assert scores["missing_data_detection"]["all_detected"] is True
    assert scores["citation_compliance"]["matched_count"] >= 2
    assert scores["output_length_chars"] == len(good_output)

    invented_output = '{"missing_data": [], "note": "A/R is 999999.99 and patient owes 12345.67"}'
    invented_scores = harness.score_review_output(packet, invented_output)
    assert invented_scores["json_structured"]["has_all_required_keys"] is False
    assert invented_scores["invented_fact_warnings"]["candidate_count"] >= 2

    non_json_output = "A/R is unavailable; recommend requesting the aging export."
    non_json_scores = harness.score_review_output(packet, non_json_output)
    assert non_json_scores["json_structured"]["parsed"] is False
