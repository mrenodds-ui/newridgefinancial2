#!/usr/bin/env python3
"""Operator production readiness checklist — Moonshot backlog item 3."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = ROOT.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _check(name: str, ok: bool, detail: str = "") -> dict:
    return {"name": name, "ok": bool(ok), "detail": detail}


def run_checks() -> dict:
    checks: list[dict] = []

    from nr2_tls import ensure_localhost_tls_certificates, tls_enforced

    enforced = tls_enforced()
    cert, key = ensure_localhost_tls_certificates(REPO_ROOT / "app_data" / "nr2")
    checks.append(_check("tls_enforced", enforced, f"cert={'yes' if cert else 'no'}"))
    checks.append(_check("tls_certs_present", bool(cert and key), str(cert or "")))

    from nr2_startup_checks import resolve_bind_host

    try:
        host = resolve_bind_host()
        checks.append(_check("loopback_bind", host in {"127.0.0.1", "localhost"}, host))
    except SystemExit:
        checks.append(_check("loopback_bind", False, "non-loopback bind rejected"))

    from nr2_db_crypto import db_encryption_enabled

    enc = db_encryption_enabled()
    checks.append(_check("db_encryption_enabled", enc, "NR2_DB_ENCRYPTION"))
    if enc:
        try:
            import pysqlcipher3  # noqa: F401

            checks.append(_check("pysqlcipher3_installed", True, "ok"))
        except ImportError:
            checks.append(_check("pysqlcipher3_installed", False, "pip install pysqlcipher3"))

    from import_diagnostics import assess_import_readiness

    readiness = assess_import_readiness(operation="posting")
    checks.append(
        _check(
            "import_readiness_posting",
            bool(readiness.get("ok")),
            str(readiness.get("level") or readiness.get("error") or ""),
        )
    )
    completeness = readiness.get("completeness") or {}
    checks.append(
        _check(
            "import_completeness",
            bool(completeness.get("ok")),
            f"{completeness.get('scorePct')}% / min {completeness.get('minPct')}%",
        )
    )

    from nr2_audit_log import verify_financial_audit_chain

    audit = verify_financial_audit_chain()
    checks.append(_check("financial_audit_chain", bool(audit.get("verified")), f"count={audit.get('count')}"))

    qbo_id = os.environ.get("NR2_QBO_CLIENT_ID", "").strip()
    checks.append(_check("qbo_configured", bool(qbo_id), "optional — set NR2_QBO_CLIENT_ID"))
    twilio = os.environ.get("NR2_TWILIO_ACCOUNT_SID", "").strip()
    checks.append(_check("twilio_configured", bool(twilio), "optional — set NR2_TWILIO_ACCOUNT_SID"))

    passed = sum(1 for c in checks if c["ok"])
    required = [c for c in checks if c["name"] not in {"qbo_configured", "twilio_configured"}]
    required_ok = all(c["ok"] for c in required)
    return {
        "ok": required_ok,
        "passed": passed,
        "total": len(checks),
        "checks": checks,
    }


def main() -> int:
    report = run_checks()
    print(json.dumps(report, indent=2))
    if not report.get("ok"):
        print("\nProduction readiness: FAIL — resolve required checks above.", file=sys.stderr)
        return 1
    print("\nProduction readiness: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
