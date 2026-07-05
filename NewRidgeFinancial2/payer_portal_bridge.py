"""Payer portal RPA prep — consent-gated manifest and step bundle for staff or automation."""

from __future__ import annotations

import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
EXPORTS_DIR = REPO_ROOT / "app_data" / "nr2" / "exports" / "payer_portal_rpa"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_portal_rpa_bundle(
    *,
    claim_id: str = "",
    payer: str = "",
    portal_url: str = "",
    narrative: str = "",
    consent_text: str = "",
    actor: str = "Staff",
) -> dict[str, Any]:
    if not consent_text or not str(consent_text).strip():
        return {"ok": False, "error": "missing_consent", "message": "Staff consent is required before payer portal RPA prep."}
    claim = str(claim_id or "claim").strip().replace("/", "-") or "claim"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    folder = EXPORTS_DIR / f"{claim}_{stamp}"
    folder.mkdir(parents=True, exist_ok=True)

    steps = [
        {"step": 1, "action": "open_portal", "target": portal_url or "https://provider.payer-portal.example/login", "note": "Staff login required"},
        {"step": 2, "action": "navigate_claim", "claimId": claim, "note": "Search claim by ID or patient"},
        {"step": 3, "action": "paste_narrative", "file": "narrative.txt", "note": "Copy narrative into portal field"},
        {"step": 4, "action": "attach_files", "manifest": "attachment_manifest.json", "note": "Upload attachments per payer rules"},
        {"step": 5, "action": "review_and_submit", "note": "Human confirms before submit — HAL never auto-submits"},
    ]
    manifest = {
        "claimId": claim,
        "payer": payer or "Unknown payer",
        "builtAt": _utc_now(),
        "consentActor": actor,
        "automationPolicy": "prep-only — staff must confirm submit in portal",
        "steps": steps,
        "playwrightHint": {
            "engine": "playwright",
            "headless": False,
            "timeoutMs": 120000,
            "selectors": "Populate NR2_PAYER_PORTAL_SELECTORS JSON for live RPA.",
        },
    }
    (folder / "rpa_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (folder / "narrative.txt").write_text(
        str(narrative or "").strip() or "Draft narrative — complete before portal upload.",
        encoding="utf-8",
    )
    (folder / "STAFF_README.txt").write_text(
        "Payer portal RPA prep bundle\n"
        f"Claim: {claim}\n"
        f"Built: {_utc_now()}\n\n"
        "1. Review rpa_manifest.json steps\n"
        "2. Run manually or with approved RPA runner\n"
        "3. HAL does not submit to payers without staff confirmation in the portal\n",
        encoding="utf-8",
    )
    zip_path = folder.with_suffix(".zip")
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for item in folder.iterdir():
            if item.is_file():
                archive.write(item, arcname=item.name)
    return {
        "ok": True,
        "claimId": claim,
        "exportPath": str(zip_path),
        "manifestPath": str(folder / "rpa_manifest.json"),
        "stepCount": len(steps),
        "message": f"Portal RPA prep ready: {zip_path.name}. Staff or approved RPA runner executes — HAL does not auto-submit.",
    }
