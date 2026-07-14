# ERA Remittance Discovery Scanner — APPLIED (hal-10575)

**Date:** 2026-07-12  
**Consult:** `MOONSHOT_WHATS_NEXT_AFTER_ERA_10574_SMOKE_2026-07-13.md`  
**Operator:** proceed  
**Build:** **hal-10575**

## What shipped

| Item | Detail |
|------|--------|
| `discover_era_candidates()` | Read-only walk of SoftDent/export roots for `.835`/`.edi`/`.x12` + sniffed remittance text |
| False-positive guards | Skip manifests/DaySheet/Register, UUID substring “835”, code/json/xlsx; require ST*835-class sniff |
| API | `GET`/`POST /api/apex/hal/era-inbox/discover` |
| Gap tile | **Scan for ERA Files** button (+ HAL chip) next to Refresh Inbox |
| HAL policy | “scan for ERA…” → `policy:era-discover` with paths / procurement honesty |
| Wrapper | `softdent_practice_exports.discover_era_candidates` |
| Honesty | Zero candidates → `No local ERA files detected; procurement required` (empty ≠ $0) |
| SoftDent write-back | **Never** — discovery does not move/copy files or invent dollars |

## Live machine scan (this host)

| Field | Value |
|-------|--------|
| scannedRoots | `C:\SoftDentFinancialExports`, `C:\SoftDentReportExports`, `C:\SoftDent` |
| candidateCount | **0** |
| chipLabel | No local ERA files detected; procurement required |
| writeBack | false |

## Validation

```text
cd NewRidgeFinancial2
python -m unittest test_era_remittance_discovery_hal10575 test_era_inbox_mutation_token_hal10574 -v
```

| Gate | Result |
|------|--------|
| Unit tests 10575 | **PASS** (8/8) |
| Prior mutation-token tests | **PASS** |
| Live discovery → none_found | **PASS** |
| Gap widget exposes `eraDiscoverUrl` | **PASS** |
| HAL discover policy | **PASS** |

## Staff use

1. Restart backend + hard-refresh for **hal-10575**
2. SoftDent → Collections Gap → **Scan for ERA Files**
3. If candidates appear: verify paths → copy into `C:\SoftDentFinancialExports\era` → **Refresh Inbox**
4. If none: procure real payer 835s (discovery proved local absence)

## Not done

- Auto-move candidates into inbox  
- Real payer portal procurement  
- Register re-export / synthetic 835 as production  
