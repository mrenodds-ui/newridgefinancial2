# Local Model Regression Gates

This repo uses a single deterministic Ollama-backed evaluation pipeline built around the canonical module in `app/evaluation/`.

## Purpose

The goal is to catch the cascade problem where a prompt tweak, model swap, or retrieval-corpus change fixes one behavior and silently breaks others.

## Canonical Layout

- `app/evaluation/client.py`: shared Ollama invocation, profile resolution, and health checks
- `app/evaluation/engine.py`: prompt builders, assertions, judge parsing, and evaluation runners
- `evals/local_model_profiles.json`: versioned model names and sampling settings
- `evals/prompts/`: versioned system prompts and judge rubric
- `evals/golden_dataset.json`: deterministic format, exact-value, retrieval, and judge cases

## Suites

### Assertion suite

Runs exact and structural checks such as:

- JSON parse success
- required JSON keys
- exact amount extraction
- exact path extraction

### Judge suite

Runs the primary chat model, then grades its answers with a stronger judge model using a strict JSON rubric.

### Retrieval assertions

Checks that context-backed answers stay grounded and fail closed when context is insufficient.

## Run Manually

```powershell
python scripts/run_local_model_evals.py
```

The report is written to `scripts/local_model_eval_report.json`.

To compare the primary GPU chat lane against the CPU/RAM second-opinion lane side-by-side:

```powershell
python scripts/run_local_model_ab_eval.py
```

Optional gate overrides:

```powershell
python scripts/run_local_model_ab_eval.py --max-ttft 0.75 --max-tps-drop 0.15
```

The default timeout budget is tuned for the checked-in two-model split, including the slower `qwen3:30b` CPU/RAM second-opinion lane. The default TTFT gate is also calibrated for that slower second-opinion path: `0.75s` is the checked-in ceiling for the resident CPU/RAM lane, while `0.5s` is still a useful stricter override when you are profiling only the fast GPU path. Override `--timeout-seconds` only when you intentionally want a tighter or looser per-request ceiling.

The comparison report is written to `scripts/local_model_ab_report.json`.
It includes a top-level per-profile summary block, a candidate-vs-baseline delta block, and a flat `regression_flags` block. Structural density is tracked with regex-based sentence counting plus blank-line paragraph counting, and the report surfaces median sentence and paragraph counts using raw numeric deltas. Outside `--dry-run`, the script exits with a non-zero code when the candidate profile breaches either the TTFT ceiling or the throughput-drop budget.
Prompt packs may also include per-case `content_assertions` with `required_contains` and `forbidden_contains`. Those checks are evaluated on both profiles, surfaced per case in the report, summarized in `content_assertion_summary`, and they fail the candidate gate when the candidate misses required grounding or includes forbidden drift.

## CI Gate Usage

To include the local LLM gate in the existing CI runner:

```powershell
python scripts/run_ci_gates.py --include-local-llm
```

To make it required:

```powershell
$env:LOCAL_LLM_EVAL_ENABLED = "true"
$env:LOCAL_LLM_EVAL_REQUIRED = "true"
python scripts/run_ci_gates.py
```

If the local gate is enabled but not required, the run may skip cleanly when Ollama is unavailable.

## Recommended Workflow

1. Update prompts, model settings, or knowledge bundle files in Git.
2. Rebuild the Open WebUI knowledge bundle when documents or exports change.
3. Run `python scripts/run_local_model_evals.py`.
4. Only keep the change if the deterministic, retrieval, and judge checks remain green.

## Notes

- The legacy `local_ai/` harness and `scripts/run_local_llm_evals.py` path have been retired.
- CI now calls the canonical runner in `scripts/run_local_model_evals.py`, which imports directly from `app/evaluation/`.
