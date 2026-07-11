# Phase I1 Applied — Structured JSON Insights

**Date:** 2026-07-11  
**Build:** hal-10472  
**Plan:** AI Program Manager Upgrade  
**Prior:** Phase I0 orchestrator (`MOONSHOT_AI_PM_PHASE_I0_APPLIED_2026-07-11.md`)  
**Status:** Phase I1 only — validated; **stop for I2 approval**

## Shipped

| Item | Detail |
|------|--------|
| Schemas | `data/insight_schemas/{kpi-card,trend-chart,alert-banner}.json` |
| Pack | `apex_structured_insight_pack.py` — extract, validate (jsonschema), PHI reject, last-insight store |
| Orchestrator | Attaches insight when query wants structured / health audit; markdown fallback on failure |
| API | `POST /api/apex/hal/insight-validate` |
| Widget | `hal-ai-insight` (`type: ai-insight`) on HAL page |
| UI | Safe renderer (no raw HTML from model); CTA navigates Apex pages |
| Tests | `test_apex_structured_insight_i1.py` |

## Honesty rules

- Numeric insights **require** `source_refs` (`softdent|qb|nr2|import:…:YYYY-MM[-DD]`)
- Missing/invalid JSON → chat keeps markdown; widget shows empty / unavailable
- SSN/DOB patterns rejected

## Validation

```text
python -m pytest NewRidgeFinancial2/test_apex_structured_insight_i1.py NewRidgeFinancial2/test_apex_orchestrator_i0.py -q
```

## Enable

```text
set NR2_AI_ORCHESTRATOR=1
```

Ask HAL e.g. “monthly practice health audit” or “structured insight as json …” when flag is on.

## Next

**I2** SoftDent Collections/Daysheet honesty (DEF-001 class)

Await: **approve I2**
