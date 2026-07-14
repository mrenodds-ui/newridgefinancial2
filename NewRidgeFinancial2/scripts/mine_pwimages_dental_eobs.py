"""Mine SoftDent PWImages for dental insurance EOBs and related docs.

Primary lane: NonPatient/Account + NonPatient/Claim JPGs (scanned insurance mail).
Also classifies Patient *.HTM portal dumps (mostly eligibility/benefits, not remittance EOBs).

Outputs under NewRidgeFinancial2/docs/_pwimages_eob_mine/
"""
from __future__ import annotations

import csv
import json
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(r"C:\SoftDent\PWImages")
OUT = Path(__file__).resolve().parents[1] / "docs" / "_pwimages_eob_mine"
TESS = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
WORKERS = max(2, min(8, (os.cpu_count() or 4)))

# Strict remittance / claim-payment EOB
REMIT_RE = re.compile(
    r"(?i)("
    r"explanation of (?:benefits|dental payment|payment)|"
    r"\beob\b|"
    r"remittance advice|"
    r"provider remittance|"
    r"claim payment|"
    r"payment advice|"
    r"direct deposit advice|"
    r"this is not\s*a\s*bill|"
    r"total paid|"
    r"amount paid|"
    r"paid amount|"
    r"allowed amount|"
    r"provider payment|"
    r"check (?:number|#|no\.?)|"
    r"eft (?:number|#|trace)|"
    r"trace (?:number|amount)|"
    r"payment date|"
    r"claim (?:number|details)|"
    r"patient (?:pays|responsibility|owes)|"
    r"subscriber responsibility|"
    r"contractual (?:obligation|adjustment)|"
    r"write[- ]?off|"
    r"not covered|"
    r"deductible applied|"
    r"coinsurance"
    r")"
)

ELIG_RE = re.compile(
    r"(?i)\b("
    r"eligibility|"
    r"member benefit|"
    r"benefit and eligibility|"
    r"summary of benefits|"
    r"confirmation of (?:dental )?benefits|"
    r"active coverage|"
    r"plan frequency|"
    r"remaining (?:balances|maximum|deductible)|"
    r"coverage level|"
    r"co-insurance|"
    r"calendar year (?:maximum|deductible)|"
    r"group (?:#|number|id)|"
    r"subscriber id"
    r")\b"
)

CARD_RE = re.compile(
    r"(?i)\b("
    r"member id|"
    r"customer id|"
    r"rx bin|"
    r"group no|"
    r"dental ppo|"
    r"present this card|"
    r"insurance card|"
    r"id card"
    r")\b"
)

CLAIM_FORM_RE = re.compile(
    r"(?i)\b("
    r"dental claim form|"
    r"statement of actual services|"
    r"ada american dental|"
    r"billing dentist|"
    r"treating dentist|"
    r"account transactions"
    r")\b"
)

CARRIER_RE = re.compile(
    r"(?i)\b("
    r"delta dental|"
    r"aetna|"
    r"cigna|"
    r"metlife|"
    r"guardian|"
    r"humana|"
    r"geha|"
    r"united\s*concordia|"
    r"unitedhealthcare|u\.?h\.?c\.?|"
    r"blue cross|blue shield|bcbs|"
    r"sun life|"
    r"principal|"
    r"dentaquest|"
    r"libertydental|"
    r"ameritas|"
    r"lincoln financial|"
    r"assurant|"
    r"renaissance|"
    r"ddks|ddks1"
    r")\b"
)


@dataclass
class Hit:
    path: str
    lane: str
    account_or_claim_id: str
    category: str
    confidence: float
    carriers: list[str]
    markers: list[str]
    ocr_preview: str
    size: int
    mtime: str


