# Moonshot AI — HAL page recommendations (BLOCKED)

**Date:** 2026-07-14  
**Status:** no API key in this cloud agent run  
**Script ready:** `scripts/run_moonshot_hal_page_recommendations_consult.py`

## Operator request (verbatim)

> ask moonshot ai for any recommendation for hal's page and report

## Blocker

This cloud run has **no saved Cursor Environment** (`environment: null`) and no
`MOONSHOT_API_KEY` / `OPENROUTER_API_KEY` / `KIMI_K2_API_KEY` in the VM.

Network to Moonshot/OpenRouter is fine; only the key is missing.

## Unblock (Cloud — recommended)

1. Open [Cloud Agents → Environments](https://cursor.com/dashboard/cloud-agents#environments)
2. Create or select an environment for this repo
3. Add a **Runtime Secret**:
   - Name: `MOONSHOT_API_KEY` (or `OPENROUTER_API_KEY`)
   - Value: your key
4. Attach that environment to a **new** cloud agent run (existing runs do not pick up new secrets)
5. Say: `run scripts/run_moonshot_hal_page_recommendations_consult.py and report`

## Unblock (local Windows workstation)

Keys already live in your User env / prior Moonshot consults:

```bat
cd /d C:\NewRidgeFamilyFinancial
git fetch origin
git checkout cursor/hal-subpages-design-d32f
git pull
python scripts\run_moonshot_hal_page_recommendations_consult.py
```

Report lands at:
`NewRidgeFinancial2\docs\MOONSHOT_HAL_PAGE_RECOMMENDATIONS_CONSULT_YYYY-MM-DD.md`
