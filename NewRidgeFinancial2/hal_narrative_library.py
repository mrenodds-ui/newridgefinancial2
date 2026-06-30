"""100 generic insurance narrative drafts (MemoAI / hal_knowledge guided) + claim matching."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
MEMOAI_MEMORIES_PATH = REPO_ROOT / "docs" / "hal_knowledge" / "memories.jsonl"

FOCUSES = (
    "Medical Necessity",
    "Denial Appeal",
    "Prior Authorization",
    "Fracture Documentation",
    "Recurrent Decay",
    "Periodontal Medical Necessity",
    "Post-Operative Complication",
    "Replacement Restoration",
    "Accident or Trauma",
    "Alternate Benefit Dispute",
)
TONES = ("Professional", "Clinical-Detailed", "Concise", "Payer-Focused", "ADA-Reference")
LENGTHS = ("Standard", "Brief")

PROCEDURE_TAGS: dict[str, tuple[str, ...]] = {
    "Medical Necessity": ("crown", "build-up", "core", "onlay", "inlay", "restoration"),
    "Denial Appeal": ("crown", "build-up", "denied", "appeal"),
    "Prior Authorization": ("srp", "scaling", "periodontal", "implant", "surgery"),
    "Fracture Documentation": ("crown", "fracture", "crack", "build-up", "core"),
    "Recurrent Decay": ("crown", "decay", "restoration", "filling"),
    "Periodontal Medical Necessity": ("srp", "scaling", "root planing", "periodontal", "quadrant"),
    "Post-Operative Complication": ("extraction", "infection", "complication", "post-op"),
    "Replacement Restoration": ("crown", "bridge", "replacement", "failed"),
    "Accident or Trauma": ("trauma", "accident", "fracture", "emergency"),
    "Alternate Benefit Dispute": ("alternate", "downgrade", "benefit", "allowance"),
}

DENIAL_TAGS: dict[str, tuple[str, ...]] = {
    "Medical Necessity": ("medical necessity", "not necessary", "insufficient"),
    "Denial Appeal": ("denied", "denial", "appeal", "reconsideration"),
    "Prior Authorization": ("prior auth", "authorization", "pre-auth"),
    "Fracture Documentation": ("fracture", "documentation", "radiograph", "x-ray", "photo"),
    "Recurrent Decay": ("decay", "recurrent", "secondary"),
    "Periodontal Medical Necessity": ("periodontal", "srp", "gum", "bone loss"),
    "Post-Operative Complication": ("complication", "infection", "pain"),
    "Replacement Restoration": ("replacement", "failed", "defective"),
    "Accident or Trauma": ("trauma", "accident", "injury"),
    "Alternate Benefit Dispute": ("alternate", "downgrade", "amalgam", "composite"),
}


def _load_memoai_insurance_memories() -> list[dict[str, str]]:
    if not MEMOAI_MEMORIES_PATH.is_file():
        return []
    rows: list[dict[str, str]] = []
    for line in MEMOAI_MEMORIES_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(item, dict):
            continue
        category = str(item.get("category") or "")
        if category in {"insurance_narratives", "safety_policy", "softdent_exports"}:
            rows.append(
                {
                    "id": str(item.get("id") or ""),
                    "category": category,
                    "text": str(item.get("text") or ""),
                }
            )
    return rows


def _lead_for(focus: str, tone: str, length: str) -> str:
    if length == "Brief":
        return f"Clinical summary ({focus.lower()}, {tone.lower()} tone):"
    if tone == "Payer-Focused":
        return f"This letter supports claim review for {focus.lower()} using documented clinical findings only."
    if tone == "ADA-Reference":
        return f"Per accepted dental standards of care, the following supports {focus.lower()} for the billed service date."
    return f"The following documents {focus.lower()} for the proposed treatment based on examination and supporting records."


def _body_for(focus: str, tone: str, length: str) -> str:
    detail = (
        "Examination revealed findings consistent with the billed procedure, including structural compromise "
        "and functional impairment that cannot be managed with a more conservative restoration."
    )
    if length == "Brief":
        detail = "Examination supports the billed procedure; conservative options were insufficient."
    if focus == "Denial Appeal":
        detail = (
            "The original determination did not account for fracture/recurrent decay documentation and functional "
            "risk if the tooth were left untreated. Attached records reflect the clinical basis for full coverage."
        )
    if focus == "Fracture Documentation":
        detail = (
            "Clinical and radiographic evaluation demonstrates fracture or crack propagation with loss of "
            "tooth integrity. A full-coverage restoration is required to protect the remaining structure."
        )
    if focus == "Periodontal Medical Necessity":
        detail = (
            "Periodontal charting and radiographs show localized disease activity with attachment loss. "
            "Scaling and root planing is medically necessary to arrest progression and reduce systemic risk."
        )
    if tone == "Clinical-Detailed":
        detail += " Findings were recorded in the clinical chart and correlate with the submitted claim line."
    return detail


def _closing_for(length: str) -> str:
    if length == "Brief":
        return "Staff review required before any payer submission. Local draft only — not submitted."
    return (
        "Based on the above, the proposed procedure is appropriate, medically necessary, and consistent with "
        "accepted standards of care. This draft is for human review only and has not been submitted to any payer."
    )


def build_generic_draft_library() -> list[dict[str, Any]]:
    """Return exactly 100 generic narrative drafts informed by MemoAI knowledge boundaries."""
    memories = _load_memoai_insurance_memories()
    memory_ids = [m["id"] for m in memories if m.get("id")]
    library: list[dict[str, Any]] = []
    idx = 0
    for focus in FOCUSES:
        for tone in TONES:
            for length in LENGTHS:
                idx += 1
                library.append(
                    {
                        "id": f"nar-{idx:03d}",
                        "focus": focus,
                        "tone": tone,
                        "length": length,
                        "procedureTags": list(PROCEDURE_TAGS.get(focus, ())),
                        "denialTags": list(DENIAL_TAGS.get(focus, ())),
                        "memoAiSources": memory_ids[:4],
                        "text": " ".join(
                            [
                                _lead_for(focus, tone, length),
                                _body_for(focus, tone, length),
                                _closing_for(length),
                            ]
                        ),
                        "localOnly": True,
                        "submissionStatus": "not_submitted",
                    }
                )
    return library


def _norm(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _claim_field(claim: dict[str, Any], *names: str) -> str:
    for name in names:
        if claim.get(name) not in (None, ""):
            return str(claim.get(name))
    return ""


def score_narrative_for_claim(template: dict[str, Any], claim: dict[str, Any]) -> int:
    procedure = _norm(_claim_field(claim, "procedure", "Procedure"))
    denial = _norm(_claim_field(claim, "denialReason", "DenialReason", "denialReason"))
    status = _norm(_claim_field(claim, "status", "ClaimStatus", "claimStatus"))
    score = 0
    for tag in template.get("procedureTags") or []:
        if tag in procedure:
            score += 3
    for tag in template.get("denialTags") or []:
        if tag in denial or tag in procedure:
            score += 3
    focus = str(template.get("focus") or "")
    if "denied" in status and focus in {"Denial Appeal", "Fracture Documentation", "Medical Necessity"}:
        score += 2
    if "review" in status and focus in {"Medical Necessity", "Prior Authorization"}:
        score += 2
    if "periodontal" in procedure and "Periodontal" in focus:
        score += 4
    if "crown" in procedure and focus in {"Fracture Documentation", "Recurrent Decay", "Medical Necessity"}:
        score += 2
    return score


def select_best_narrative_for_claim(
    claim: dict[str, Any],
    library: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    library = library or build_generic_draft_library()
    ranked = sorted(
        (
            {
                "template": item,
                "score": score_narrative_for_claim(item, claim),
            }
            for item in library
        ),
        key=lambda row: (-row["score"], row["template"]["id"]),
    )
    best = ranked[0] if ranked else None
    return {
        "claimRef": _claim_field(claim, "id", "ClaimId", "claimId"),
        "patientLabel": _claim_field(claim, "patient", "PatientName"),
        "librarySize": len(library),
        "selected": best["template"] if best else None,
        "score": best["score"] if best else 0,
        "alternates": [row["template"]["id"] for row in ranked[1:4]],
        "safety": {
            "localOnly": True,
            "humanReviewRequired": True,
            "notSubmitted": True,
        },
    }


if __name__ == "__main__":
    lib = build_generic_draft_library()
    sample = {
        "id": "CLM-2026-1001",
        "patient": "Patient",
        "procedure": "Crown build-up tooth #30",
        "status": "Denied",
        "denialReason": "Carrier requested clearer documentation of fracture",
    }
    print(json.dumps({"libraryCount": len(lib), "sampleSelection": select_best_narrative_for_claim(sample, lib)}, indent=2))
