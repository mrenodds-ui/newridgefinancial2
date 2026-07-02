# Gemma 2 HAL programming review — triage (July 2026)

Local report: `gemma2_hal_program_9b_report.md` (gitignored). Re-run with:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_gemma2_hal_program_eval.ps1 -Size 9b
powershell -ExecutionPolicy Bypass -File .\scripts\run_gemma2_hal_program_eval.ps1 -Size 27b
```

Apply the same evidence bar as the dual-model audit: **file + line or validator assertion required** before changing production code.

## 9B report triage

| Finding | Verdict | Notes |
|---------|---------|-------|
| `halAutoRefreshCalled` not reset | **False positive** | Symbol does not exist in `NewRidgeFinancial2/site/` (model hallucination). |
| Globals `DesktopBridge` / `ImportCoordinator` | **By design** | Intentional pywebview desktop bridge; browser mode uses degraded stubs. Not a bug for NR2 architecture. |
| Generic `assert` messages in validators | **Partial / low priority** | Node validators (`validate-hal.mjs`, `validate-pages.mjs`) already use descriptive messages. Python `unittest` uses method docstrings; bulk assert rewrites are low ROI. |

## Recommended next steps

1. Run **27B** review when daily GPU lanes can be stopped (`-Size 27b` or `-Both`).
2. Cross-check any new 27B findings against `node validate-hal.mjs` before fixing.
3. Optional: set `NR2_EVAL_SECONDARY_MODEL=hal-gemma2:9b` for dual-model micro eval secondary pass (see `.env.example`).

## Do not auto-fix from model output

- Architecture refactors (remove globals, rewrite agent loop) without staff sign-off.
- Findings that cite symbols or files not present in the repo snapshot.
