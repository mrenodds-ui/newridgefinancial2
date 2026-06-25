# Insurance narrative review packets (de-identified)

These JSON packets are **synthetic, de-identified** review inputs for the experimental
`fast_review` lane bakeoff (`scripts/run_fast_review_bakeoff.py`). They compare structured
review quality and latency between:

- `chat_second_opinion` → `:11435` / `qwen3:30b` (current backend default; **not** replaced)
- `fast_review` → `:11437` / `Qwen3-Coder-30B-A3B-Instruct` (experimental, opt-in)

## No PHI

These packets contain **no protected health information**. By design they use only:

- Generic labels (`Patient A`, `Provider 1`, `CHART-A`, `CLAIM-1001`, `Payer One`)
- Synthetic dates, procedures, and dollar amounts
- No real names, dates of birth, phone numbers, email addresses, street addresses,
  Social Security numbers, or insurance member IDs

`app/tests/test_fast_review_bakeoff.py` enforces this with PHI pattern scans on every packet.
Do not add real patient data to this directory.

## Packet schema

| Field | Purpose |
| --- | --- |
| `id`, `title` | Identifiers for the report |
| `deidentified` | Must be `true` |
| `source_text` | The de-identified material the model reviews |
| `review_instructions` | Prompt asking for a single JSON review object |
| `required_json_keys` | Keys the JSON output must contain to count as parsed/structured |
| `expected_missing_data` | Fields the reviewer should flag as unavailable (missing-data detection score) |
| `source_citations` | Facts present in the source (citation/source compliance score) |
| `allowed_facts` | Facts/labels permitted to appear in output |
| `allowed_numbers` | Numeric tokens present in the source (invented-fact warning heuristic) |

## Business rules preserved

- No synthetic dental A/R; missing A/R is **unavailable**, never `0`.
- No demo KPIs; figures are synthetic review fixtures only.
- Packets never imply receivables success without an explicit A/R export.

## Running the bakeoff

The bakeoff requires both local lanes to be running and is **manual / local-only**:

```bash
python scripts/run_fast_review_bakeoff.py \
  --packets evals/insurance_narrative_packets \
  --profiles chat_second_opinion fast_review \
  --out fast_review_bakeoff_report.json
```

The default report output (`fast_review_bakeoff_report.json`) is gitignored. The harness never
uses the `:11436` evaluator lane and never falls back to cloud models.
