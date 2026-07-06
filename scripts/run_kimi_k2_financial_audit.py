from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

REPO = Path(r"C:\NewRidgeFamilyFinancial")
OUT_DIR = REPO / ".local_logs" / "multi_model_audit"
OUT_DIR.mkdir(parents=True, exist_ok=True)

FILES = [
    "_legacy/app/data_pipeline.py",
    "_legacy/app/services.py",
    "_legacy/app/hal/financial_tools.py",
    "_legacy/app/hal/accounting_tools.py",
    "_legacy/app/hal/softdent_read_broker.py",
    "frontend/src/components/mockup/MissionControlMockupPage.tsx",
]

SYSTEM = """You are a senior financial software auditor. Review only the provided code.
Do not invent files, databases, APIs, accounting flows, or runtime behavior that are not explicitly present.
Focus on financial correctness, data integrity, accounting edge cases, claims or AR risk, refresh/import failure modes,
security of financial data access, and dashboard-metric trustworthiness.
Return markdown with exactly these sections:
# Verdict
## Key Findings
## Financial Integrity Risks
## Data Pipeline Risks
## Dashboard / Reporting Risks
## Performance Notes
## Suggested Fix Order
Use concise bullets. Mark each finding with Severity: Critical|High|Medium|Low. If no confirmed issue exists for a category, say so.
"""


def build_context() -> str:
    parts: list[str] = []
    for rel in FILES:
        content = (REPO / rel).read_text(encoding="utf-8", errors="replace")
        ext = Path(rel).suffix.lstrip(".") or "txt"
        parts.append(f"### FILE: {rel}\n```{ext}\n{content}\n```")
    return "\n\n".join(parts)


def _resolve_api_key() -> str:
    return str(
        os.getenv("OPENROUTER_API_KEY")
        or os.getenv("KIMI_K2_API_KEY")
        or os.getenv("MOONSHOT_API_KEY")
        or ""
    ).strip()


def _resolve_base_url() -> str:
    return str(
        os.getenv("KIMI_K2_BASE_URL")
        or os.getenv("MOONSHOT_API_BASE")
        or "https://openrouter.ai/api/v1/chat/completions"
    ).strip()


def _resolve_model() -> str:
    explicit_model = str(os.getenv("KIMI_K2_MODEL") or os.getenv("MOONSHOT_MODEL") or "").strip()
    if explicit_model:
        return explicit_model

    base_url = _resolve_base_url().lower()
    if "api.moonshot.ai" in base_url or "api.moonshot.cn" in base_url:
        return "kimi-k2.6"
    return "moonshotai/kimi-k2"


def _failure_report(message: str) -> str:
    return "\n".join(
        [
            "# Verdict",
            "- Severity: Medium - Kimi K2 audit did not run.",
            "## Key Findings",
            f"- Severity: Medium - {message}",
            "## Financial Integrity Risks",
            "- Severity: Low - No Kimi-specific financial review was produced.",
            "## Data Pipeline Risks",
            "- Severity: Low - External model execution failed before analysis.",
            "## Dashboard / Reporting Risks",
            "- Severity: Low - No additional dashboard findings were generated.",
            "## Performance Notes",
            "- Severity: Low - Failure happened before token generation completed.",
            "## Suggested Fix Order",
            "- Severity: Medium - Set OPENROUTER_API_KEY or KIMI_K2_API_KEY and rerun the script.",
        ]
    )


def main() -> int:
    out_file = OUT_DIR / "kimi_k2_financial_program_report.md"
    api_key = _resolve_api_key()
    if not api_key:
        out_file.write_text(
            _failure_report("Missing OPENROUTER_API_KEY, KIMI_K2_API_KEY, or MOONSHOT_API_KEY."),
            encoding="utf-8",
        )
        print(out_file.name)
        return 1

    user = (
        "Analyze this financial-program slice before any fixes. Focus on confirmed financial correctness bugs, accounting/data integrity issues, AR or insurance workflow risk, import/refresh failure modes, and dashboard metric trustworthiness. Prefer evidence over style commentary.\n\n"
        + build_context()
    )

    payload = {
        "model": _resolve_model(),
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
        ],
        "temperature": 0.1,
        "top_p": 1,
        "max_tokens": 2500,
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    referer = str(os.getenv("OPENROUTER_HTTP_REFERER") or "").strip()
    title = str(os.getenv("OPENROUTER_X_TITLE") or "NewRidgeFamilyFinancial Audit").strip()
    if referer:
        headers["HTTP-Referer"] = referer
    if title:
        headers["X-Title"] = title

    req = Request(
        _resolve_base_url(),
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    try:
        with urlopen(req, timeout=3600) as response:
            body = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        out_file.write_text(_failure_report(f"HTTP {exc.code}: {detail}"), encoding="utf-8")
        print(out_file.name)
        return 1
    except URLError as exc:
        out_file.write_text(_failure_report(f"Network error: {exc.reason}"), encoding="utf-8")
        print(out_file.name)
        return 1

    choices = body.get("choices") if isinstance(body, dict) else []
    message = choices[0].get("message") if choices and isinstance(choices[0], dict) else {}
    content = str((message or {}).get("content") or "").strip()
    if not content:
        out_file.write_text(_failure_report(f"Empty response body: {json.dumps(body)[:4000]}"), encoding="utf-8")
        print(out_file.name)
        return 1

    out_file.write_text(content, encoding="utf-8")
    print(out_file.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())