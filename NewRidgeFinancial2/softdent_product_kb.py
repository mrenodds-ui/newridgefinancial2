"""SoftDent full product knowledge base — program-readable + HAL formatter.

Built from Carestream SoftDent Online Help (OH_DE1010 CHM) via
`scripts/build_softdent_product_kb.py` + office doctrine / NR2 automation ids.

Loads:
  - softdent_product_kb.json — TOC, reports, modules, howSoftDentWorks
  - softdent_product_kb_topics.json — searchable Help topic bodies (inside-out)

Automation subsets remain authoritative in:
  - softdent_gui_menu_map.json
  - softdent_master_reports.json
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

KB_DIR = Path(__file__).resolve().parent
KB_PATH = KB_DIR / "softdent_product_kb.json"
TOPICS_PATH = KB_DIR / "softdent_product_kb_topics.json"


@lru_cache(maxsize=1)
def load_softdent_product_kb(path: str | None = None) -> dict[str, Any]:
    target = Path(path) if path else KB_PATH
    if not target.is_file():
        raise FileNotFoundError(f"SoftDent product KB missing: {target}")
    return json.loads(target.read_text(encoding="utf-8-sig"))


@lru_cache(maxsize=1)
def load_softdent_product_topic_bodies(path: str | None = None) -> list[dict[str, Any]]:
    target = Path(path) if path else TOPICS_PATH
    if not target.is_file():
        return []
    data = json.loads(target.read_text(encoding="utf-8-sig"))
    topics = data.get("topics") if isinstance(data, dict) else data
    return list(topics or []) if isinstance(topics, list) else []


def clear_softdent_product_kb_cache() -> None:
    load_softdent_product_kb.cache_clear()
    load_softdent_product_topic_bodies.cache_clear()


def _tokens(query: str) -> list[str]:
    q = str(query or "").strip().lower()
    if not q:
        return []
    toks = [t for t in re.split(r"[^a-z0-9]+", q) if len(t) >= 3]
    return toks or [q]


def product_kb_summary() -> dict[str, Any]:
    kb = load_softdent_product_kb()
    cats = (kb.get("reportCatalog") or {}).get("categories") or {}
    cat_counts = {
        name: int((meta or {}).get("reportCount") or 0)
        for name, meta in cats.items()
        if name != "overview" and isinstance(meta, dict)
    }
    bodies = load_softdent_product_topic_bodies()
    return {
        "version": kb.get("version"),
        "built": kb.get("built"),
        "tocEntryCount": ((kb.get("helpToc") or {}).get("entryCount")),
        "reportCountParsed": ((kb.get("reportCatalog") or {}).get("reportCountParsed")),
        "topicBodyCount": int(kb.get("topicBodyCount") or len(bodies)),
        "howItWorksArticleCount": len(
            ((kb.get("howSoftDentWorks") or {}).get("coreHelpArticles") or {})
        ),
        "categoryCounts": cat_counts,
        "moduleCount": len(kb.get("productModules") or []),
        "guiExportIds": list(((kb.get("nr2Automation") or {}).get("guiExportIds") or [])),
        "helpUrlBase": kb.get("helpUrlBase"),
        "localHelpChm": ((kb.get("officeDoctrine") or {}).get("localHelpChm")),
    }


def lookup_report(query: str, *, limit: int = 12) -> list[dict[str, Any]]:
    """Keyword match against Help report catalog (name + description)."""
    tokens = _tokens(query)
    if not tokens:
        return []
    kb = load_softdent_product_kb()
    scored: list[tuple[int, dict[str, Any]]] = []
    for rep in (kb.get("reportCatalog") or {}).get("allReports") or []:
        blob = f"{rep.get('name','')} {rep.get('description','')} {rep.get('category','')}".lower()
        score = sum(1 for t in tokens if t in blob)
        if score:
            if rep.get("nr2GuiId"):
                score += 2
            scored.append((score, rep))
    scored.sort(key=lambda x: (-x[0], str(x[1].get("name") or "")))
    return [r for _, r in scored[: max(1, int(limit))]]


def lookup_help_topics(query: str, *, limit: int = 15) -> list[dict[str, Any]]:
    """Keyword match against SoftDent Online Help TOC names."""
    tokens = _tokens(query)
    if not tokens:
        return []
    kb = load_softdent_product_kb()
    scored: list[tuple[int, dict[str, Any]]] = []
    for ent in (kb.get("helpToc") or {}).get("entries") or []:
        name = str(ent.get("name") or "")
        blob = name.lower()
        score = sum(1 for t in tokens if t in blob)
        if score:
            scored.append((score, ent))
    scored.sort(key=lambda x: (-x[0], str(x[1].get("name") or "")))
    return [e for _, e in scored[: max(1, int(limit))]]


def lookup_topic_bodies(query: str, *, limit: int = 8) -> list[dict[str, Any]]:
    """Deep keyword match against SoftDent Help topic body text."""
    tokens = _tokens(query)
    if not tokens:
        return []
    scored: list[tuple[int, dict[str, Any]]] = []
    for topic in load_softdent_product_topic_bodies():
        title = str(topic.get("title") or "")
        body = str(topic.get("body") or "")
        title_l = title.lower()
        body_l = body.lower()
        score = 0
        for t in tokens:
            if t in title_l:
                score += 4
            if t in body_l:
                score += 1 + min(3, body_l.count(t))
        if score:
            scored.append((score, topic))
    scored.sort(key=lambda x: (-x[0], str(x[1].get("title") or "")))
    return [t for _, t in scored[: max(1, int(limit))]]


def _excerpt(text: str, *, max_chars: int = 700) -> str:
    raw = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(raw) <= max_chars:
        return raw
    cut = raw[: max_chars - 1].rsplit(" ", 1)[0]
    return cut + "…"


def format_softdent_product_kb_hal_reply(query: str = "") -> str:
    """HAL reply: how SoftDent works + deep Help bodies + matching reports."""
    kb = load_softdent_product_kb()
    doctrine = kb.get("officeDoctrine") or {}
    how = kb.get("howSoftDentWorks") or {}
    summary = product_kb_summary()
    modules = kb.get("productModules") or []
    cat_bits = ", ".join(
        f"{name} ({n})" for name, n in (summary.get("categoryCounts") or {}).items() if n
    )
    lines = [
        "SOFTDENT INSIDE-OUT KB (Carestream SoftDent Online Help OH_DE1010 + this office):",
        f"Build {doctrine.get('practiceBuild') or 'SoftDent desktop'}.",
        str(how.get("summary") or "").strip(),
        "Lifecycle: " + " -> ".join(str(x) for x in (how.get("lifecycle") or [])[:9]) + ".",
        f"Help TOC topics: {summary.get('tocEntryCount')}; "
        f"Help topic bodies searchable: {summary.get('topicBodyCount')}; "
        f"report rows: {summary.get('reportCountParsed')} across thirteen categories"
        + (f" [{cat_bits}]." if cat_bits else "."),
        "Product modules: "
        + "; ".join(str(m.get("label") or m.get("id")) for m in modules)
        + ".",
        "Office doctrine: Excel or Print Preview only — never Printer; empty ≠ $0; "
        "period-close $ from desktop Excel; ops detail may use Sensei/sd_*/ODBC; "
        f"launch {doctrine.get('launch')}.",
        f"F1 / Help → SoftDent Help. Local CHM: {doctrine.get('localHelpChm')}. "
        f"Online: {kb.get('helpUrlBase')}. Support: {doctrine.get('supportPortal')}.",
        "NR2 automates a money/ops subset only (softdent_gui_menu_map.json / "
        "softdent_master_reports.json) — HAL still knows the rest of the product from Help.",
    ]
    q = str(query or "").strip()
    if q:
        bodies = lookup_topic_bodies(q, limit=5)
        if bodies:
            lines.append("SoftDent Help article text (matched):")
            for b in bodies:
                lines.append(
                    f"- {b.get('title')} [{b.get('file')}]: {_excerpt(b.get('body') or '', max_chars=650)}"
                )
        hits = lookup_report(q, limit=6)
        if hits:
            lines.append("Matching SoftDent reports:")
            for h in hits:
                nr2 = f" [NR2 gui:{h.get('nr2GuiId')}]" if h.get("nr2GuiId") else ""
                lines.append(
                    f"- {h.get('category')}: {h.get('name')} — "
                    f"{(h.get('description') or '')[:180]}{nr2}"
                )
        topics = lookup_help_topics(q, limit=6)
        if topics:
            lines.append("Matching SoftDent Help TOC topics:")
            for t in topics:
                url = t.get("helpUrl") or t.get("local") or ""
                lines.append(f"- {t.get('name')}" + (f" → {url}" if url else ""))
        # Core how-it-works articles when asking broadly how SoftDent works
        if re.search(r"\b(how\s+(does|do|to)|inside\s+and\s+out|entire|everything|works?)\b", q.lower()):
            cores = (how.get("coreHelpArticles") or {})
            if cores:
                lines.append("Core SoftDent how-it-works Help articles:")
                for _stem, art in list(cores.items())[:6]:
                    lines.append(
                        f"- {art.get('title')}: {_excerpt(art.get('body') or '', max_chars=500)}"
                    )
        if not bodies and not hits and not topics:
            lines.append(
                "No specific Help keyword hit — try a SoftDent feature name "
                "(Daysheet, Charting, ERA, Treatment Plan, Report Manager) or open F1."
            )
    keys = kb.get("keystrokes") or {}
    if keys:
        key_bits = ", ".join(f"{k}={v}" for k, v in list(keys.items())[:8])
        lines.append(f"Keystrokes: {key_bits}.")
    return " ".join(x for x in lines if x)


def query_touches_softdent_product(query: str) -> bool:
    """True when the user asks about SoftDent product features / Help / how it works."""
    q = str(query or "").lower()
    if re.search(
        r"\b("
        r"softdent\s+(product|help|manual|feature|module|menu|toc|everything|entire|reports?|catalog|"
        r"inside|works?|workflow|lifecycle)|"
        r"(learn|what\s+is|how\s+(does|do|to)|tell\s+me\s+about|describe)\s+(the\s+)?softdent|"
        r"soft\s*dent\s+(charting|scheduling|treatment\s*plan|era|eclaim|e-?claim|"
        r"imaging|report\s*manager|audit\s*trail|trojan|kiosk|voice|practice\s+management|"
        r"daysheet|aging|register|claim|posting|transaction\s+code)|"
        r"(list|all)\s+(softdent\s+)?(reports|menus|modules|features)|"
        r"carestream\s+(softdent|help)|"
        r"thirteen\s+categor|"
        r"over\s+200\s+reports|"
        r"help\s*→\s*softdent|soft\s*dent\s+help|f1\s+softdent|"
        r"softdent\s+help\s+catalog|product\s+help\s+catalog|"
        r"inside\s+and\s+out"
        r")\b",
        q,
    ):
        return True
    if "softdent" in q and re.search(
        r"\b(charting|treatment plan|report manager|audit trail|trojan|"
        r"practice (summary|management)|receivables|capitation|ortho|lab case|"
        r"what (can|does) softdent|full (product|manual|catalog)|help catalog|"
        r"report(s)? (are|in|exist|available)|how .{0,20}work|"
        r"operatory|eclaim|era|end of day|post(ing)? transaction)\b",
        q,
    ):
        return True
    return False


def format_softdent_product_kb_brief() -> str:
    s = product_kb_summary()
    return (
        f"SoftDent product KB v{s.get('version')} ({s.get('built')}): "
        f"{s.get('tocEntryCount')} Help TOC topics, "
        f"{s.get('topicBodyCount')} Help topic bodies, "
        f"{s.get('reportCountParsed')} cataloged reports, "
        f"{s.get('moduleCount')} product modules, "
        f"{s.get('howItWorksArticleCount')} how-it-works core articles. "
        "Load via softdent_product_kb /api/apex/hal/softdent-kb."
    )


if __name__ == "__main__":
    import sys

    q = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "how does SoftDent work"
    print(format_softdent_product_kb_brief())
    print(format_softdent_product_kb_hal_reply(q))
