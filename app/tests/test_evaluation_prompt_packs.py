from pathlib import Path

from app.evaluation.ab_compare import validate_ab_prompt_cases
from app.evaluation.client import load_json_file


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _load_prompt_pack(relative_path: str) -> list[dict[str, object]]:
    return validate_ab_prompt_cases(load_json_file(PROJECT_ROOT / relative_path))


def _load_json(relative_path: str) -> dict[str, object]:
    return load_json_file(PROJECT_ROOT / relative_path)


def test_validate_ab_prompt_cases_rejects_duplicate_ids():
    try:
        validate_ab_prompt_cases(
            [
                {"id": "ops", "prompt": "One"},
                {"id": "ops", "prompt": "Two"},
            ]
        )
    except ValueError as exc:
        assert str(exc) == "Prompt pack contains a duplicate id: ops"
    else:
        raise AssertionError("Expected duplicate-id validation failure.")


def test_validate_ab_prompt_cases_rejects_invalid_required_contains_any_group():
    try:
        validate_ab_prompt_cases(
            [
                {
                    "id": "softdent-risk",
                    "prompt": "What should I look at first?",
                    "content_assertions": {"required_contains_any": [[]]},
                }
            ]
        )
    except ValueError as exc:
        assert str(exc) == "Prompt case 'softdent-risk' has an invalid required_contains_any group at position 1."
    else:
        raise AssertionError("Expected required_contains_any validation failure.")


def test_canonical_ab_prompt_pack_contract_is_present():
    prompts = _load_prompt_pack("evals/hal_humanization_ab_prompts.json")

    prompt_ids = [str(item["id"]) for item in prompts]
    assert prompt_ids == [
        "ops-brief",
        "softdent-risk",
        "quickbooks-guardrail",
        "claims-followup",
        "owner-tone",
    ]

    cases = {str(item["id"]): item for item in prompts}
    assert cases["ops-brief"]["content_assertions"]["required_contains"] == ["Ollama", "SoftDent", "QuickBooks"]
    assert "if you want" in cases["ops-brief"]["content_assertions"]["forbidden_contains"]
    assert "work queue" in cases["ops-brief"]["content_assertions"]["forbidden_contains"]

    assert cases["softdent-risk"]["content_assertions"]["required_contains"] == ["insurance"]
    assert cases["softdent-risk"]["content_assertions"]["required_contains_any"] == [
        ["aging report", "accounts receivable", "A/R", "outstanding balances"]
    ]

    assert cases["quickbooks-guardrail"]["content_assertions"]["required_contains"] == ["QuickBooks"]
    assert cases["quickbooks-guardrail"]["content_assertions"]["required_contains_any"] == [
        ["cannot", "can't"],
        ["review", "validate", "prepare", "manual review", "posting package"],
    ]
    assert "QuickBooks Online" in cases["quickbooks-guardrail"]["content_assertions"]["forbidden_contains"]
    assert "created in QuickBooks" in cases["quickbooks-guardrail"]["content_assertions"]["forbidden_contains"]

    assert cases["claims-followup"]["content_assertions"]["required_contains"] == ["claim"]
    assert cases["owner-tone"]["content_assertions"]["required_contains"] == ["SoftDent", "QuickBooks"]
    assert "let me know" in cases["owner-tone"]["content_assertions"]["forbidden_contains"]


def test_focused_prompt_packs_preserve_target_case_contracts():
    single_prompt = _load_prompt_pack("evals/hal_humanization_single_prompt.json")
    owner_tone = _load_prompt_pack("evals/hal_humanization_owner_tone_prompt.json")
    softdent_risk = _load_prompt_pack("evals/hal_humanization_softdent_risk_prompt.json")
    quickbooks = _load_prompt_pack("evals/hal_humanization_quickbooks_guardrail_prompt.json")

    assert [item["id"] for item in single_prompt] == ["ops-brief"]
    assert [item["id"] for item in owner_tone] == ["owner-tone"]
    assert [item["id"] for item in softdent_risk] == ["softdent-risk"]
    assert [item["id"] for item in quickbooks] == ["quickbooks-guardrail"]

    assert "QuickBooks" in quickbooks[0]["content_assertions"]["required_contains"]
    assert "created in QuickBooks" in quickbooks[0]["content_assertions"]["forbidden_contains"]
    assert quickbooks[0]["content_assertions"]["required_contains_any"] == [
        ["cannot", "can't"],
        ["review", "validate", "prepare", "manual review", "posting package"],
    ]


def test_quickbooks_guardrail_prompt_matches_write_boundary_contract():
    quickbooks = _load_prompt_pack("evals/hal_humanization_quickbooks_guardrail_prompt.json")[0]
    assertions = quickbooks["content_assertions"]

    assert assertions["required_contains"] == ["QuickBooks"]
    assert assertions["required_contains_any"] == [["cannot", "can't"], ["review", "validate", "prepare", "manual review", "posting package"]]
    assert "posted" in assertions["forbidden_contains"]
    assert "completed the adjustment" in assertions["forbidden_contains"]
    assert "created in QuickBooks" in assertions["forbidden_contains"]
    assert "Would you like help" in assertions["forbidden_contains"]
    assert "QuickBooks Desktop" in assertions["forbidden_contains"]
    assert "credentials" in assertions["forbidden_contains"]
    assert "let me know" in assertions["forbidden_contains"]


def test_quickbooks_write_boundary_is_consistent_across_eval_layers():
    golden_dataset = _load_json("evals/golden_dataset.json")
    retrieval_cases = {item["id"]: item for item in golden_dataset["retrieval_assertions"]}
    qb_boundary = retrieval_cases["qb-read-only-boundary"]
    system_prompt = (PROJECT_ROOT / "evals/prompts/mistral_chat_system.txt").read_text(encoding="utf-8")

    assert qb_boundary["required_phrases"] == ["read-only"]
    assert qb_boundary["required_phrase_groups"] == [["separate local posting worker", "direct tool surface"]]
    assert "HAL can post directly" in qb_boundary["forbidden_phrases"]
    assert "For QuickBooks write requests, say you cannot post or apply the adjustment yourself." in system_prompt
    assert "Use the word \"cannot\" and name QuickBooks explicitly in that boundary sentence." in system_prompt
    assert "Offer a local next step such as reviewing the draft, validating the journal lines, or preparing the posting package for human review." in system_prompt
    assert "Do not say the adjustment has already been created, saved, sent, posted, or applied in QuickBooks unless the verified context explicitly says that happened." in system_prompt