def ocr_image(path: Path, timeout: int = 60) -> str:
    if not TESS.is_file():
        raise FileNotFoundError(f"tesseract missing: {TESS}")
    # stdout OCR, quiet
    proc = subprocess.run(
        [str(TESS), str(path), "stdout", "--psm", "6"],
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    text = (proc.stdout or b"").decode("utf-8", "replace")
    if not text.strip() and proc.returncode != 0:
        err = (proc.stderr or b"").decode("utf-8", "replace")[:200]
        return f"[ocr_error:{proc.returncode}] {err}"
    return text


def classify_text(text: str) -> tuple[str, float, list[str], list[str]]:
    rem = sorted({m.lower() for m in REMIT_RE.findall(text)})
    elig = sorted({m.lower() for m in ELIG_RE.findall(text)})
    card = sorted({m.lower() for m in CARD_RE.findall(text)})
    claim = sorted({m.lower() for m in CLAIM_FORM_RE.findall(text)})
    carriers = sorted({m.lower() for m in CARRIER_RE.findall(text)})

    blob = " ".join(rem).lower()
    text_l = text.lower()
    # Prefer remittance when strong EOB phrases present (incl. OCR spacing quirks)
    strong_remit = bool(
        re.search(
            r"(?i)(explanation of (?:benefits|dental payment|payment)|"
            r"remittance advice|provider remittance|claim payment|"
            r"payment advice|direct deposit advice|this is not\s*a\s*bill|\beob\b)",
            text_l,
        )
    ) or any(
        x in blob
        for x in (
            "explanation of benefits",
            "explanation of dental payment",
            "explanation of payment",
            "eob",
            "remittance advice",
            "provider remittance",
            "claim payment",
            "payment advice",
            "direct deposit advice",
            "this is not a bill",
        )
    )
    money_keys = (
        "amount paid",
        "paid amount",
        "total paid",
        "allowed amount",
        "patient pays",
        "patient responsibility",
        "patient owes",
        "check number",
        "check #",
        "check no.",
        "eft number",
        "eft #",
        "eft trace",
        "trace number",
        "trace amount",
        "payment date",
        "claim number",
        "claim details",
        "coinsurance",
        "deductible applied",
        "contractual obligation",
        "contractual adjustment",
        "write-off",
        "write off",
        "not covered",
        "provider payment",
        "subscriber responsibility",
    )
    money_remit = sum(1 for x in money_keys if x in text_l or x in blob)

    if strong_remit or money_remit >= 3:
        markers = rem[:20]
        conf = 0.95 if strong_remit else min(0.9, 0.55 + 0.1 * money_remit)
        return "REMITTANCE_EOB", conf, carriers, markers
    if claim:
        return "CLAIM_OR_LEDGER", 0.85, carriers, claim[:20]
    if elig and (carriers or len(elig) >= 2):
        return "ELIGIBILITY_BENEFITS", 0.88, carriers, elig[:20]
    if card and carriers:
        return "INSURANCE_CARD", 0.8, carriers, card[:20]
    if carriers and money_remit >= 1:
        return "REMITTANCE_EOB_CANDIDATE", 0.65, carriers, rem[:20]
    if carriers or elig or rem:
        return "INSURANCE_RELATED", 0.5, carriers, (rem + elig + card)[:20]
    return "OTHER", 0.2, carriers, []


def parse_id_from_path(path: Path) -> tuple[str, str]:
    name = path.name
    m = re.match(r"SD(Account|Claim|Patient)Doc_(\d+)_", name, re.I)
    if m:
        kind = m.group(1).lower()
        return kind, m.group(2)
    parts = path.parts
    if "Account" in parts:
        return "account", path.parent.name
    if "Claim" in parts:
        return "claim", path.parent.name
    return "patient", path.parent.parent.name if path.parent.name == "Other" else path.parent.name


def process_image(path: Path) -> Hit:
    kind, oid = parse_id_from_path(path)
    lane = "account" if "Account" in path.parts else ("claim" if "Claim" in path.parts else "patient")
    text = ocr_image(path)
    cat, conf, carriers, markers = classify_text(text)
    st = path.stat()
    preview = re.sub(r"\s+", " ", text).strip()[:400]
    return Hit(
        path=str(path),
        lane=lane,
        account_or_claim_id=oid,
        category=cat,
        confidence=round(conf, 3),
        carriers=carriers,
        markers=markers,
        ocr_preview=preview,
        size=st.st_size,
        mtime=datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat(),
    )


def classify_htm(path: Path) -> Hit:
    raw = path.read_bytes().decode("latin-1", "replace")
    plain = re.sub(r"<script[\s\S]*?</script>", " ", raw, flags=re.I)
    plain = re.sub(r"<style[\s\S]*?</style>", " ", plain, flags=re.I)
    plain = re.sub(r"<[^>]+>", " ", plain)
    plain = re.sub(r"&\w+;", " ", plain)
    plain = re.sub(r"\s+", " ", plain)
    cat, conf, carriers, markers = classify_text(plain)
    # Portal dumps titled Eligibility Benefits are not remittance EOBs
    if re.search(r"(?i)eligibility\s+benefits", plain[:500]) and cat.startswith("REMIT"):
        cat, conf = "ELIGIBILITY_BENEFITS", 0.9
    kind, oid = parse_id_from_path(path)
    st = path.stat()
    return Hit(
        path=str(path),
        lane="patient_htm",
        account_or_claim_id=oid,
        category=cat,
        confidence=round(conf, 3),
        carriers=carriers,
        markers=markers,
        ocr_preview=plain[:400],
        size=st.st_size,
        mtime=datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat(),
    )


def write_outputs(hits: list[Hit]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    rows = [asdict(h) for h in hits]

    by_cat: dict[str, int] = {}
    for h in hits:
        by_cat[h.category] = by_cat.get(h.category, 0) + 1

    summary = {
        "generatedAt": stamp,
        "root": str(ROOT),
        "tesseract": str(TESS),
        "countsByCategory": dict(sorted(by_cat.items(), key=lambda kv: (-kv[1], kv[0]))),
        "remittanceEobs": sum(1 for h in hits if h.category == "REMITTANCE_EOB"),
        "remittanceCandidates": sum(1 for h in hits if h.category == "REMITTANCE_EOB_CANDIDATE"),
        "eligibilityBenefits": sum(1 for h in hits if h.category == "ELIGIBILITY_BENEFITS"),
        "totalClassified": len(hits),
        "note": (
            "REMITTANCE_EOB = claim payment / provider remittance EOB. "
            "ELIGIBILITY_BENEFITS = portal/fax benefit summaries (often mislabeled 'EOB' in offices). "
            "Patient MHTs are Carestream eForms (consent/history) and were excluded from OCR."
        ),
    }

    (OUT / "eob_mine_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (OUT / "eob_mine_all.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")

    csv_path = OUT / "eob_mine_all.csv"
    fields = [
        "category",
        "confidence",
        "lane",
        "account_or_claim_id",
        "carriers",
        "markers",
        "path",
        "size",
        "mtime",
        "ocr_preview",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow(
                {
                    **{k: r.get(k) for k in fields if k not in ("carriers", "markers")},
                    "carriers": "|".join(r.get("carriers") or []),
                    "markers": "|".join(r.get("markers") or []),
                }
            )

    # Copy remittance EOBs (+ candidates) into a folder for review
    eob_dir = OUT / "remittance_eobs"
    eob_dir.mkdir(exist_ok=True)
    copied = 0
    for h in hits:
        if h.category not in ("REMITTANCE_EOB", "REMITTANCE_EOB_CANDIDATE"):
            continue
        src = Path(h.path)
        if not src.is_file():
            continue
        dest = eob_dir / f"{h.account_or_claim_id}__{src.name}"
        try:
            if not dest.exists():
                dest.write_bytes(src.read_bytes())
            copied += 1
        except OSError:
            pass
    summary["copiedTo"] = str(eob_dir)
    summary["copiedCount"] = copied
    (OUT / "eob_mine_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    # Remittance-only CSV
    remit_csv = OUT / "remittance_eobs.csv"
    with remit_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            if r["category"] not in ("REMITTANCE_EOB", "REMITTANCE_EOB_CANDIDATE"):
                continue
            w.writerow(
                {
                    **{k: r.get(k) for k in fields if k not in ("carriers", "markers")},
                    "carriers": "|".join(r.get("carriers") or []),
                    "markers": "|".join(r.get("markers") or []),
                }
            )

    print(json.dumps(summary, indent=2))


def main() -> int:
    if not TESS.is_file():
        print("Tesseract not found", file=sys.stderr)
        return 2
    OUT.mkdir(parents=True, exist_ok=True)

    images: list[Path] = []
    images.extend((ROOT / "NonPatient" / "Account").rglob("*.JPG"))
    images.extend((ROOT / "NonPatient" / "Account").rglob("*.jpg"))
    images.extend((ROOT / "NonPatient" / "Claim").rglob("*.JPG"))
    images.extend((ROOT / "NonPatient" / "Claim").rglob("*.jpg"))
    # de-dupe
    images = sorted({p.resolve() for p in images if p.is_file()})

    htms = sorted({p.resolve() for p in ROOT.rglob("*.HTM") if p.is_file()})

    print(f"OCR images: {len(images)}  HTM: {len(htms)}  workers={WORKERS}", flush=True)

    hits: list[Hit] = []
    # HTM first (fast)
    for i, p in enumerate(htms, 1):
        try:
            hits.append(classify_htm(p))
        except Exception as exc:  # noqa: BLE001
            hits.append(
                Hit(
                    path=str(p),
                    lane="patient_htm",
                    account_or_claim_id="",
                    category="ERROR",
                    confidence=0.0,
                    carriers=[],
                    markers=[str(exc)[:120]],
                    ocr_preview="",
                    size=0,
                    mtime="",
                )
            )
        if i % 200 == 0:
            print(f"  HTM {i}/{len(htms)}", flush=True)

    done = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(process_image, p): p for p in images}
        for fut in as_completed(futs):
            done += 1
            try:
                hits.append(fut.result())
            except Exception as exc:  # noqa: BLE001
                p = futs[fut]
                hits.append(
                    Hit(
                        path=str(p),
                        lane="account",
                        account_or_claim_id="",
                        category="ERROR",
                        confidence=0.0,
                        carriers=[],
                        markers=[str(exc)[:120]],
                        ocr_preview="",
                        size=0,
                        mtime="",
                    )
                )
            if done % 50 == 0 or done == len(images):
                print(f"  OCR {done}/{len(images)}", flush=True)
                # checkpoint
                write_outputs(hits)

    write_outputs(hits)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
