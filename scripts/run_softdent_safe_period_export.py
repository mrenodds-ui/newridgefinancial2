"""Safe SoftDent period export orchestrator (sign-on + Register + Collections).

- Credentials: SOFTDENT_SIGNON_USER / SOFTDENT_SIGNON_PASSWORD from local .env only
- Never prints password
- SoftDent read-only (report export only; no write-back)
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "NewRidgeFinancial2"))

from softdent_gui_export import run_safe_period_exports  # noqa: E402


def main() -> int:
    today = date.today()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default=f"{today.year:04d}-{today.month:02d}-01")
    parser.add_argument("--end", default=today.isoformat())
    parser.add_argument("--skip-register", action="store_true")
    parser.add_argument("--skip-collections", action="store_true")
    parser.add_argument("--skip-signon", action="store_true")
    args = parser.parse_args()
    result = run_safe_period_exports(
        start=date.fromisoformat(args.start),
        end=date.fromisoformat(args.end),
        do_register=not args.skip_register,
        do_collections=not args.skip_collections,
        ensure_signon=not args.skip_signon,
    )
    # Defense in depth: never echo secret-looking keys
    blob = json.dumps(result, indent=2)
    for bad in ("password", "PASSWORD", "PWD="):
        if bad in blob and "passwordConfigured" not in bad:
            # passwordConfigured is allowed; raw password must not appear
            if '"password":' in blob.lower().replace("passwordconfigured", ""):
                print("REFUSING to print payload that may contain secrets", file=sys.stderr)
                return 2
    print(blob)
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
