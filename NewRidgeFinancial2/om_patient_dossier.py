"""OM patient dossier mini surfaces — Moonshot Mon–Thu consult 2026-07-11.

PHI-safe hashes/initials. SoftDent READ-ONLY. empty ≠ $0.
Uses real sd_* columns (patient_name, not first_name/last_name; claims via name join).
"""

from __future__ import annotations

from typing import Any

from nr2_softdent_daily import _hash_patient_id, _open_db, _table_exists
from patient_dossier import _initials, _safe_money, name_hash


def get_patient_dossier_mini(patient_id: str) -> dict[str, Any]:
    """Returns patient summary for OM widget — identifiers hashed."""
    pid = str(patient_id or "").strip()
    if not pid:
        return {"ok": False, "error": "patient_id required"}

    conn, db_path = _open_db()
    if not conn:
        return {"ok": False, "error": "SoftDent DB unavailable", "dbPath": str(db_path) if db_path else None}

    try:
        cur = conn.cursor()
        patient_name = ""
        dob_year = None
        # Real schema: patient_name, first_visit_date, last_visit_date — no dob/first_name/last_name
        if _table_exists(conn, "sd_patients"):
            cur.execute(
                """
                SELECT patient_name, first_visit_date, last_visit_date
                FROM sd_patients WHERE patient_id=? LIMIT 1
                """,
                (pid,),
            )
            row = cur.fetchone()
            if not row:
                return {"ok": False, "error": "Patient not found", "patientHash": _hash_patient_id(pid)}
            patient_name = str(row[0] or "")
            last_visit = row[2]
        else:
            return {"ok": False, "error": "sd_patients missing"}

        primary_carrier = None
        if _table_exists(conn, "sd_insurance_payment_lines"):
            # May not have patient_id — try if column exists
            cols = {r[1] for r in cur.execute("PRAGMA table_info(sd_insurance_payment_lines)").fetchall()}
            if "insurance_company" in cols or "payer" in cols:
                payer_col = "insurance_company" if "insurance_company" in cols else "payer"
                if "patient_id" in cols:
                    cur.execute(
                        f"SELECT {payer_col} FROM sd_insurance_payment_lines WHERE patient_id=? LIMIT 1",
                        (pid,),
                    )
                    ins = cur.fetchone()
                    if ins:
                        primary_carrier = ins[0]
        if not primary_carrier and _table_exists(conn, "sd_payments"):
            cur.execute(
                "SELECT payer FROM sd_payments WHERE patient_id=? AND COALESCE(payer,'')!='' LIMIT 1",
                (pid,),
            )
            ins = cur.fetchone()
            if ins:
                primary_carrier = ins[0]

        open_claims = 0
        if _table_exists(conn, "sd_claims") and patient_name:
            cur.execute(
                """
                SELECT COUNT(*) FROM sd_claims
                WHERE patient_name=?
                  AND LOWER(COALESCE(claim_status,'')) NOT IN ('closed','paid','complete','completed')
                """,
                (patient_name,),
            )
            open_claims = int(cur.fetchone()[0] or 0)

        has_notes = False
        try:
            from nr2_clinical_bridge import load_clinical_context

            ctx = load_clinical_context(None, patient_id=pid, patient_name=patient_name, limit=1)
            has_notes = bool(ctx.get("items"))
        except Exception:
            has_notes = False

        # Account balance — SoftDent extract has no AR balance column; honest unknown
        account_balance = "unavailable"

        return {
            "ok": True,
            "patientHash": _hash_patient_id(pid),
            "nameHash": name_hash(patient_name),
            "initials": _initials(patient_name),
            "dobYear": dob_year,  # Schema gap: sd_patients has no DOB
            "schemaGap": "sd_patients has no DOB/gender/SSN columns in ODBC extract",
            "primaryCarrier": primary_carrier,
            "openClaims": open_claims,
            "lastVisit": last_visit or "unknown",
            "accountBalance": account_balance,
            "hasClinicalNotes": has_notes,
            "readOnly": True,
        }
    finally:
        conn.close()


def get_claims_review_detail(patient_id: str, *, limit: int = 10) -> dict[str, Any]:
    """Claims detail for selected patient — amounts use safe money / null honesty."""
    pid = str(patient_id or "").strip()
    conn, _db = _open_db()
    if not conn:
        return {"ok": False, "items": [], "emptyMessage": "SoftDent DB unavailable"}
    try:
        cur = conn.cursor()
        patient_name = ""
        if _table_exists(conn, "sd_patients"):
            cur.execute("SELECT patient_name FROM sd_patients WHERE patient_id=? LIMIT 1", (pid,))
            row = cur.fetchone()
            if row:
                patient_name = str(row[0] or "")
        if not patient_name or not _table_exists(conn, "sd_claims"):
            return {
                "ok": True,
                "items": [],
                "patientHash": _hash_patient_id(pid),
                "emptyMessage": "No SoftDent claims for this patient (name join required).",
            }
        cur.execute(
            """
            SELECT claim_id, payer, service_date, claim_amount, claim_status
            FROM sd_claims WHERE patient_name=?
            ORDER BY service_date DESC LIMIT ?
            """,
            (patient_name, max(1, min(int(limit or 10), 50))),
        )
        items = []
        for r in cur.fetchall():
            amt = r[3]
            items.append(
                {
                    "claimHash": _hash_patient_id(str(r[0] or "")),
                    "claimId": str(r[0] or ""),
                    "payer": r[1] or "unknown",
                    "serviceDate": r[2] or "unknown",
                    "amount": _safe_money(amt),
                    "status": r[4] or "unknown",
                    "narrativeDrafted": False,  # local narrative store may enrich later
                }
            )
        return {
            "ok": True,
            "items": items,
            "patientHash": _hash_patient_id(pid),
            "emptyMessage": "No SoftDent claims for this patient." if not items else "",
        }
    finally:
        conn.close()
