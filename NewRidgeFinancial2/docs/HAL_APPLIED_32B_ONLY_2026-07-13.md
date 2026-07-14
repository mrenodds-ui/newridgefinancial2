# Applied: Hard 32B-only office AI (2026-07-13)

**Status:** APPLIED  
**Policy:** Office NR2/HAL uses **only** `hal-local:32b` (Qwen3 32B Q4_K_M) on the R9700 GPU. No other local or cloud AI models.

## Code / config

| Change | Where |
|--------|--------|
| Hard allowlist `APPROVED_LOCAL_MODEL` | `nr2_hal_gateway.py` |
| Reject `payload.model` / `X-HAL-Model-Override` ≠ 32B (403) | `nr2_hal_gateway.py`, `nr2_http_server.py` |
| `call_ollama_chat` refuses foreign tags | `nr2_hal_gateway.py` |
| Cloud lane refused (403) | `nr2_http_server.py` |
| Inventory stripped to 32B lanes | `site/data/hal-models.json` |
| Cloud reasoning disabled / no auto-enable | `hal-models.json` |
| UI 120B/OSS → local 32B; cloud agent path removed | `hal-core.js`, `hal-agent.js`, `app.js` |
| Enforce script | `model-automation/Enforce-HAL-32B-Only.ps1` |
| Unit tests | `test_hal_32b_only_policy.py` |

## Ollama (this machine)

- **Installed:** `hal-local:32b`, `qwen3:32b` (base for create only)
- **Removed:** 8B/14B/24B/30B/120B/235B/180B/coder/helper/gemma/etc.
- **Loaded:** `hal-local:32b` · **100% GPU** · ctx 8192 · keep_alive Forever

## Validation

```powershell
ollama list   # only hal-local:32b + qwen3:32b
ollama ps     # only hal-local:32b, 100% GPU
python .\NewRidgeFinancial2\scripts\validate_hal_local_32b.py --skip-prompts
python -m pytest NewRidgeFinancial2/test_hal_32b_only_policy.py -q
```

## Out of scope (by design)

- Cursor / Moonshot consult scripts remain **dev tooling**, not office HAL routing.
- Staff must restart `browser_app` to pick up gateway + `hal-models.json` changes.
