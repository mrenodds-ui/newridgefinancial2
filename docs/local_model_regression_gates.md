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

By default, `chat` resolves to the frontend lane (`:11434`, `qwen3:14b`) and `chat_second_opinion` resolves to the backend lane (`:11435`, `qwen3:14b`) via `app/ai_local_config.py`. Lane-specific env overrides such as `AI_FRONTEND_MODEL`, `AI_BACKEND_MODEL`, `AI_FRONTEND_BASE_URL`, and `AI_BACKEND_BASE_URL` apply before the run starts. Use `--base-url` only when you intentionally want one URL to override both profiles.

Optional gate overrides:

```powershell
python scripts/run_local_model_ab_eval.py --max-ttft 0.75 --max-tps-drop 0.15
```

The default timeout budget is tuned for the checked-in two-model split, including the slower `qwen3:14b` CPU/RAM second-opinion lane. The default TTFT gate is also calibrated for that second-opinion path: `0.75s` is the checked-in ceiling for the resident CPU/RAM lane, while `0.5s` is still a useful stricter override when you are profiling only the fast GPU path. Override `--timeout-seconds` only when you intentionally want a tighter or looser per-request ceiling.

The comparison report is written to `scripts/local_model_ab_report.json`.
It includes a top-level per-profile summary block, a candidate-vs-baseline delta block, and a flat `regression_flags` block. Structural density is tracked with regex-based sentence counting plus blank-line paragraph counting, and the report surfaces median sentence and paragraph counts using raw numeric deltas. Outside `--dry-run`, the script exits with a non-zero code when the candidate profile breaches either the TTFT ceiling or the throughput-drop budget.
Prompt packs may also include per-case `content_assertions` with `required_contains` and `forbidden_contains`. Those checks are evaluated on both profiles, surfaced per case in the report, summarized in `content_assertion_summary`, and they fail the candidate gate when the candidate misses required grounding or includes forbidden drift.

## CI Gate Usage

GitHub Actions runs `python scripts/run_ci_gates.py` in `.github/workflows/test.yml` (`ci-gates` job) on every push/PR to `main`.

Deployment security contracts (`APP_ENV`, `APP_AUTH_SESSION_SECRET`, `WIDGET_API_KEY`, LiteLLM auth) are documented in `docs/API.md` and `README.md` (**Production environment checklist**).

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
- Deployment hardening: unset `APP_ENV` is treated as production-like. Set `APP_ENV=development` only on local workstations. Production requires `APP_AUTH_SESSION_SECRET` and `WIDGET_API_KEY`. LiteLLM proxy use outside localhost requires `LITELLM_MASTER_KEY`.
- Local 235B evaluator outputs (`235b_*.md`, `235b_*.txt`, `235b_*.json`, raw logs) are gitignored at the repo root. Keep them local unless you deliberately sanitize and approve a commit.
