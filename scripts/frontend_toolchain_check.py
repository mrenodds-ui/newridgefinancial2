from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass


@dataclass(frozen=True)
class FrontendToolchainCheckResult:
    available: bool
    npm_path: str | None
    npm_version: str | None
    message: str


def _resolve_npm_path() -> str | None:
    for candidate in ("npm", "npm.cmd"):
        npm_path = shutil.which(candidate)
        if npm_path:
            return npm_path
    return None


def check_frontend_toolchain() -> FrontendToolchainCheckResult:
    npm_path = _resolve_npm_path()
    if not npm_path:
        return FrontendToolchainCheckResult(
            available=False,
            npm_path=None,
            npm_version=None,
            message="npm is not available on PATH.",
        )

    try:
        result = subprocess.run(
            [npm_path, "--version"],
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
    except OSError as exc:
        return FrontendToolchainCheckResult(
            available=False,
            npm_path=npm_path,
            npm_version=None,
            message=f"npm was found at {npm_path} but could not be executed: {exc}",
        )
    except subprocess.TimeoutExpired:
        return FrontendToolchainCheckResult(
            available=False,
            npm_path=npm_path,
            npm_version=None,
            message=f"npm was found at {npm_path} but the version probe timed out.",
        )

    npm_version = (result.stdout or "").strip()
    error_text = (result.stderr or "").strip()
    if result.returncode != 0 or not npm_version:
        detail = error_text or f"exit code {result.returncode}"
        return FrontendToolchainCheckResult(
            available=False,
            npm_path=npm_path,
            npm_version=None,
            message=f"npm was found at {npm_path} but the version probe failed: {detail}",
        )

    return FrontendToolchainCheckResult(
        available=True,
        npm_path=npm_path,
        npm_version=npm_version,
        message=f"npm is available at {npm_path}.",
    )


def main() -> int:
    result = check_frontend_toolchain()
    print(result.message)
    if result.npm_version:
        print(f"npm_version={result.npm_version}")
    return 0 if result.available else 1


if __name__ == "__main__":
    raise SystemExit(main())