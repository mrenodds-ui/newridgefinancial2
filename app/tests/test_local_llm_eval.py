from app.evaluation.engine import compute_context_precision, evaluate_assertions, split_text_into_chunks


def test_assertion_helpers_cover_json_and_string_rules():
    output = '{"plan": ["one", "two"], "risks": ["three"]}'
    failures = evaluate_assertions(
        output,
        [
            {"type": "json_parse"},
            {"type": "json_keys", "keys": ["plan", "risks"]},
            {"type": "not_contains", "value": "```"},
        ],
    )
    assert failures == []


def test_context_precision_uses_expected_hits_over_top_k():
    precision = compute_context_precision(
        ["docs/a.md", "docs/b.md", "docs/c.md", "docs/d.md"],
        ["docs/b.md", "docs/d.md"],
    )
    assert precision == 0.5


def test_chunking_splits_large_text_with_overlap():
    text = "A" * 50 + "B" * 50 + "C" * 50
    chunks = split_text_into_chunks(text, chunk_size=80, overlap=20)
    assert len(chunks) >= 2
    assert all(chunks)