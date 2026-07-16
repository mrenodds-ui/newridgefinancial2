"""Build printable Trellis ClearCoverage eligibility HTML report for a schedule date.

Usage:
  python NewRidgeFinancial2/scripts/build_trellis_eligibility_report.py --date 2026-07-16
  python NewRidgeFinancial2/scripts/build_trellis_eligibility_report.py --date 2026-07-16 --open

Reads:  app_data/nr2/vyne_pulls/tomorrow_trellis_verify_results_YYYY-MM-DD.json
Writes: app_data/nr2/vyne_pulls/trellis_eligibility_report_YYYY-MM-DD.html

Honest empties: missing money/% → em dash; never invent $0 / 0%.
Status-only rows (pre-scrape) show an awaiting-capture note.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import sys
import webbrowser
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "app_data" / "nr2" / "vyne_pulls"
CAT_ORDER = (
    ("preventive", "Preventive"),
    ("basic", "Basic"),
    ("major", "Major"),
    ("ortho", "Ortho"),
)


def _target_date(cli: str | None) -> str:
    raw = (cli or os.environ.get("NR2_TRELLIS_TARGET_DATE") or "").strip()
    if raw:
        return raw
    return (date.today() + timedelta(days=1)).isoformat()


def _esc(value: Any) -> str:
    if value is None:
        return ""
    return html.escape(str(value), quote=True)


def _dash(value: Any) -> str:
    if value is None or value == "":
        return "—"
    return _esc(value)


def _money(value: Any) -> str:
    if value is None or value == "":
        return "—"
    try:
        n = float(value)
    except (TypeError, ValueError):
        return _esc(value)
    if n == int(n):
        return f"${int(n):,}"
    return f"${n:,.2f}"


def _money_pair(rem: Any, tot: Any) -> str:
    if rem is None and tot is None:
        return "—"
    return f"{_money(rem)} / {_money(tot)}"


def _pct(value: Any) -> str:
    if value is None or value == "":
        return "—"
    try:
        return f"{int(value)}%"
    except (TypeError, ValueError):
        return _esc(value)


def _carrier(row: dict[str, Any]) -> str:
    return (
        row.get("softdent_carrier")
        or row.get("carrier_trellis")
        or row.get("carrier")
        or ""
    )


def _has_benefits(row: dict[str, Any]) -> bool:
    ben = row.get("benefits")
    if not isinstance(ben, dict):
        return False
    if ben.get("scrapeOk"):
        return True
    if any(
        ben.get(k) is not None
        for k in (
            "deductibleRemaining",
            "deductibleTotal",
            "annualMaxRemaining",
            "annualMaxTotal",
            "planName",
        )
    ):
        return True
    cats = ben.get("categories") or {}
    return any(cats.get(k) for k, _ in CAT_ORDER)


def _ada_cell(svc: dict[str, Any]) -> str:
    codes = svc.get("adaCodes") or []
    if not codes:
        return "—"
    parts = []
    for c in codes:
        code = c.get("code") or ""
        pct = c.get("coinsurancePct")
        if pct is None:
            parts.append(_esc(code))
        else:
            parts.append(f"{_esc(code)} ({_pct(pct)})")
    return ", ".join(parts)


def _category_tables(ben: dict[str, Any]) -> str:
    cats = ben.get("categories") or {}
    chunks: list[str] = []
    for key, title in CAT_ORDER:
        rows = cats.get(key) or []
        if not rows:
            chunks.append(
                f'<h4 class="cat">{_esc(title)}</h4>'
                f'<p class="muted">No services captured for this category.</p>'
            )
            continue
        body_rows = []
        for svc in rows:
            body_rows.append(
                "<tr>"
                f"<td>{_dash(svc.get('name'))}</td>"
                f"<td>{_dash(svc.get('frequency'))}</td>"
                f"<td>{_dash(svc.get('ageLimit'))}</td>"
                f"<td>{_pct(svc.get('coinsurancePct'))}</td>"
                f"<td class=\"ada\">{_ada_cell(svc)}</td>"
                "</tr>"
            )
        chunks.append(
            f'<h4 class="cat">{_esc(title)}</h4>'
            '<table class="svc"><thead><tr>'
            "<th>Service</th><th>Frequency</th><th>Age limit</th>"
            "<th>Coinsurance</th><th>ADA codes</th>"
            "</tr></thead><tbody>"
            + "".join(body_rows)
            + "</tbody></table>"
        )
    return "\n".join(chunks)


def _status_class(status: str) -> str:
    return "status-" + (status or "unknown").lower().replace(" ", "-")


def _patient_section(row: dict[str, Any], idx: int) -> str:
    name = row.get("patient_name") or f"Patient {idx}"
    status = row.get("status") or "Unknown"
    status_cls = _status_class(status)
    carrier = _carrier(row)
    plan = row.get("plan_name") or (row.get("benefits") or {}).get("planName")
    eff = row.get("effective_date") or (row.get("benefits") or {}).get("effectiveDate")
    cid = row.get("carrier_id") or (row.get("benefits") or {}).get("carrierId") or ""
    notes = row.get("notes") or ""
    sub_id = row.get("subscriber_id") or row.get("memberId")

    if not _has_benefits(row):
        notes_html = f'<p class="muted">{_esc(notes)}</p>' if notes else ""
        return (
            f'<section class="patient" id="p{idx}">'
            f"<h3>{idx}. {_esc(name)} "
            f'<span class="status {status_cls}">{_esc(status)}</span></h3>'
            f"<p><strong>Carrier:</strong> {_dash(carrier)} &nbsp; "
            f"<strong>Member/Sub ID:</strong> {_dash(sub_id)}</p>"
            '<p class="await">Benefits not captured — awaiting next ClearCoverage scrape.</p>'
            f"{notes_html}"
            "</section>"
        )

    ben = row.get("benefits") or {}
    plan_notes = ben.get("planNotes") or []
    if isinstance(plan_notes, str):
        plan_notes = [plan_notes]
    scrape_note = ""
    if ben.get("scrapeOk") is False and ben.get("scrapeError"):
        scrape_note = (
            f'<p class="warn">Scrape incomplete: {_esc(ben.get("scrapeError"))}</p>'
        )
    notes_block = ""
    if plan_notes:
        joined = "; ".join(str(x) for x in plan_notes)
        notes_block = f'<p class="notes"><strong>Plan notes:</strong> {_esc(joined)}</p>'

    return (
        f'<section class="patient" id="p{idx}">'
        f"<h3>{idx}. {_esc(name)} "
        f'<span class="status {status_cls}">{_esc(status)}</span></h3>'
        '<div class="meta">'
        f"<div><span>Carrier</span><strong>{_dash(carrier)}</strong></div>"
        f"<div><span>Carrier ID</span><strong>{_dash(cid)}</strong></div>"
        f"<div><span>Plan</span><strong>{_dash(plan)}</strong></div>"
        f"<div><span>Effective</span><strong>{_dash(eff)}</strong></div>"
        f"<div><span>Network</span><strong>{_dash(ben.get('network') or 'In Network')}</strong></div>"
        f"<div><span>Subscriber ID</span><strong>{_dash(sub_id)}</strong></div>"
        f"<div><span>Deductible rem/total</span><strong>"
        f"{_money_pair(ben.get('deductibleRemaining'), ben.get('deductibleTotal'))}"
        "</strong></div>"
        f"<div><span>Annual max rem/total</span><strong>"
        f"{_money_pair(ben.get('annualMaxRemaining'), ben.get('annualMaxTotal'))}"
        "</strong></div>"
        f"<div><span>Ortho remaining</span><strong>"
        f"{_money(ben.get('orthoRemaining'))}</strong></div>"
        "</div>"
        + notes_block
        + scrape_note
        + _category_tables(ben)
        + "</section>"
    )


def build_report_html(data: dict[str, Any], *, schedule_date: str) -> str:
    results = list(data.get("results") or [])
    by_status = Counter(str(r.get("status") or "Unknown") for r in results)
    with_ben = sum(1 for r in results if _has_benefits(r))
    scrape_fail = sum(
        1
        for r in results
        if isinstance(r.get("benefits"), dict)
        and r["benefits"].get("scrapeOk") is False
    )
    stamped = datetime.now().strftime("%Y-%m-%d %I:%M %p")
    status_bits = ", ".join(f"{k}: {v}" for k, v in sorted(by_status.items()))

    cover = (
        '<section class="cover">'
        "<h1>Trellis ClearCoverage Eligibility Report</h1>"
        f"<p class=\"lede\">Schedule date <strong>{_esc(schedule_date)}</strong> · "
        f"Generated {_esc(stamped)}</p>"
        '<ul class="counts">'
        f"<li><strong>{len(results)}</strong> patients on verify list</li>"
        f"<li><strong>{by_status.get('Eligible', 0)}</strong> Eligible</li>"
        f"<li><strong>{with_ben}</strong> with ClearCoverage benefits captured</li>"
        f"<li><strong>{len(results) - with_ben}</strong> status-only "
        "(awaiting benefits scrape)</li>"
        f"<li><strong>{scrape_fail}</strong> scrape failures / incomplete</li>"
        "</ul>"
        f'<p class="muted">Status mix: {_esc(status_bits) or "—"}</p>'
        '<p class="muted">Source: tomorrow_trellis_verify_results_'
        f"{_esc(schedule_date)}.json · Missing values shown as — (never invented $0).</p>"
        "</section>"
    )

    body = "\n".join(_patient_section(r, i) for i, r in enumerate(results, 1))
    if not results:
        body = '<p class="await">No verify results for this date.</p>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>Trellis Eligibility Report {_esc(schedule_date)}</title>
<style>
  :root {{
    --ink: #1a1f24;
    --muted: #5c6670;
    --line: #d5dbe3;
    --bg: #f7f5f1;
    --paper: #fff;
    --accent: #0b5f6b;
    --ok: #1b6b3a;
    --warn: #8a5a00;
    --bad: #8b1e1e;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    font: 12.5px/1.45 "Segoe UI", system-ui, sans-serif;
    color: var(--ink);
    background: var(--bg);
  }}
  main {{ max-width: 960px; margin: 0 auto; padding: 24px 20px 48px; }}
  h1 {{ font-size: 22px; margin: 0 0 6px; color: var(--accent); }}
  h3 {{ font-size: 15px; margin: 0 0 10px; }}
  h4.cat {{
    margin: 16px 0 6px;
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--accent);
  }}
  .cover, .patient {{
    background: var(--paper);
    border: 1px solid var(--line);
    border-radius: 6px;
    padding: 18px 20px;
    margin-bottom: 16px;
  }}
  .lede {{ margin: 0 0 12px; color: var(--muted); }}
  .counts {{ margin: 0; padding-left: 18px; }}
  .counts li {{ margin: 2px 0; }}
  .muted {{ color: var(--muted); font-size: 11.5px; }}
  .await {{
    background: #f0f4f6;
    border-left: 3px solid var(--accent);
    padding: 8px 10px;
    margin: 8px 0 0;
  }}
  .warn {{ color: var(--warn); }}
  .meta {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
    gap: 8px 14px;
    margin-bottom: 8px;
  }}
  .meta span {{ display: block; font-size: 10.5px; color: var(--muted); }}
  .meta strong {{ font-weight: 600; }}
  .status {{
    display: inline-block;
    font-size: 11px;
    font-weight: 600;
    padding: 2px 8px;
    border-radius: 999px;
    background: #e8eef0;
    color: var(--ink);
    vertical-align: middle;
  }}
  .status-eligible {{ background: #e4f5ea; color: var(--ok); }}
  .status-failed, .status-not-eligible {{ background: #f8e6e6; color: var(--bad); }}
  .status-insurance-info-issue, .status-info-needed, .status-unknown {{
    background: #fff3d9; color: var(--warn);
  }}
  table.svc {{
    width: 100%;
    border-collapse: collapse;
    font-size: 11.5px;
  }}
  table.svc th, table.svc td {{
    border: 1px solid var(--line);
    padding: 5px 7px;
    text-align: left;
    vertical-align: top;
  }}
  table.svc th {{ background: #eef3f5; font-weight: 600; }}
  td.ada {{ font-family: Consolas, "Courier New", monospace; font-size: 11px; }}
  @media print {{
    body {{ background: #fff; }}
    main {{ max-width: none; padding: 0; }}
    .cover, .patient {{
      break-inside: avoid;
      border-color: #bbb;
      box-shadow: none;
    }}
    .patient {{ page-break-inside: avoid; }}
  }}
</style>
</head>
<body>
<main>
{cover}
{body}
</main>
</body>
</html>
"""


