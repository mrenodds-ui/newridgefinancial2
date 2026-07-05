"""HAL outbound executors — email and QuickBooks export after staff consent."""

from __future__ import annotations

import csv
import json
import os
import smtplib
import zipfile
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
NR2_DATA_DIR = REPO_ROOT / "app_data" / "nr2"
EXPORTS_DIR = NR2_DATA_DIR / "exports"
INBOX_DIR = NR2_DATA_DIR / "document_inbox"
AUDIT_KEY = "nr2:hal:outbound-audit"
CLAIMS_CSV_NAMES = ("softdent_claims_export.csv", "claims_export.csv")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _smtp_config() -> dict[str, Any]:
    return {
        "host": os.environ.get("NR2_SMTP_HOST", "").strip(),
        "port": int(os.environ.get("NR2_SMTP_PORT", "587") or "587"),
        "user": os.environ.get("NR2_SMTP_USER", "").strip(),
        "password": os.environ.get("NR2_SMTP_PASS", "").strip(),
        "from_addr": os.environ.get("NR2_SMTP_FROM", os.environ.get("NR2_SMTP_USER", "")).strip(),
        "use_tls": os.environ.get("NR2_SMTP_TLS", "1").strip() not in ("0", "false", "no"),
    }


def smtp_configured() -> bool:
    cfg = _smtp_config()
    return bool(cfg["host"] and cfg["from_addr"])


