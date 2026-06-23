from __future__ import annotations

import json
import sys

from .services import fetch_quickbooks_sdk_summary_direct


def main() -> int:
    if len(sys.argv) not in {2, 4}:
        print("[]")
        return 1

    topic = sys.argv[1]
    period_dict = None
    if len(sys.argv) == 4:
        period_dict = {
            "start_date": sys.argv[2],
            "end_date": sys.argv[3],
        }
    try:
        payload = fetch_quickbooks_sdk_summary_direct(topic, period_dict=period_dict)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 2

    print(json.dumps(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())