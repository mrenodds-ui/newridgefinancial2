"""Serve elite page mockups embedded inside Start Program (static HTML, no live wiring)."""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MOCKUP_ELITE_DIR = REPO_ROOT / ".local_logs" / "moonshot_financial_eval" / "page_mockups_elite"
PAGE_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

# Strip duplicate app chrome when elite HTML is shown inside the staff page iframe.
# Outer shell (nav rail, hero, filters) comes from nr2-moonshot-mockup-chrome.js in compact mode.
EMBED_CSS = """
html[data-nr2-embed="1"] .nav-rail,
html[data-nr2-embed="1"] .ms-rail,
html[data-nr2-embed="1"] aside.nav-rail { display: none !important; }

html[data-nr2-embed="1"] .mission-frame { grid-template-columns: 1fr !important; height: auto !important; min-height: 0 !important; overflow: visible !important; }
html[data-nr2-embed="1"] .app-shell { height: auto !important; min-height: 0 !important; overflow: visible !important; }

html[data-nr2-embed="1"] .page-shell,
html[data-nr2-embed="1"] .app,
html[data-nr2-embed="1"] .ms-main,
html[data-nr2-embed="1"] .main,
html[data-nr2-embed="1"] .main-stage,
html[data-nr2-embed="1"] body > header,
html[data-nr2-embed="1"] main,
html[data-nr2-embed="1"] .toolbar { margin-left: 0 !important; padding-left: 0 !important; }

html[data-nr2-embed="1"] .page-header,
html[data-nr2-embed="1"] .page-filters,
html[data-nr2-embed="1"] .page-title,
html[data-nr2-embed="1"] .page-sub,
html[data-nr2-embed="1"] .top-bar,
html[data-nr2-embed="1"] .ms-topbar,
html[data-nr2-embed="1"] body > header,
html[data-nr2-embed="1"] body > .toolbar,
html[data-nr2-embed="1"] .badge-safety { display: none !important; }

html[data-nr2-embed="1"] body,
html[data-nr2-embed="1"] html {
  min-height: auto !important;
  height: auto !important;
  overflow: visible !important;
  background: transparent !important;
}

html[data-nr2-embed="1"] .page-shell { padding: 0 0 24px !important; }
html[data-nr2-embed="1"] main { padding-top: 0 !important; }
html[data-nr2-embed="1"] .content,
html[data-nr2-embed="1"] .widget-grid,
html[data-nr2-embed="1"] .dashboard-grid { height: auto !important; max-height: none !important; overflow: visible !important; }

html[data-nr2-embed="1"] .kanban { height: auto !important; min-height: 420px !important; max-height: none !important; }
html[data-nr2-embed="1"] .lane { max-height: none !important; }
"""

EMBED_BOOT = '<script>document.documentElement.setAttribute("data-nr2-embed","1");</script>'


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
    inject = f'<style id="nr2-mockup-embed">{EMBED_CSS}</style>{EMBED_BOOT}'
    if "</head>" in html:
        return html.replace("</head>", inject + "</head>", 1)
    return inject + html
