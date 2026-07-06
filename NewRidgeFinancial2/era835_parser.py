"""ERA/835 parse and fuzzy claim matching — Moonshot Phase 9."""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any


def _parse_money(value: Any) -> float:
    raw = str(value or "").replace("$", "").replace(",", "").strip()
    try:
        return float(raw) if raw else 0.0
    except ValueError:
        return 0.0


def parse_835_text(content: str) -> dict[str, Any]:
    """Parse X12 835 or plain-text ERA extract into payment segments."""
    text = str(content or "")
    segments: list[dict[str, Any]] = []
    if "~" in text or text.startswith("ISA"):
        parts = [p.strip() for p in re.split(r"~|\n", text) if p.strip()]
        current: dict[str, Any] = {}
        for part in parts:
            if part.startswith("CLP"):
                if current:
                    segments.append(current)
                fields = part.split("*")
                current = {
                    "claimId": fields[1] if len(fields) > 1 else "",
                    "status": fields[2] if len(fields) > 2 else "",
                    "charged": _parse_money(fields[3] if len(fields) > 3 else 0),
                    "paid": _parse_money(fields[4] if len(fields) > 4 else 0),
                    "patientName": "",
                    "serviceDate": "",
                }
            elif part.startswith("NM1") and current:
                fields = part.split("*")
                if len(fields) > 3 and fields[1] == "QC":
                    current["patientName"] = " ".join(fields[3:5]).strip()
            elif part.startswith("DTM") and current:
                fields = part.split("*")
                if len(fields) > 2 and fields[1] == "472":
                    current["serviceDate"] = fields[2]
        if current:
            segments.append(current)
    else:
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            m_amt = re.search(r"(?:paid|payment|amount)[:\s]+\$?([\d,.]+)", line, re.I)
            m_clm = re.search(r"(?:claim|clm)[#:\s]+([A-Z0-9-]+)", line, re.I)
            m_pat = re.search(r"(?:patient|member)[:\s]+(.+?)(?:\||$)", line, re.I)
            m_dt = re.search(r"(\d{4}[-/]?\d{2}[-/]?\d{2})", line)
            if m_amt or m_clm:
                segments.append(
                    {
                        "claimId": m_clm.group(1) if m_clm else "",
                        "paid": _parse_money(m_amt.group(1) if m_amt else 0),
                        "patientName": m_pat.group(1).strip() if m_pat else "",
                        "serviceDate": m_dt.group(1) if m_dt else "",
                        "status": "paid",
                        "charged": 0.0,
                    }
                )
    return {"ok": True, "segments": segments, "count": len(segments)}


def _name_score(a: str, b: str) -> float:
    a_norm = re.sub(r"\s+", " ", str(a or "").lower()).strip()
    b_norm = re.sub(r"\s+", " ", str(b or "").lower()).strip()
    if not a_norm or not b_norm:
        return 0.0
    return SequenceMatcher(None, a_norm, b_norm).ratio()


def fuzzy_match_claims(
    segments: list[dict[str, Any]],
    claim_rows: list[dict[str, Any]],
    *,
    min_confidence: float = 0.55,
) -> list[dict[str, Any]]:
    """Match ERA segments to open claim rows with confidence scoring."""
    matches: list[dict[str, Any]] = []
    for seg in segments:
        seg_claim = str(seg.get("claimId") or "").strip()
        seg_patient = str(seg.get("patientName") or "")
        seg_paid = _parse_money(seg.get("paid"))
        best: dict[str, Any] | None = None
        best_score = 0.0
        for row in claim_rows:
            row_claim = str(row.get("Claim") or row.get("claim") or row.get("ClaimId") or row.get("id") or "")
            row_patient = str(row.get("Patient") or row.get("patient") or row.get("Name") or "")
            row_amt = _parse_money(row.get("Amount") or row.get("Balance") or row.get("Paid"))
            score = 0.0
            if seg_claim and row_claim and seg_claim.upper() == row_claim.upper():
                score = 0.98
            else:
                name_s = _name_score(seg_patient, row_patient)
                amt_s = 1.0 if seg_paid and row_amt and abs(seg_paid - row_amt) < 0.02 else 0.0
                if seg_paid and row_amt and abs(seg_paid - row_amt) / max(seg_paid, row_amt, 1) < 0.05:
                    amt_s = 0.85
                score = max(name_s * 0.6 + amt_s * 0.4, name_s, amt_s)
            if score > best_score:
                best_score = score
                best = {
                    "claimId": row_claim,
                    "patientName": row_patient,
                    "confidence": round(best_score, 3),
                    "paidAmount": seg_paid,
                    "segment": seg,
                }
        if best and best_score >= min_confidence:
            best["confidence"] = round(best_score, 3)
            matches.append(best)
        else:
            matches.append(
                {
                    "claimId": "",
                    "confidence": round(best_score, 3) if best else 0.0,
                    "paidAmount": seg_paid,
                    "segment": seg,
                    "status": "review",
                }
            )
    return matches