def build_report_for_date(schedule_date: str) -> dict[str, Any]:
    src = OUT_DIR / f"tomorrow_trellis_verify_results_{schedule_date}.json"
    if not src.is_file():
        return {"ok": False, "error": "missing_results", "path": str(src)}
    data = json.loads(src.read_text(encoding="utf-8"))
    html_doc = build_report_html(data, schedule_date=schedule_date)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"trellis_eligibility_report_{schedule_date}.html"
    out.write_text(html_doc, encoding="utf-8")
    return {
        "ok": True,
        "date": schedule_date,
        "source": str(src),
        "path": str(out),
        "patients": len(data.get("results") or []),
        "withBenefits": sum(1 for r in (data.get("results") or []) if _has_benefits(r)),
        "generatedAt": datetime.now(timezone.utc).isoformat(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Trellis ClearCoverage HTML report")
    parser.add_argument("--date", help="Schedule date YYYY-MM-DD (default: tomorrow / env)")
    parser.add_argument("--open", action="store_true", help="Open report in default browser")
    parser.add_argument("--print", dest="do_print", action="store_true", help="Open then print")
    args = parser.parse_args()
    schedule = _target_date(args.date)
    result = build_report_for_date(schedule)
    print(json.dumps(result, indent=2))
    if not result.get("ok"):
        return 1
    path = Path(result["path"])
    if args.open or args.do_print:
        webbrowser.open(path.as_uri())
        if args.do_print:
            # Best-effort: Windows print via default association
            try:
                os.startfile(str(path), "print")  # type: ignore[attr-defined]
            except Exception as exc:  # noqa: BLE001
                print("print_failed", exc, file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
