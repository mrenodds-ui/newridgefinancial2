# Portal-derived NR2 ops layer (integration health, support bundle, daily closeout)

Porting ideas from NewRidge Portal into read-only NR2 desktop scope — no patient portal or writeback.

## Modules

| Module | Purpose |
|--------|---------|
| `integration_health.py` | Single snapshot: imports, Ollama, documents, posting queue, automations |
| `support_bundle.py` | Redacted zip for operator troubleshooting |
| `financial_reports.py` | Claims tracking + A/R aging summaries from import cache |
| `daily_closeout.py` | Morning/day-end checklist |
| `automation_registry.py` | Job manifest + last-run state |
| `program_help.py` | "How do I…?" topic router |
| `knowledge_memory_index.py` | Token search over governed memories |
| `hal_audit.py` | JSONL audit log + `config/hal_policy.yaml` |

## HAL commands

- "Show integration health"
- "Build support bundle"
- "Run daily closeout"
- "Show financial reports"
- "Show automation registry"
- "How do I refresh imports?"

## APIs

Loopback (desktop): `/api/integration-health`, `/api/automation-registry`, `/api/support-bundle` (POST), `/api/financial-reports`, `/api/daily-closeout`

Desktop bridge: `getIntegrationHealth`, `buildSupportBundle`, etc.

## Tests

```powershell
cd NewRidgeFinancial2
python -m pytest test_portal_ops.py -q
```
