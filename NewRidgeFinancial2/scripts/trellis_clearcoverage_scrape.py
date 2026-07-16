"""DOM-scrape Vyne Trellis ClearCoverage eligibility benefits (no OCR).

Called from vyne_trellis_add_verify_batch after Verify status is known and before
closing the verification panel. Never invents $0 / 0% — missing values stay null.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

_MONEY = re.compile(
    r"\$?\s*([\d,]+(?:\.\d+)?)\s*/\s*\$?\s*([\d,]+(?:\.\d+)?)",
    re.I,
)
_PCT = re.compile(r"(\d{1,3})\s*%")
_ADA = re.compile(r"\b(D\d{4}[A-Z0-9]?)\b", re.I)
_DATE = re.compile(r"\b(\d{1,2}/\d{1,2}/\d{4})\b")
_CATS = ("preventive", "basic", "major", "ortho")
_CAT_LABELS = {
    "preventive": "Preventive",
    "basic": "Basic",
    "major": "Major",
    "ortho": "Ortho",
}


def parse_money_pair(text: str | None) -> tuple[float | None, float | None]:
    """Parse '$rem / $total' → (remaining, total). Not Provided / empty → (None, None)."""
    raw = (text or "").strip()
    if not raw or re.search(r"not\s+provided", raw, re.I):
        return None, None
    # Strip leading/trailing junk but keep slash pair
    m = _MONEY.search(raw.replace("\u00a0", " "))
    if not m:
        return None, None
    try:
        rem = float(m.group(1).replace(",", ""))
        tot = float(m.group(2).replace(",", ""))
    except ValueError:
        return None, None
    return rem, tot


def parse_pct(text: str | None) -> int | None:
    raw = (text or "").strip()
    if not raw or re.search(r"not\s+provided", raw, re.I):
        return None
    m = _PCT.search(raw)
    if not m:
        return None
    try:
        n = int(m.group(1))
    except ValueError:
        return None
    return n if 0 <= n <= 100 else None


def _empty_benefits(*, error: str | None = None) -> dict[str, Any]:
    return {
        "planName": None,
        "effectiveDate": None,
        "carrierId": None,
        "network": "In Network",
        "deductibleRemaining": None,
        "deductibleTotal": None,
        "annualMaxRemaining": None,
        "annualMaxTotal": None,
        "orthoRemaining": None,
        "planNotes": [],
        "categories": {k: [] for k in _CATS},
        "lastVerified": None,
        "transactionId": None,
        "scrapedAt": datetime.now(timezone.utc).isoformat(),
        "scrapeOk": False if error else True,
        "scrapeError": error,
    }


def _label_value(body: str, label: str) -> str | None:
    """Best-effort: Label\\nValue or Label: Value on same/next line."""
    pat = re.compile(
        rf"(?:^|\n)\s*{re.escape(label)}\s*(?::|\n)\s*([^\n]+)",
        re.I | re.M,
    )
    m = pat.search(body)
    if not m:
        return None
    val = m.group(1).strip()
    if not val or re.search(r"not\s+provided", val, re.I):
        return None
    if val.lower() in {label.lower(), "clearcoverage view", "carrier response"}:
        return None
    return val


def _money_after_label(body: str, label: str) -> tuple[float | None, float | None]:
    pat = re.compile(
        rf"{re.escape(label)}\s*(?:Remaining)?\s*[:\n]?\s*"
        rf"(\$?\s*[\d,]+\.?\d*\s*/\s*\$?\s*[\d,]+\.?\d*|Not\s+Provided)",
        re.I,
    )
    m = pat.search(body)
    if not m:
        return None, None
    return parse_money_pair(m.group(1))


def _click_if_visible(page, *names: str) -> bool:
    for name in names:
        loc = page.get_by_role("button", name=re.compile(rf"^{re.escape(name)}$", re.I))
        if loc.count() == 0:
            loc = page.get_by_text(re.compile(rf"^{re.escape(name)}$", re.I))
        try:
            if loc.count() and loc.first.is_visible():
                loc.first.click(force=True, timeout=3000)
                page.wait_for_timeout(400)
                return True
        except Exception:
            continue
    return False


def _ensure_clearcoverage_tab(page) -> None:
    tab = page.get_by_role("tab", name=re.compile(r"ClearCoverage", re.I))
    if tab.count() == 0:
        tab = page.get_by_text(re.compile(r"ClearCoverage\s*View", re.I))
    try:
        if tab.count() and tab.first.is_visible():
            tab.first.click(force=True, timeout=3000)
            page.wait_for_timeout(500)
    except Exception:
        pass


def _ensure_in_network(page) -> None:
    _click_if_visible(page, "In Network")


def _set_page_size_large(page) -> None:
    """Prefer showing all benefit rows (50/page if available)."""
    try:
        # Ant pagination size changer
        changer = page.locator(".ant-pagination-options-size-changer, .ant-select-selection-item")
        for el in changer.all()[:6]:
            txt = (el.inner_text() or "").strip()
            if "/page" in txt.lower() or re.match(r"^\d+$", txt):
                el.click(force=True)
                page.wait_for_timeout(200)
                opt = page.locator(
                    ".ant-select-dropdown:not(.ant-select-dropdown-hidden) "
                    ".ant-select-item-option-content"
                ).filter(has_text=re.compile(r"50|100|All", re.I))
                if opt.count():
                    opt.last.click(force=True)
                    page.wait_for_timeout(400)
                break
    except Exception:
        pass


def _expand_all_ada(page) -> None:
    """Click every visible 'ADA Codes' expander."""
    for _ in range(3):
        clicked = 0
        locs = page.get_by_text(re.compile(r"^\s*ADA\s*Codes\s*$", re.I))
        n = min(locs.count(), 80)
        for i in range(n):
            try:
                el = locs.nth(i)
                if not el.is_visible():
                    continue
                # Skip if already expanded (sibling already shows D#### nearby)
                parent = el.locator("xpath=ancestor::*[self::div or self::li or self::tr][1]")
                try:
                    parent.inner_text(timeout=500)
                except Exception:
                    pass
                el.click(force=True, timeout=2000)
                clicked += 1
                page.wait_for_timeout(150)
            except Exception:
                continue
        if clicked == 0:
            break
        page.wait_for_timeout(300)


def _field_after(lines: list[str], start: int, label: str, *, look_ahead: int = 8) -> str | None:
    lab = label.lower()
    end = min(len(lines), start + look_ahead)
    for j in range(start, end):
        if lines[j].lower() != lab:
            continue
        if j + 1 >= len(lines):
            return None
        val = lines[j + 1].strip()
        if not val or val.lower() in {
            "frequency",
            "age limit",
            "coinsurance",
            "ada codes",
            "not provided",
        }:
            return None
        return val
    return None


def _scrape_services_from_text(block: str) -> list[dict[str, Any]]:
    """Parse category benefit rows from ClearCoverage text after ADA expand.

    Expected pattern per service::
        Exams
        Frequency
        2 treatments per calendar year
        Age Limit
        Not Provided
        Coinsurance
        100%
        ADA Codes
        D0120 …
    """
    lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
    field_labels = {"frequency", "age limit", "coinsurance", "ada codes"}
    chrome = {
        "preventive",
        "basic",
        "major",
        "ortho",
        "in network",
        "out of network",
        "premier",
        "search by code or category",
        "clearcoverage view",
        "carrier response",
        "download",
        "print",
        "close",
        "eligibility & benefit response",
        "plan name",
        "effective date",
        "deductible remaining",
        "maximum remaining",
        "ortho remaining",
    }
    services: list[dict[str, Any]] = []
    i = 0
    while i < len(lines) - 1:
        line = lines[i]
        low = line.lower()
        if (
            low in field_labels
            or low in chrome
            or low.startswith("deductible")
            or low.startswith("maximum")
            or _ADA.fullmatch(line)
            or _PCT.fullmatch(line)
            or _DATE.fullmatch(line)
            or re.match(r"^\d+-\d+\s+of\s+\d+", low)
            or "/page" in low
        ):
            i += 1
            continue
        # Service name if "Frequency" appears within next few lines
        ahead = [x.lower() for x in lines[i + 1 : i + 6]]
        if "frequency" not in ahead:
            i += 1
            continue
        name = line
        freq = _field_after(lines, i + 1, "Frequency")
        age = _field_after(lines, i + 1, "Age Limit")
        coins_raw = _field_after(lines, i + 1, "Coinsurance")
        coins = parse_pct(coins_raw)
        # Collect ADA until next service (name + Frequency) or category chrome
        ada_codes: list[dict[str, Any]] = []
        seen: set[str] = set()
        j = i + 1
        while j < len(lines):
            lj = lines[j]
            lj_low = lj.lower()
            if lj_low in chrome:
                break
            nxt_ahead = [x.lower() for x in lines[j + 1 : j + 5]]
            if (
                j > i + 2
                and lj_low not in field_labels
                and "frequency" in nxt_ahead
                and not _ADA.search(lj)
            ):
                break
            for m in _ADA.finditer(lj):
                code = m.group(1).upper()
                if code in seen:
                    continue
                seen.add(code)
                pct = parse_pct(lj)
                entry: dict[str, Any] = {"code": code}
                if pct is not None:
                    entry["coinsurancePct"] = pct
                elif coins is not None:
                    entry["coinsurancePct"] = coins
                ada_codes.append(entry)
            j += 1
        services.append(
            {
                "name": name,
                "frequency": freq,
                "ageLimit": age,
                "coinsurancePct": coins,
                "adaCodes": ada_codes,
            }
        )
        i = max(j, i + 1)

    by_name: dict[str, dict[str, Any]] = {}
    for svc in services:
        key = str(svc.get("name") or "").strip().lower()
        if not key:
            continue
        prev = by_name.get(key)
        if not prev or len(svc.get("adaCodes") or []) >= len(prev.get("adaCodes") or []):
            by_name[key] = svc
    return list(by_name.values())


def _scrape_category(page, key: str) -> list[dict[str, Any]]:
    label = _CAT_LABELS[key]
    _click_if_visible(page, label)
    page.wait_for_timeout(500)
    _expand_all_ada(page)
    page.wait_for_timeout(400)
    # Prefer main content region text
    try:
        body = page.locator("body").inner_text(timeout=5000)
    except Exception:
        body = ""
    # Narrow to category section if markers exist
    start = re.search(rf"(?i)\b{re.escape(label)}\b", body)
    end = None
    if start:
        rest = body[start.start() :]
        # Cut at next major category button label if present later
        cut = len(rest)
        for other in _CAT_LABELS.values():
            if other.lower() == label.lower():
                continue
            m = re.search(rf"(?i)\n{re.escape(other)}\n", rest[len(label) + 5 :])
            if m:
                cut = min(cut, len(label) + 5 + m.start())
        block = rest[:cut]
    else:
        block = body
    return _scrape_services_from_text(block)


def _header_from_body(body: str) -> dict[str, Any]:
    plan = _label_value(body, "Plan Name")
    eff = _label_value(body, "Effective Date")
    if eff:
        dm = _DATE.search(eff)
        eff = dm.group(1) if dm else eff
    carrier_id = _label_value(body, "Carrier ID")
    last_v = _label_value(body, "Last Verified")
    if last_v:
        dm = _DATE.search(last_v)
        last_v = dm.group(1) if dm else last_v
    txn = _label_value(body, "Transaction ID")
    ded_r, ded_t = _money_after_label(body, "Deductible")
    if ded_r is None:
        ded_r, ded_t = _money_after_label(body, "Deductible Remaining")
    max_r, max_t = _money_after_label(body, "Maximum")
    if max_r is None:
        max_r, max_t = _money_after_label(body, "Maximum Remaining")
    ortho_raw = _label_value(body, "Ortho Remaining") or _label_value(body, "Ortho")
    ortho_r, _ = parse_money_pair(ortho_raw or "")
    notes: list[str] = []
    for note_label in ("Plan Notes", "Plan details", "Plan Details"):
        n = _label_value(body, note_label)
        if n:
            notes.append(n)
    if re.search(r"no waiting period", body, re.I):
        if not any("waiting" in x.lower() for x in notes):
            notes.append("No waiting period")
    return {
        "planName": plan,
        "effectiveDate": eff,
        "carrierId": carrier_id,
        "lastVerified": last_v,
        "transactionId": txn,
        "deductibleRemaining": ded_r,
        "deductibleTotal": ded_t,
        "annualMaxRemaining": max_r,
        "annualMaxTotal": max_t,
        "orthoRemaining": ortho_r,
        "planNotes": notes,
    }


def scrape_clearcoverage(page) -> dict[str, Any]:
    """Scrape ClearCoverage panel on the current Playwright page.

    Returns benefits dict (always). scrapeOk False on hard failure.
    """
    out = _empty_benefits()
    try:
        # Wait briefly for panel content
        for _ in range(40):
            body = page.locator("body").inner_text()
            if re.search(r"ClearCoverage|Deductible|Maximum Remaining|Eligible", body, re.I):
                break
            page.wait_for_timeout(250)
        else:
            return _empty_benefits(error="clearcoverage_panel_not_found")

        _ensure_clearcoverage_tab(page)
        _ensure_in_network(page)
        _set_page_size_large(page)
        page.wait_for_timeout(400)

        body = page.locator("body").inner_text()
        header = _header_from_body(body)
        out.update(header)
        out["network"] = "In Network"
        out["scrapedAt"] = datetime.now(timezone.utc).isoformat()

        categories: dict[str, list] = {}
        for key in _CATS:
            try:
                categories[key] = _scrape_category(page, key)
            except Exception as exc:  # noqa: BLE001
                categories[key] = []
                # Keep going; record soft error on last failure only if all empty later
                out["scrapeError"] = f"category_{key}:{exc}"[:200]
        out["categories"] = categories

        # Success if we got any money OR any service rows OR plan name
        has_money = any(
            out.get(k) is not None
            for k in (
                "deductibleRemaining",
                "deductibleTotal",
                "annualMaxRemaining",
                "annualMaxTotal",
            )
        )
        has_svc = any(categories.get(k) for k in _CATS)
        if has_money or has_svc or out.get("planName"):
            out["scrapeOk"] = True
            if has_money or has_svc:
                out["scrapeError"] = None
        else:
            out["scrapeOk"] = False
            out["scrapeError"] = out.get("scrapeError") or "no_benefits_fields_parsed"
        return out
    except Exception as exc:  # noqa: BLE001
        return _empty_benefits(error=f"exception:{exc}"[:240])
