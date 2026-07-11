"""
Phase V1 — Synthetic SoftDent / QB / ERA fixtures (Moonshot REAUDIT4 SHOULD).

Anonymized only — no real patient names, SSN, or DOB.
Known math for reconciliation staging:
  - quiet MoM: production ~$50k, payroll ~$48.5k, MoM deltas under 5%/$500
  - noisy MoM: production jump >5% and >$500 → expect RECON_VARIANCE
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

FIXTURE_DIR = Path(__file__).resolve().parent

# Documented Moonshot example gap (math-only check; not MoM alert input)
MOONSHOT_DOC_PROD = 50000.0
MOONSHOT_DOC_PAYROLL = 48500.0  # 3% below production

# Quiet MoM: realistic payroll share (~30%) + tiny MoM deltas under 5%/$500
QUIET_PROD = 50000.0
QUIET_PAYROLL = 15000.0
QUIET_PRIOR_PROD = 49800.0
QUIET_PRIOR_PAYROLL = 14900.0

NOISY_PRIOR_PROD = 50000.0
NOISY_PROD = 60000.0  # +20% / +$10k → alert
NOISY_PRIOR_PAYROLL = 15000.0
NOISY_PAYROLL = 15500.0


def _providers() -> list[str]:
    return ["SYNTH_PROV_A", "SYNTH_PROV_B", "SYNTH_PROV_C"]


def _procedure_rows(period: str, total: float, *, n: int = 10) -> list[dict[str, Any]]:
    """Split production across anonymized procedure rows (no patient ids)."""
    providers = _providers()
    codes = ["D1110", "D0120", "D2391", "D2740", "D4341"]
    per = round(total / n, 2)
    rows = []
    acc = 0.0
    for i in range(n):
        amt = per if i < n - 1 else round(total - acc, 2)
        acc += amt
        rows.append(
            {
                "period": period,
                "Provider": providers[i % 3],
                "ProcCode": codes[i % len(codes)],
                "Amount": amt,
                "Qty": 1,
                "PatientId": f"SYNTH_{i+1:03d}",  # opaque id — not a name
            }
        )
    return rows


def _payroll_rows(period: str, total_gross: float) -> list[dict[str, Any]]:
    """3 synthetic staff — wages sum to total_gross."""
    shares = [0.40, 0.35, 0.25]
    rows = []
    acc = 0.0
    for i, share in enumerate(shares):
        gross = round(total_gross * share, 2) if i < len(shares) - 1 else round(total_gross - acc, 2)
        acc += gross
        rows.append(
            {
                "Employee": f"SYNTH_STAFF_{i+1}",
                "Wages": gross,
                "period": period,
                "NetPay": round(gross * 0.75, 2),
            }
        )
    return rows


def quiet_bundle(*, period: str = "2026-06", prior: str = "2026-05") -> dict[str, Any]:
    """Stable MoM — reconciliation should NOT raise RECON_VARIANCE."""
    return {
        "meta": {
            "fixture": "quiet_mom",
            "phase": "V1",
            "expected": {
                "production": QUIET_PROD,
                "payroll": QUIET_PAYROLL,
                "payrollShare": round(QUIET_PAYROLL / QUIET_PROD, 4),
                "moonshotDocGapPct": round(
                    (MOONSHOT_DOC_PROD - MOONSHOT_DOC_PAYROLL) / MOONSHOT_DOC_PROD, 4
                ),
                "alert": False,
                "gapCode": None,
            },
            "anonymized": True,
        },
        "loadedAt": "2026-07-11T12:00:00Z",
        "softdent": {
            "dashboard": {
                "rows": [
                    {
                        "period": prior,
                        "production": QUIET_PRIOR_PROD,
                        "collections": 42000,
                        "collectionsPending": False,
                    },
                    {
                        "period": period,
                        "production": QUIET_PROD,
                        "collections": 43000,
                        "collectionsPending": False,
                    },
                ]
            },
            "procedures": {
                "rows": _procedure_rows(prior, QUIET_PRIOR_PROD)
                + _procedure_rows(period, QUIET_PROD)
            },
            "caseAcceptance": {
                "rows": [
                    {"period": period, "Presented": 20000, "Accepted": 14000, "Provider": "SYNTH_PROV_A"}
                ]
            },
            "ar": {
                "rows": [
                    {"Bucket": "0-30", "Balance": 5000},
                    {"Bucket": "31-60", "Balance": 2000},
                    {"Bucket": "90+", "Balance": 500},
                ]
            },
            "operatory": {
                "rows": [
                    {
                        "period": period,
                        "Appointments": 80,
                        "Broken": 6,
                        "Capacity": 100,
                        "Used": 72,
                    }
                ]
            },
        },
        "quickbooks": {
            "profitAndLoss": {
                "rows": [
                    {
                        "period": prior,
                        "TotalIncome": QUIET_PRIOR_PROD,
                        "TotalExpenses": 18000,
                        "Payroll": QUIET_PRIOR_PAYROLL,
                        "NetIncome": 15000,
                    },
                    {
                        "period": period,
                        "TotalIncome": QUIET_PROD,
                        "TotalExpenses": 18500,
                        "Payroll": QUIET_PAYROLL,
                        "NetIncome": 15500,
                    },
                ]
            },
            "expenseCategories": {"rows": [{"Category": "Supplies", "Amount": 1200, "period": period}]},
            "payroll": {
                "rows": _payroll_rows(prior, QUIET_PRIOR_PAYROLL)
                + _payroll_rows(period, QUIET_PAYROLL)
            },
            "ap": {
                "rows": [
                    {"period": prior, "Vendor": "SYNTH_VENDOR", "AmountDue": 800},
                    {"period": period, "Vendor": "SYNTH_VENDOR", "AmountDue": 900},
                ]
            },
        },
    }


def noisy_bundle(*, period: str = "2026-06", prior: str = "2026-05") -> dict[str, Any]:
    """Large MoM production jump — reconciliation SHOULD alert."""
    return {
        "meta": {
            "fixture": "noisy_mom",
            "phase": "V1",
            "expected": {
                "production": NOISY_PROD,
                "priorProduction": NOISY_PRIOR_PROD,
                "productionDelta": NOISY_PROD - NOISY_PRIOR_PROD,
                "alert": True,
                "gapCode": "RECON_VARIANCE",
            },
            "anonymized": True,
        },
        "loadedAt": "2026-07-11T12:00:00Z",
        "softdent": {
            "dashboard": {
                "rows": [
                    {
                        "period": prior,
                        "production": NOISY_PRIOR_PROD,
                        "collections": 40000,
                        "collectionsPending": False,
                    },
                    {
                        "period": period,
                        "production": NOISY_PROD,
                        "collections": 45000,
                        "collectionsPending": False,
                    },
                ]
            },
            "procedures": {
                "rows": _procedure_rows(prior, NOISY_PRIOR_PROD)
                + _procedure_rows(period, NOISY_PROD)
            },
            "caseAcceptance": {"rows": [{"period": period, "Presented": 10000, "Accepted": 7000}]},
            "ar": {"rows": [{"Bucket": "0-30", "Balance": 3000}]},
            "operatory": {
                "rows": [{"period": period, "Appointments": 50, "Broken": 4, "Capacity": 80, "Used": 60}]
            },
        },
        "quickbooks": {
            "profitAndLoss": {
                "rows": [
                    {
                        "period": prior,
                        "TotalIncome": NOISY_PRIOR_PROD,
                        "TotalExpenses": 12000,
                        "Payroll": NOISY_PRIOR_PAYROLL,
                        "NetIncome": 18000,
                    },
                    {
                        "period": period,
                        "TotalIncome": NOISY_PROD,
                        "TotalExpenses": 14000,
                        "Payroll": NOISY_PAYROLL,
                        "NetIncome": 25000,
                    },
                ]
            },
            "expenseCategories": {"rows": [{"Category": "Supplies", "Amount": 900}]},
            "payroll": {
                "rows": _payroll_rows(prior, NOISY_PRIOR_PAYROLL)
                + _payroll_rows(period, NOISY_PAYROLL)
            },
            "ap": {
                "rows": [
                    {"period": prior, "Vendor": "SYNTH_VENDOR", "AmountDue": 500},
                    {"period": period, "Vendor": "SYNTH_VENDOR", "AmountDue": 700},
                ]
            },
        },
    }


def synthetic_era835_text() -> str:
    """Minimal X12 835 — no patient NM1*QC segments (PHI-safe)."""
    return (
        "ISA*00*          *00*          *ZZ*SYNTHSEND     *ZZ*SYNTHRECV     *260711*1200*^*00501*000000001*0*P*:~\n"
        "GS*HP*SYNTHSEND*SYNTHRECV*20260711*1200*1*X*005010X221A1~\n"
        "ST*835*0001~\n"
        "BPR*I*1500.00*C*CHK************20260710~\n"
        "N1*PR*SYNTH PAYER DELTA~\n"
        "N1*PE*SYNTH PRACTICE~\n"
        "CLP*SYNTHCLM1*1*200*150**12*1~\n"
        "CAS*CO*45*50~\n"
        "SVC*AD:D1110*100*75~\n"
        "CLP*SYNTHCLM2*1*100*75**12*2~\n"
        "SVC*AD:D0120*100*75~\n"
        "SE*15*0001~\n"
        "GE*1*1~\n"
        "IEA*1*000000001~\n"
    )


def write_fixtures(*, out_dir: Path | None = None) -> dict[str, Path]:
    """Write JSON + ERA text under test/fixtures (or out_dir)."""
    root = Path(out_dir) if out_dir else FIXTURE_DIR
    root.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    for name, bundle in (("quiet_mom.json", quiet_bundle()), ("noisy_mom.json", noisy_bundle())):
        path = root / name
        path.write_text(json.dumps(bundle, indent=2), encoding="utf-8")
        paths[name] = path
    era_path = root / "synthetic.835"
    era_path.write_text(synthetic_era835_text(), encoding="utf-8")
    paths["synthetic.835"] = era_path
    meta = {
        "phase": "V1",
        "quiet": {
            "production": QUIET_PROD,
            "payroll": QUIET_PAYROLL,
            "expectAlert": False,
        },
        "moonshotDocExample": {
            "production": MOONSHOT_DOC_PROD,
            "payroll": MOONSHOT_DOC_PAYROLL,
            "gapPct": round((MOONSHOT_DOC_PROD - MOONSHOT_DOC_PAYROLL) / MOONSHOT_DOC_PROD, 4),
        },
        "noisy": {
            "production": NOISY_PROD,
            "priorProduction": NOISY_PRIOR_PROD,
            "expectAlert": True,
        },
        "anonymized": True,
        "note": "Synthetic only — empty ≠ $0; no SoftDent write-back.",
    }
    meta_path = root / "FIXTURE_MANIFEST.json"
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    paths["FIXTURE_MANIFEST.json"] = meta_path
    return paths


def load_fixture(name: str) -> dict[str, Any]:
    path = FIXTURE_DIR / name
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    if name == "quiet_mom.json":
        return quiet_bundle()
    if name == "noisy_mom.json":
        return noisy_bundle()
    raise FileNotFoundError(name)


if __name__ == "__main__":
    written = write_fixtures()
    for k, p in written.items():
        print(f"{k} -> {p}")