def append_outbound_audit(store, *, action: str, consent: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    raw = store.get(AUDIT_KEY) if store else None
    try:
        entries = json.loads(raw) if raw else []
    except json.JSONDecodeError:
        entries = []
    if not isinstance(entries, list):
        entries = []
    entry = {
        "id": f"out-{len(entries) + 1}",
        "at": _utc_now(),
        "action": action,
        "consent": consent,
        "result": result,
    }
    entries.append(entry)
    if len(entries) > 200:
        entries = entries[-200:]
    if store:
        store.set(AUDIT_KEY, json.dumps(entries))
    return entry


def send_email_with_consent(
    *,
    to: str,
    subject: str,
    body: str,
    consent_text: str,
    actor: str = "Staff",
    store=None,
    dry_run: bool = False,
) -> dict[str, Any]:
    to_addr = str(to or "").strip()
    subj = str(subject or "").strip() or "(no subject)"
    text = str(body or "").strip()
    if not to_addr:
        return {"ok": False, "error": "missing_recipient", "message": "Email recipient is required."}
    if not consent_text or not str(consent_text).strip():
        return {"ok": False, "error": "missing_consent", "message": "Staff consent is required before sending email."}

    cfg = _smtp_config()
    if not smtp_configured():
        result = {
            "ok": False,
            "error": "smtp_not_configured",
            "message": "Set NR2_SMTP_HOST, NR2_SMTP_FROM, and NR2_SMTP_USER in the environment to enable outbound email.",
            "draft": {"to": to_addr, "subject": subj, "body": text},
        }
        if store:
            append_outbound_audit(store, action="email", consent={"text": consent_text, "actor": actor}, result=result)
        return result

    if dry_run:
        result = {"ok": True, "dryRun": True, "to": to_addr, "subject": subj, "message": "Dry run — email not sent."}
        if store:
            append_outbound_audit(store, action="email", consent={"text": consent_text, "actor": actor}, result=result)
        return result

    msg = EmailMessage()
    msg["From"] = cfg["from_addr"]
    msg["To"] = to_addr
    msg["Subject"] = subj
    msg.set_content(text)

    try:
        with smtplib.SMTP(cfg["host"], cfg["port"], timeout=30) as server:
            if cfg["use_tls"]:
                server.starttls()
            if cfg["user"] and cfg["password"]:
                server.login(cfg["user"], cfg["password"])
            server.send_message(msg)
        result = {"ok": True, "to": to_addr, "subject": subj, "sentAt": _utc_now(), "message": f"Email sent to {to_addr}."}
    except Exception as exc:
        result = {"ok": False, "error": "smtp_send_failed", "message": str(exc), "to": to_addr, "subject": subj}

    if store:
        append_outbound_audit(store, action="email", consent={"text": consent_text, "actor": actor}, result=result)
    return result


def export_posting_queue_iif(store_path: Any, *, limit: int = 200, consent_text: str = "", actor: str = "Staff", store=None) -> dict[str, Any]:
    from accounting_bridge import export_approved_posting_queue_iif

    if not consent_text or not str(consent_text).strip():
        return {"ok": False, "error": "missing_consent", "message": "Staff consent is required before QuickBooks export."}
    payload = export_approved_posting_queue_iif(store_path, limit=limit)
    payload["ok"] = bool(payload.get("iif"))
    payload["message"] = (
        f"Exported {payload.get('entryCount', 0)} approved entries ({payload.get('lineCount', 0)} lines) to IIF."
        if payload["ok"]
        else "No approved entries to export."
    )
    if store:
        append_outbound_audit(
            store,
            action="qb-iif-export",
            consent={"text": consent_text, "actor": actor},
            result={"ok": payload["ok"], "entryCount": payload.get("entryCount"), "path": payload.get("exportPath")},
        )
    return payload


def _exports_subdir(name: str) -> Path:
    path = EXPORTS_DIR / name
    path.mkdir(parents=True, exist_ok=True)
    return path


def _find_claims_csv() -> Path | None:
    candidates = [
        INBOX_DIR / "softdent" / name for name in CLAIMS_CSV_NAMES
    ] + [
        INBOX_DIR / name for name in CLAIMS_CSV_NAMES
    ]
    for path in candidates:
        if path.is_file():
            return path
    return None


def _load_claim_row(claim_id: str) -> dict[str, Any] | None:
    needle = str(claim_id or "").strip().lower()
    if not needle:
        return None
    csv_path = _find_claims_csv()
    if not csv_path:
        return None
    try:
        with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                ref = str(
                    row.get("ClaimRef")
                    or row.get("claim_ref")
                    or row.get("ClaimID")
                    or row.get("claim_id")
                    or row.get("Reference")
                    or ""
                ).strip()
                if ref and needle in ref.lower():
                    return dict(row)
    except OSError:
        return None
    return None


def build_claim_submission_packet(
    *,
    claim_id: str = "",
    narrative: str = "",
    notes: str = "",
    consent_text: str = "",
    actor: str = "Staff",
    store=None,
) -> dict[str, Any]:
    if not consent_text or not str(consent_text).strip():
        return {"ok": False, "error": "missing_consent", "message": "Staff consent is required before building a claim packet."}
    claim = str(claim_id or "claim").strip().replace("/", "-").replace("\\", "-") or "claim"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    folder = _exports_subdir("claim_packets") / f"{claim}_{stamp}"
    folder.mkdir(parents=True, exist_ok=True)
    claim_row = _load_claim_row(claim_id) if claim_id else None
    enriched_narrative = str(narrative or notes or "").strip()
    if not enriched_narrative and claim_row:
        parts = []
        for key in ("Patient", "patient", "Payer", "payer", "Status", "status", "Procedure", "procedure", "Amount", "amount"):
            val = claim_row.get(key)
            if val:
                parts.append(f"{key}: {val}")
        if parts:
            enriched_narrative = "Claim context from SoftDent export:\n" + "\n".join(parts) + "\n\nDraft narrative — staff to review before upload."
    if not enriched_narrative:
        enriched_narrative = "Draft narrative — staff to review before upload."
    readme = (
        "New Ridge Family Dental — claim submission packet (local draft)\n"
        "================================================================\n"
        f"Claim: {claim}\n"
        f"Built: {_utc_now()}\n\n"
        "Staff steps:\n"
        "1. Review narrative.txt, claim_context.json, and attachment_manifest.json\n"
        "2. Attach any required clinical notes or imaging from SoftDent\n"
        "3. Upload this zip to the payer portal manually\n"
        "HAL does not submit to payer portals directly.\n"
    )
    (folder / "PORTAL_UPLOAD_README.txt").write_text(readme, encoding="utf-8")
    (folder / "narrative.txt").write_text(enriched_narrative, encoding="utf-8")
    if claim_row:
        (folder / "claim_context.json").write_text(json.dumps(claim_row, indent=2), encoding="utf-8")
    manifest = {
        "claimId": claim,
        "builtAt": _utc_now(),
        "files": [
            {"name": "narrative.txt", "purpose": "Payer portal narrative field", "required": True},
            {"name": "checklist.txt", "purpose": "Staff review checklist", "required": True},
            {"name": "PORTAL_UPLOAD_README.txt", "purpose": "Upload instructions", "required": False},
        ],
        "staffAttachments": [
            "Perio charting (if required by payer)",
            "Clinical notes from SoftDent",
            "Radiographs or imaging exports",
        ],
    }
    if claim_row:
        manifest["files"].append({"name": "claim_context.json", "purpose": "Local claim row from SoftDent export", "required": False})
    (folder / "attachment_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (folder / "checklist.txt").write_text(
        "- Verify patient and subscriber IDs\n- Confirm procedure codes and dates\n- Attach perio charting if required\n- Review attachment_manifest.json\n- Upload via payer portal\n",
        encoding="utf-8",
    )
    zip_path = folder.with_suffix(".zip")
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for item in folder.iterdir():
            if item.is_file():
                archive.write(item, arcname=item.name)
    result = {
        "ok": True,
        "claimId": claim,
        "exportPath": str(zip_path),
        "folderPath": str(folder),
        "enrichedFromImport": bool(claim_row),
        "message": f"Claim packet ready: {zip_path.name}. Upload via payer portal after review.",
    }
    if store:
        append_outbound_audit(
            store,
            action="claim-packet",
            consent={"text": consent_text, "actor": actor},
            result={"ok": True, "claimId": claim, "path": str(zip_path)},
        )
    return result


def export_narrative_portal_prep(
    *,
    claim_id: str = "",
    narrative: str = "",
    consent_text: str = "",
    actor: str = "Staff",
    store=None,
) -> dict[str, Any]:
    if not consent_text or not str(consent_text).strip():
        return {"ok": False, "error": "missing_consent", "message": "Staff consent is required before narrative portal prep."}
    claim = str(claim_id or "narrative").strip().replace("/", "-") or "narrative"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_dir = _exports_subdir("narrative_portal")
    txt_path = out_dir / f"{claim}_{stamp}_portal_narrative.txt"
    meta_path = out_dir / f"{claim}_{stamp}_upload_steps.txt"
    body = str(narrative or "").strip() or "Draft narrative — complete before portal upload."
    txt_path.write_text(body, encoding="utf-8")
    meta_path.write_text(
        "Portal upload prep\n"
        f"Claim: {claim}\n"
        f"Built: {_utc_now()}\n\n"
        "1. Copy narrative text into payer portal narrative field\n"
        "2. Attach supporting documentation\n"
        "3. Confirm claim ID matches SoftDent export\n",
        encoding="utf-8",
    )
    result = {
        "ok": True,
        "claimId": claim,
        "exportPath": str(txt_path),
        "stepsPath": str(meta_path),
        "message": f"Narrative portal prep saved to {txt_path.name}. Copy into payer portal after review.",
    }
    if store:
        append_outbound_audit(
            store,
            action="narrative-portal-prep",
            consent={"text": consent_text, "actor": actor},
            result={"ok": True, "claimId": claim, "path": str(txt_path)},
        )
    return result


def build_payer_portal_rpa_with_consent(
    *,
    claim_id: str = "",
    payer: str = "",
    portal_url: str = "",
    narrative: str = "",
    consent_text: str = "",
    actor: str = "Staff",
    store=None,
) -> dict[str, Any]:
    from payer_portal_bridge import build_portal_rpa_bundle

    result = build_portal_rpa_bundle(
        claim_id=claim_id,
        payer=payer,
        portal_url=portal_url,
        narrative=narrative,
        consent_text=consent_text,
        actor=actor,
    )
    if store and result.get("ok"):
        append_outbound_audit(
            store,
            action="payer-portal-rpa",
            consent={"text": consent_text, "actor": actor},
            result={"ok": True, "claimId": result.get("claimId"), "path": result.get("exportPath")},
        )
    return result


def queue_softdent_writeback_with_consent(
    *,
    action: str = "note",
    payload: dict[str, Any] | None = None,
    consent_text: str = "",
    actor: str = "Staff",
    store=None,
) -> dict[str, Any]:
    from softdent_writeback_bridge import enqueue_writeback

    result = enqueue_writeback(action=action, payload=payload or {}, consent_text=consent_text, actor=actor)
    if store:
        append_outbound_audit(
            store,
            action="softdent-writeback-queue",
            consent={"text": consent_text, "actor": actor},
            result={"ok": result.get("ok"), "entryId": result.get("entryId"), "message": result.get("message")},
        )
    return result


def softdent_writeback_status() -> dict[str, Any]:
    from softdent_writeback_bridge import queue_status

    return queue_status()


def send_staff_briefing_email(
    *,
    subject: str,
    body: str,
    to: str = "",
    consent_text: str = "Scheduled internal briefing",
    actor: str = "HAL",
    store=None,
) -> dict[str, Any]:
    recipient = str(to or os.environ.get("NR2_BRIEFING_EMAIL_TO", "")).strip()
    if not recipient:
        return {
            "ok": False,
            "error": "briefing_email_not_configured",
            "message": "Set NR2_BRIEFING_EMAIL_TO to enable scheduled briefing email.",
            "draft": {"subject": subject, "body": body},
        }
    return send_email_with_consent(
        to=recipient,
        subject=subject,
        body=body,
        consent_text=consent_text,
        actor=actor,
        store=store,
    )


def post_qbo_journal_with_consent(
    store_path: Any,
    *,
    limit: int = 25,
    consent_text: str = "",
    actor: str = "Staff",
    store=None,
    dry_run: bool = False,
) -> dict[str, Any]:
    if not consent_text or not str(consent_text).strip():
        return {"ok": False, "error": "missing_consent", "message": "Staff consent is required before QuickBooks Online post."}
    from quickbooks_online_bridge import post_approved_queue_entries, qbo_config

    cfg = qbo_config()
    if not cfg.get("client_id") or not cfg.get("refresh_token"):
        result = {
            "ok": False,
            "error": "qbo_not_configured",
            "message": "QuickBooks Online API not configured — use Export approved journal entries to QuickBooks IIF after consent.",
        }
        if store:
            append_outbound_audit(
                store,
                action="qbo-journal-post",
                consent={"text": consent_text, "actor": actor},
                result=result,
            )
        return result
    payload = post_approved_queue_entries(store_path, limit=limit, dry_run=dry_run)
    payload["ok"] = bool(payload.get("ok"))
    if store:
        append_outbound_audit(
            store,
            action="qbo-journal-post",
            consent={"text": consent_text, "actor": actor},
            result={"ok": payload.get("ok"), "posted": payload.get("posted"), "message": payload.get("message")},
        )
    return payload


def quickbooks_online_status() -> dict[str, Any]:
    client_id = os.environ.get("NR2_QBO_CLIENT_ID", "").strip()
    client_secret = os.environ.get("NR2_QBO_CLIENT_SECRET", "").strip()
    realm_id = os.environ.get("NR2_QBO_REALM_ID", "").strip()
    refresh = os.environ.get("NR2_QBO_REFRESH_TOKEN", "").strip()
    configured = bool(client_id and client_secret)
    ready = configured and bool(realm_id and refresh)
    return {
        "ok": True,
        "configured": configured,
        "ready": ready,
        "realmId": realm_id or None,
        "message": (
            "QuickBooks Online API ready for consent-gated journal post."
            if ready
            else "Set NR2_QBO_CLIENT_ID, NR2_QBO_CLIENT_SECRET, NR2_QBO_REALM_ID, and NR2_QBO_REFRESH_TOKEN to enable QBO API post (hal-160+)."
            if configured
            else "QuickBooks Online API not configured — IIF export remains the supported path."
        ),
    }


def list_outbound_audit(store=None, *, limit: int = 15) -> dict[str, Any]:
    raw = store.get(AUDIT_KEY) if store else None
    try:
        entries = json.loads(raw) if raw else []
    except json.JSONDecodeError:
        entries = []
    if not isinstance(entries, list):
        entries = []
    items = entries[-max(1, int(limit or 15)) :]
    return {"ok": True, "items": list(reversed(items)), "count": len(entries)}
