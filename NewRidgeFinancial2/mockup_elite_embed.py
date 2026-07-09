"""Serve elite page mockups embedded inside Start Program (static HTML, no live wiring)."""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MOCKUP_ELITE_DIR = REPO_ROOT / ".local_logs" / "moonshot_financial_eval" / "page_mockups_elite"
PAGE_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

EMBED_CSS = """
.nav-rail { display: none !important; }
.page-shell { margin-left: 0 !important; padding: 12px 0 24px !important; }
.page-header, .page-filters { display: none !important; }
body { min-height: auto !important; background: transparent !important; }
"""


def list_mockup_page_ids() -> list[str]:
    if not MOCKUP_ELITE_DIR.is_dir():
        return []
    return sorted(
        path.stem
        for path in MOCKUP_ELITE_DIR.glob("*.html")
        if path.name != "index.html" and PAGE_ID_RE.fullmatch(path.stem)
    )


def mockup_elite_path(page_id: str) -> Path | None:
    if not page_id or not PAGE_ID_RE.fullmatch(page_id):
        return None
    path = MOCKUP_ELITE_DIR / f"{page_id}.html"
    if not path.is_file():
        return None
    return path


def render_embed_html(page_id: str) -> str | None:
    path = mockup_elite_path(page_id)
    if not path:
        return None
    html = path.read_text(encoding="utf-8", errors="replace")
    inject = f'<style id="nr2-mockup-embed">{EMBED_CSS}</style>'
    if "</head>" in html:
        return html.replace("</head>", inject + "</head>", 1)
    return inject + html
