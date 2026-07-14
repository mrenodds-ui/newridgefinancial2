"""Scan SoftDent PWImages for dental insurance EOB signals (text + inventory)."""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(r"C:\SoftDent\PWImages")
OUT = Path(__file__).resolve().parents[1] / "docs" / "_pwimages_eob_mine"

KEYWORD_RE = re.compile(
    rb"(?i)("
    rb"explanation of benefits|"
    rb"\beob\b|"
    rb"remittance advice|"
    rb"claim payment|"
    rb"amount paid|"
    rb"allowed amount|"
    rb"patient responsibility|"
    rb"delta dental|"
    rb"metlife|"
    rb"aetna|"
    rb"cigna|"
    rb"guardian|"
    rb"united concordia|"
    rb"geha|"
    rb"bcbs|"
    rb"blue cross|"
    rb"blue shield|"
    rb"humana dental|"
    rb"sun life|"
    rb"principal dental|"
    rb"unitedhealthcare|"
    rb"u\.?h\.?c\.?|"
    rb"dentaquest|"
    rb"payment advice|"
    rb"provider remittance|"
    rb"check number|"
    rb"claim number|"
    rb"subscriber id|"
    rb"group number"
    rb")"
)


def scan_text_file(p: Path, max_bytes: int = 200_000):
    data = p.read_bytes()[:max_bytes]
    m = re.search(rb"Content-Location:\s*([^\r\n]+)", data, re.I)
    loc = m.group(1).decode("latin-1", "replace") if m else ""
    fm = re.search(rb"/eForms/EForms/([^?\s\"']+)", data, re.I)
    form = fm.group(1).decode("latin-1", "replace") if fm else ""
    tm = re.search(rb"<title>([^<]{1,120})</title>", data, re.I)
    title = tm.group(1).decode("latin-1", "replace") if tm else ""
    hits = [h.decode("latin-1", "replace").lower() for h in KEYWORD_RE.findall(data)]
    return loc, form, title, hits, data


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    inventory = {
        "root": str(ROOT),
        "patient_category_folders": {},
        "extension_counts": {},
        "nonpatient": {},
    }

    # Inventory
    ext = Counter()
    for p in ROOT.rglob("*"):
        if p.is_file():
            ext[p.suffix.lower() or "(none)"] += 1
    inventory["extension_counts"] = dict(ext.most_common())

    cats = Counter()
    for bucket in (ROOT / "Patient").iterdir() if (ROOT / "Patient").is_dir() else []:
        if not bucket.is_dir():
            continue
        for pid in bucket.iterdir():
            if not pid.is_dir():
                continue
            for cat in pid.iterdir():
                if cat.is_dir():
                    n = sum(1 for f in cat.iterdir() if f.is_file())
                    cats[cat.name] += n
    inventory["patient_category_folders"] = dict(cats.most_common())
    inventory["nonpatient"] = {
        "account_jpgs": sum(1 for _ in (ROOT / "NonPatient" / "Account").rglob("*.JPG")),
        "claim_jpgs": sum(1 for _ in (ROOT / "NonPatient" / "Claim").rglob("*.JPG")),
    }

    # HTM scan (all)
    htm_forms = Counter()
    htm_eob = []
    for p in ROOT.rglob("*.HTM"):
        loc, form, title, hits, data = scan_text_file(p)
        key = form or title or "unknown"
        htm_forms[key] += 1
        if hits:
            htm_eob.append(
                {
                    "path": str(p),
                    "hits": sorted(set(hits))[:20],
                    "title": title,
                    "form": form,
                    "loc": loc[:200],
                }
            )

    # MHT sample (~2500)
    mhts = list(ROOT.rglob("*.mht"))
    step = max(1, len(mhts) // 2500)
    mht_forms = Counter()
    mht_eob = []
    sampled = mhts[::step]
    for p in sampled:
        loc, form, title, hits, data = scan_text_file(p, 80_000)
        plain = data[:5000].decode("latin-1", "replace")
        if "NOTICE OF PRIVACY" in plain:
            key = "PrivacyNotice"
        elif form:
            key = form
        elif "Consent" in loc:
            key = "Consent"
        else:
            key = title or "unknown"
        mht_forms[key] += 1
        if hits:
            mht_eob.append(
                {
                    "path": str(p),
                    "hits": sorted(set(hits))[:20],
                    "title": title,
                    "form": form,
                    "loc": loc[:200],
                }
            )

    # PDF name scan
    pdfs = []
    for p in ROOT.rglob("*.pdf"):
        name = p.name
        pdfs.append(
            {
                "path": str(p),
                "name": name,
                "size": p.stat().st_size,
                "eobish": bool(
                    re.search(
                        r"(?i)eob|insurance|benefit|remit|claim|delta|aetna|metlife|cigna",
                        name,
                    )
                ),
            }
        )

    result = {
        "inventory": inventory,
        "htm": {
            "count": sum(htm_forms.values()),
            "forms": htm_forms.most_common(40),
            "eob_keyword_hits": len(htm_eob),
            "eob_samples": htm_eob[:50],
        },
        "mht_sample": {
            "total_mht": len(mhts),
            "sampled": len(sampled),
            "step": step,
            "forms": mht_forms.most_common(40),
            "eob_keyword_hits": len(mht_eob),
            "eob_samples": mht_eob[:50],
        },
        "pdfs": {
            "count": len(pdfs),
            "eobish_names": [x for x in pdfs if x["eobish"]],
            "other_name_samples": [x for x in pdfs if not x["eobish"]][:30],
        },
        "likely_eob_lanes": {
            "note": (
                "SoftDent stores all patient docs under category 'Other'. "
                "MHTs are mostly Carestream eForms. Scanned EOBs typically live as "
                "JPGs under NonPatient/Account (account-level) and sometimes Patient JPGs / Claim JPGs."
            ),
            "account_jpgs": inventory["nonpatient"]["account_jpgs"],
            "claim_jpgs": inventory["nonpatient"]["claim_jpgs"],
            "patient_jpgs": inventory["extension_counts"].get(".jpg", 0),
        },
    }

    out_json = OUT / "pwimages_eob_scan.json"
    out_json.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("inventory", "likely_eob_lanes")}, indent=2))
    print("HTM forms:", htm_forms.most_common(15))
    print("HTM EOB hits:", len(htm_eob))
    print("MHT sample forms:", mht_forms.most_common(15))
    print("MHT EOB hits:", len(mht_eob), "/", len(sampled))
    print("PDFs eobish names:", len(result["pdfs"]["eobish_names"]), "/", len(pdfs))
    print("Wrote", out_json)


if __name__ == "__main__":
    main()
