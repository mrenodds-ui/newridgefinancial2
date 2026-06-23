from __future__ import annotations

import json
import os
import sys
from pathlib import Path


DEFAULT_AUTH_USERS_JSON = json.dumps(
    [
        {
            "username": "contract-generator",
            "display_name": "Contract Generator",
            "password": "contract-generator",
            "roles": ["dashboard:read", "hal:operator", "hal:index:refresh", "admin"],
        }
    ]
)


def main() -> int:
    if len(sys.argv) > 2:
        print("Usage: python scripts/export_openapi.py [output_path]", file=sys.stderr)
        return 2

    output_path = Path(sys.argv[1]) if len(sys.argv) == 2 else Path("frontend/src/api/generated/backend-openapi.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    repo_root = Path(__file__).resolve().parent.parent
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    os.environ.setdefault("APP_AUTH_USERS_JSON", DEFAULT_AUTH_USERS_JSON)

    from app.main import app

    output_path.write_text(json.dumps(app.openapi(), indent=2), encoding="utf-8")
    print(f"Wrote OpenAPI schema to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())