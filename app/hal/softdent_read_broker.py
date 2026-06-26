"""SoftDent Read Broker.

Phase 1 employee-like read access for HAL. The broker mediates all
patient-scoped SoftDent reads behind role gates and record-level audit. It:

- reads only from server-configured exports (no user-shaped SQL, no DB browsing),
- returns bounded typed facts (never raw CSV rows or full payloads),
- includes source metadata and missing-data codes,
- never writes back to SoftDent and never performs external submission,
- never fabricates A/R: missing A/R sources surface ``missing_softdent_ar``.

Role enforcement convention: when ``roles is None`` the caller is a trusted
internal/unit context and access is allowed (backward compatible). When
``roles`` is provided (for example from an authenticated request), the broker
enforces the SoftDent read roles and raises :class:`SoftDentAccessError` on
missing permissions.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from .audit import record_softdent_read_audit
from .softdent_read_models import (
    MISSING_SOFTDENT_AR,
    MISSING_SOFTDENT_CLAIMS_EXPORT,
    MISSING_SOFTDENT_CLINICAL_NOTES_EXPORT,
    MISSING_SOFTDENT_PATIENT_LEDGER_EXPORT,
    MISSING_SOFTDENT_PATIENT_MATCH,
    MISSING_SOFTDENT_PROCEDURES_EXPORT,
    ClaimContext,
    ClinicalNoteSummary,
    DocumentationStatus,
    LedgerContext,
    NarrativeSourceFacts,
    PatientContext,
    PatientMatch,
    PayerContext,
    ProcedureContext,
    SoftDentPatientQuery,
    SoftDentReadSourceStatus,
    SoftDentSourceMetadata,
)


# --- Roles -----------------------------------------------------------------

SOFTDENT_READ = "softdent:read"
SOFTDENT_PATIENT_READ = "softdent:patient:read"
SOFTDENT_CLINICAL_READ = "softdent:clinical:read"
SOFTDENT_LEDGER_READ = "softdent:ledger:read"
SOFTDENT_NARRATIVE_DRAFT = "softdent:narrative:draft"
SOFTDENT_EXPORT_REFRESH = "softdent:export:refresh"

SOFTDENT_READ_ROLES = frozenset(
    {
        SOFTDENT_READ,
        SOFTDENT_PATIENT_READ,
        SOFTDENT_CLINICAL_READ,
        SOFTDENT_LEDGER_READ,
        SOFTDENT_NARRATIVE_DRAFT,
        SOFTDENT_EXPORT_REFRESH,
    }
)

# Bounded clinical-note controls (mirrors the narrative adapter discipline).
CLINICAL_NOTE_SUMMARY_MAX_LENGTH = 500
CLINICAL_NOTE_BULK_MARKERS = (
    "full patient export",
    "all patients",
    "database dump",
    "patient roster",
    "unrestricted export",
)


class SoftDentAccessError(PermissionError):
    """Raised when a caller lacks the SoftDent read roles for an action."""

    def __init__(self, *, action: str, required_roles: list[str], missing_roles: list[str]) -> None:
        self.action = action
        self.required_roles = required_roles
        self.missing_roles = missing_roles
        super().__init__(
            f"SoftDent read access denied for action '{action}'. "
            f"Required roles: {', '.join(required_roles)}. Missing: {', '.join(missing_roles)}."
        )


def _normalize_roles(roles: Iterable[str] | None) -> set[str] | None:
    if roles is None:
        return None
    return {str(role) for role in roles}


def _require_roles(roles: set[str] | None, required: Iterable[str], *, action: str) -> None:
    if roles is None:
        return
    required_set = {str(role) for role in required}
    missing = required_set - roles
    if missing:
        raise SoftDentAccessError(
            action=action,
            required_roles=sorted(required_set),
            missing_roles=sorted(missing),
        )


def _has_roles(roles: set[str] | None, required: Iterable[str]) -> bool:
    if roles is None:
        return True
    return set(str(role) for role in required).issubset(roles)


def _row_value(row: dict, keys: tuple[str, ...]) -> str:
    from .financial_tools import _normalize_key

    normalized_keys = {_normalize_key(key) for key in keys}
    for key, value in row.items():
        if _normalize_key(str(key)) in normalized_keys and value not in (None, ""):
            return str(value)
    return ""


def _clinical_note_summary_text(raw_text: str) -> str | None:
    collapsed = " ".join(str(raw_text or "").split())
    if not collapsed:
        return None
    lowered = collapsed.lower()
    if any(marker in lowered for marker in CLINICAL_NOTE_BULK_MARKERS):
        return None
    if len(collapsed) > CLINICAL_NOTE_SUMMARY_MAX_LENGTH:
        return collapsed[:CLINICAL_NOTE_SUMMARY_MAX_LENGTH].rstrip() + "..."
    return collapsed


def _load_claim_rows() -> list[dict]:
    from . import financial_tools as ft

    return ft.load_softdent_claim_rows()


def _load_clinical_note_rows() -> list[dict]:
    from . import financial_tools as ft

    return ft.load_softdent_clinical_note_rows()


def _load_ar_rows() -> list[dict]:
    from . import financial_tools as ft

    return ft.load_softdent_ar_rows()


def _claim_source_status() -> dict:
    from . import financial_tools as ft

    return ft.get_softdent_claim_source_status()


def _clinical_note_source_status() -> dict:
    from . import financial_tools as ft

    return ft.get_softdent_clinical_note_source_status()


class SoftDentReadBroker:
    """Export-backed broker. No SQL, no writeback, no raw rows."""

    def get_source_status(self) -> SoftDentReadSourceStatus:
        claim_rows = _load_claim_rows()
        note_rows = _load_clinical_note_rows()
        ar_rows = _load_ar_rows()
        claim_status = _claim_source_status()
        note_status = _clinical_note_source_status()

        metadata = [
            self._source_metadata(claim_status, len(claim_rows)),
            self._source_metadata(note_status, len(note_rows)),
        ]
        missing: list[str] = []
        if not claim_rows:
            missing.append(MISSING_SOFTDENT_CLAIMS_EXPORT)
        if not note_rows:
            missing.append(MISSING_SOFTDENT_CLINICAL_NOTES_EXPORT)
        if not self._patient_level_ar_available(ar_rows):
            missing.append(MISSING_SOFTDENT_AR)

        return SoftDentReadSourceStatus(
            claims_available=bool(claim_rows),
            clinical_notes_available=bool(note_rows),
            ar_available=self._patient_level_ar_available(ar_rows),
            source_metadata=metadata,
            missing_data_codes=missing,
        )

    def find_patients(
        self,
        query_text: str,
        *,
        actor: str | None = None,
        roles: Iterable[str] | None = None,
        limit: int = 5,
    ) -> list[PatientMatch]:
        from .financial_tools import (
            _extract_patient_query_signals,
            _find_matching_rows,
            _refresh_patient_name_registry,
        )

        normalized_roles = _normalize_roles(roles)
        _require_roles(normalized_roles, {SOFTDENT_READ, SOFTDENT_PATIENT_READ}, action="find_patients")

        claim_rows = _load_claim_rows()
        note_rows = _load_clinical_note_rows()
        known = _refresh_patient_name_registry(claim_rows=claim_rows, note_rows=note_rows)
        signals = _extract_patient_query_signals(query_text, known_patient_names=known)
        matched = _find_matching_rows([*claim_rows, *note_rows], signals)
        seen: set[str] = set()
        matches: list[PatientMatch] = []
        for row in matched:
            name = _row_value(row, ("PatientName", "patient_name", "patient", "name"))
            if not name or name.lower() in seen:
                continue
            seen.add(name.lower())
            matches.append(PatientMatch(display_name=name))
            if len(matches) >= max(1, limit):
                break
        return matches

    def get_patient_context(
        self,
        query: SoftDentPatientQuery,
        *,
        actor: str | None = None,
        roles: Iterable[str] | None = None,
        workflow_reason: str = "patient_context",
        response_mode: str = "answer",
        write_audit: bool = True,
    ) -> PatientContext:
        normalized_roles = _normalize_roles(roles)
        _require_roles(normalized_roles, {SOFTDENT_READ, SOFTDENT_PATIENT_READ}, action="get_patient_context")

        match = self._match_patient(query.question or query.patient_ref or "")
        if not match["matched"]:
            return PatientContext(matched=False, missing_data_codes=[MISSING_SOFTDENT_PATIENT_MATCH])

        matched_claims = match["claims"]
        matched_notes = match["notes"]
        include_clinical = query.include_clinical_notes and _has_roles(normalized_roles, {SOFTDENT_CLINICAL_READ})
        include_ledger = query.include_ledger and _has_roles(normalized_roles, {SOFTDENT_LEDGER_READ})

        claims = [self._build_claim_context(row) for row in matched_claims]
        procedures = self._build_procedures(matched_claims)
        clinical_notes = self._build_clinical_notes(matched_notes, limit=query.note_limit) if include_clinical else []
        ledger = self.get_ledger_context(match["display_name"], actor=actor, roles=roles, write_audit=False) if include_ledger else None
        payer_context = self._build_payer_context(matched_claims)
        documentation = self._build_documentation_status(matched_claims, matched_notes)

        missing: list[str] = []
        if not matched_claims:
            missing.append(MISSING_SOFTDENT_CLAIMS_EXPORT)
        if query.include_clinical_notes and not matched_notes:
            missing.append(MISSING_SOFTDENT_CLINICAL_NOTES_EXPORT)
        missing.append(MISSING_SOFTDENT_PROCEDURES_EXPORT)
        if ledger is not None:
            missing.extend(ledger.missing_data_codes)
        elif query.include_ledger:
            missing.append(MISSING_SOFTDENT_AR)

        narrative_facts = None
        if query.include_narrative_source_facts:
            narrative_facts = self._build_narrative_source_facts(
                display_name=match["display_name"],
                claims=claims,
                procedures=procedures,
                clinical_notes=clinical_notes,
                ledger=ledger,
            )

        context = PatientContext(
            matched=True,
            display_name=match["display_name"],
            chart_ref_hash=_hash_ref(match["display_name"]),
            claims=claims,
            procedures=procedures,
            clinical_notes=clinical_notes,
            ledger=ledger,
            payer_context=payer_context,
            documentation_status=documentation,
            narrative_source_facts=narrative_facts,
            missing_data_codes=sorted(set(missing)),
            source_metadata=self._patient_source_metadata(len(matched_claims), len(matched_notes)),
        )

        if write_audit and actor:
            self._audit(
                actor=actor,
                roles=normalized_roles,
                workflow_reason=workflow_reason,
                response_mode=response_mode,
                display_name=match["display_name"],
                claims=matched_claims,
                notes=matched_notes,
                ledger_used=ledger is not None,
                missing_codes=context.missing_data_codes,
            )
        return context

    def get_claim_context(
        self,
        claim_id: str,
        *,
        actor: str | None = None,
        roles: Iterable[str] | None = None,
        workflow_reason: str = "claim_context",
    ) -> ClaimContext | None:
        normalized_roles = _normalize_roles(roles)
        _require_roles(normalized_roles, {SOFTDENT_READ}, action="get_claim_context")
        target = str(claim_id or "").strip().upper()
        if not target:
            return None
        for row in _load_claim_rows():
            if _row_value(row, ("ClaimId", "claim_id", "claimnumber", "claim")).strip().upper() == target:
                context = self._build_claim_context(row)
                if actor:
                    self._audit(
                        actor=actor,
                        roles=normalized_roles,
                        workflow_reason=workflow_reason,
                        response_mode="answer",
                        display_name=_row_value(row, ("PatientName", "patient_name", "patient", "name"))
                        if _has_roles(normalized_roles, {SOFTDENT_PATIENT_READ})
                        else "",
                        claims=[row],
                        notes=[],
                        ledger_used=False,
                        missing_codes=[],
                    )
                return context
        return None

    def get_clinical_note_summaries(
        self,
        patient_ref: str,
        *,
        actor: str | None = None,
        roles: Iterable[str] | None = None,
        limit: int = 5,
    ) -> list[ClinicalNoteSummary]:
        normalized_roles = _normalize_roles(roles)
        _require_roles(normalized_roles, {SOFTDENT_READ, SOFTDENT_CLINICAL_READ}, action="get_clinical_note_summaries")
        match = self._match_patient(patient_ref)
        if not match["matched"]:
            return []
        notes = self._build_clinical_notes(match["notes"], limit=limit)
        if actor and notes:
            self._audit(
                actor=actor,
                roles=normalized_roles,
                workflow_reason="clinical_notes",
                response_mode="answer",
                display_name=match["display_name"],
                claims=[],
                notes=match["notes"],
                ledger_used=False,
                missing_codes=[],
            )
        return notes

    def get_ledger_context(
        self,
        patient_ref: str,
        *,
        actor: str | None = None,
        roles: Iterable[str] | None = None,
        write_audit: bool = True,
    ) -> LedgerContext:
        normalized_roles = _normalize_roles(roles)
        _require_roles(normalized_roles, {SOFTDENT_READ, SOFTDENT_LEDGER_READ}, action="get_ledger_context")
        ar_rows = _load_ar_rows()
        if not self._patient_level_ar_available(ar_rows):
            ledger = LedgerContext(
                available=False,
                missing_data_codes=[MISSING_SOFTDENT_AR, MISSING_SOFTDENT_PATIENT_LEDGER_EXPORT],
            )
            if write_audit and actor:
                self._audit(
                    actor=actor,
                    roles=normalized_roles,
                    workflow_reason="ledger_context",
                    response_mode="answer",
                    display_name=str(patient_ref or ""),
                    claims=[],
                    notes=[],
                    ledger_used=True,
                    missing_codes=ledger.missing_data_codes,
                )
            return ledger
        # A real patient-level A/R source is not wired in Phase 1; remain unavailable
        # rather than fabricating balances. This branch stays conservative on purpose.
        return LedgerContext(available=False, missing_data_codes=[MISSING_SOFTDENT_AR])

    def build_narrative_source_facts(
        self,
        patient_ref: str,
        claim_id: str | None = None,
        *,
        actor: str | None = None,
        roles: Iterable[str] | None = None,
    ) -> NarrativeSourceFacts:
        normalized_roles = _normalize_roles(roles)
        _require_roles(
            normalized_roles,
            {SOFTDENT_READ, SOFTDENT_PATIENT_READ, SOFTDENT_NARRATIVE_DRAFT},
            action="build_narrative_source_facts",
        )
        query = SoftDentPatientQuery(
            question=patient_ref,
            patient_ref=patient_ref,
            claim_id=claim_id,
            include_narrative_source_facts=True,
        )
        context = self.get_patient_context(
            query,
            actor=actor,
            roles=roles,
            workflow_reason="narrative_draft",
            response_mode="narrative_draft",
        )
        return context.narrative_source_facts or NarrativeSourceFacts(
            patient_label=context.display_name,
            limitations=["No narrative source facts were available from approved exports."],
        )

    # --- Legacy bridge -----------------------------------------------------

    def get_legacy_patient_context(
        self,
        question: str,
        *,
        actor: str | None = None,
        roles: Iterable[str] | None = None,
        workflow_reason: str = "patient_context",
        response_mode: str = "answer",
    ) -> dict[str, object]:
        """Return the legacy patient-context dict used by existing HAL flows.

        Preserves the historical shape (snippets/narrative/summary_fields) while
        adding role enforcement and record-level audit. On access denial this
        returns an unmatched context with ``access_denied`` rather than raising,
        so chat answers stay safe.
        """
        from .financial_tools import (
            PATIENT_TOOL_KEYWORDS,
            _build_insurance_narrative,
            _build_patient_row_excerpt,
            _coerce_numeric,
            _make_snippet,
            _pick_first_field_value,
        )

        empty = {"matched": False, "snippets": [], "narrative": "", "summary_fields": {}}
        lowered = question.lower()
        if not any(keyword in lowered for keyword in PATIENT_TOOL_KEYWORDS):
            return empty

        normalized_roles = _normalize_roles(roles)
        try:
            _require_roles(normalized_roles, {SOFTDENT_READ, SOFTDENT_PATIENT_READ}, action="patient_context")
        except SoftDentAccessError as exc:
            return {**empty, "access_denied": True, "required_roles": exc.required_roles}

        match = self._match_patient(question)
        if not match["matched"]:
            return empty

        matched_claims = match["claims"]
        matched_notes = match["notes"]
        signals = match["signals"]

        snippets: list[dict[str, str]] = []
        if matched_claims:
            snippets.append(
                _make_snippet(
                    "softdent-patient-claims-dossier",
                    "SoftDent patient claims dossier",
                    "softdent_tool",
                    _build_patient_row_excerpt(rows=matched_claims, label="claims dossier"),
                )
            )
        if matched_notes:
            snippets.append(
                _make_snippet(
                    "softdent-patient-clinical-dossier",
                    "SoftDent patient clinical dossier",
                    "softdent_tool",
                    _build_patient_row_excerpt(rows=matched_notes, label="clinical dossier"),
                )
            )
        narrative = _build_insurance_narrative(
            question=question,
            matched_claims=matched_claims,
            matched_notes=matched_notes,
            signals=signals,
        )
        snippets.append(
            _make_snippet(
                "softdent-insurance-narrative-support",
                "SoftDent insurance narrative support",
                "softdent_tool",
                narrative,
            )
        )
        patient_name = _pick_first_field_value(matched_claims + matched_notes, ("patientname", "patient_name", "patient", "name"))
        primary_status = _pick_first_field_value(matched_claims, ("claimstatus", "status"))
        total_claim_amount = round(
            sum(_coerce_numeric(row.get("ClaimAmount") or row.get("amount") or row.get("balance")) for row in matched_claims),
            2,
        )
        summary_fields = {
            "patient_name": patient_name,
            "claim_count": len(matched_claims),
            "note_count": len(matched_notes),
            "total_claim_amount": total_claim_amount,
            "primary_claim_status": primary_status,
        }

        if actor:
            self._audit(
                actor=actor,
                roles=normalized_roles,
                workflow_reason=workflow_reason,
                response_mode=response_mode,
                display_name=patient_name or match["display_name"],
                claims=matched_claims,
                notes=matched_notes,
                ledger_used=False,
                missing_codes=[],
            )
        return {"matched": True, "snippets": snippets, "narrative": narrative, "summary_fields": summary_fields}

    # --- Internal helpers --------------------------------------------------

    def _match_patient(self, question: str) -> dict[str, object]:
        from .financial_tools import (
            _extract_patient_query_signals,
            _find_matching_rows,
            _pick_first_field_value,
            _refresh_patient_name_registry,
        )

        claim_rows = _load_claim_rows()
        note_rows = _load_clinical_note_rows()
        known = _refresh_patient_name_registry(claim_rows=claim_rows, note_rows=note_rows)
        signals = _extract_patient_query_signals(question, known_patient_names=known)
        if not signals["exact_terms"] and not signals["meaningful_tokens"]:
            return {"matched": False}
        matched_claims = _find_matching_rows(claim_rows, signals)
        matched_notes = _find_matching_rows(note_rows, signals)
        if not matched_claims and not matched_notes:
            return {"matched": False}
        display_name = _pick_first_field_value(
            matched_claims + matched_notes, ("patientname", "patient_name", "patient", "name")
        )
        return {
            "matched": True,
            "claims": matched_claims,
            "notes": matched_notes,
            "signals": signals,
            "display_name": display_name or "the patient",
        }

    def _build_claim_context(self, row: dict) -> ClaimContext:
        from .financial_tools import _coerce_numeric

        amount_raw = row.get("ClaimAmount") or row.get("amount") or row.get("balance")
        claim_amount = _coerce_numeric(amount_raw) if amount_raw not in (None, "") else None
        denial = _row_value(row, ("DenialReason", "denialreason", "reason", "remark")) or None
        documentation_needed = [denial] if denial else []
        procedure = _row_value(row, ("Procedure", "procdesc", "description", "servicedescription", "treatment"))
        return ClaimContext(
            claim_id=_row_value(row, ("ClaimId", "claim_id", "claimnumber", "claim")) or None,
            status=_row_value(row, ("ClaimStatus", "claimstatus", "status")) or None,
            payer_name=_row_value(row, ("Payer", "carrier", "insurance", "insurancename", "plan")) or None,
            procedure_refs=[procedure] if procedure else [],
            service_date=_row_value(row, ("ServiceDate", "dateofservice", "date", "dos")) or None,
            denial_reason=denial,
            claim_amount=claim_amount,
            documentation_needed=documentation_needed,
            source_record_id=_row_value(row, ("ClaimId", "claim_id", "claimnumber", "claim")) or None,
        )

    def _build_procedures(self, claim_rows: list[dict]) -> list[ProcedureContext]:
        procedures: list[ProcedureContext] = []
        for row in claim_rows[:3]:
            description = _row_value(row, ("Procedure", "procdesc", "description", "servicedescription", "treatment"))
            code = _row_value(row, ("Code", "procedurecode", "adacode", "cdt"))
            if not description and not code:
                continue
            procedures.append(
                ProcedureContext(
                    procedure_id=_row_value(row, ("ProcedureId", "procedure_id")) or None,
                    code=code or None,
                    description=description or None,
                    tooth=_row_value(row, ("Tooth", "toothnumber")) or None,
                    service_date=_row_value(row, ("ServiceDate", "dateofservice", "date", "dos")) or None,
                    provider=_row_value(row, ("Provider", "providername", "dentist")) or None,
                    claim_id=_row_value(row, ("ClaimId", "claim_id", "claimnumber", "claim")) or None,
                    source_record_id=_row_value(row, ("ProcedureId", "procedure_id")) or None,
                )
            )
        return procedures

    def _build_clinical_notes(self, note_rows: list[dict], *, limit: int) -> list[ClinicalNoteSummary]:
        summaries: list[ClinicalNoteSummary] = []
        for row in note_rows[: max(1, limit)]:
            raw_text = _row_value(row, ("ClinicalNote", "note", "note_text", "narrative", "assessment"))
            summary_text = _clinical_note_summary_text(raw_text)
            if not summary_text:
                continue
            summaries.append(
                ClinicalNoteSummary(
                    note_id=_row_value(row, ("NoteId", "note_id")) or None,
                    note_date=_row_value(row, ("NoteDate", "notedate", "date")) or None,
                    procedure_id=_row_value(row, ("ProcedureId", "procedure_id")) or None,
                    summary_text=summary_text,
                    source_record_id=_row_value(row, ("NoteId", "note_id")) or None,
                )
            )
        return summaries

    def _build_payer_context(self, claim_rows: list[dict]) -> list[PayerContext]:
        by_payer: dict[str, PayerContext] = {}
        for row in claim_rows:
            payer = _row_value(row, ("Payer", "carrier", "insurance", "insurancename", "plan"))
            if not payer:
                continue
            status = _row_value(row, ("ClaimStatus", "claimstatus", "status"))
            entry = by_payer.setdefault(payer, PayerContext(payer_name=payer))
            if status and status not in entry.claim_statuses:
                entry.claim_statuses.append(status)
            if status and status.lower() not in {"paid", "closed", "complete", "completed"}:
                pending = _row_value(row, ("ClaimId", "claim_id", "claimnumber", "claim"))
                if pending and pending not in entry.pending_items:
                    entry.pending_items.append(pending)
        return list(by_payer.values())

    def _build_documentation_status(self, claim_rows: list[dict], note_rows: list[dict]) -> DocumentationStatus:
        missing_items: list[str] = []
        available_items: list[str] = []
        source_facts: list[str] = []
        for row in claim_rows:
            denial = _row_value(row, ("DenialReason", "denialreason", "reason", "remark"))
            if denial:
                missing_items.append(denial)
        if note_rows:
            available_items.append("clinical notes present")
            source_facts.append(f"{len(note_rows)} clinical note row(s) matched")
        else:
            missing_items.append(MISSING_SOFTDENT_CLINICAL_NOTES_EXPORT)
        return DocumentationStatus(
            missing_items=missing_items,
            available_items=available_items,
            needs_review=True,
            source_facts=source_facts,
        )

    def _build_narrative_source_facts(
        self,
        *,
        display_name: str,
        claims: list[ClaimContext],
        procedures: list[ProcedureContext],
        clinical_notes: list[ClinicalNoteSummary],
        ledger: LedgerContext | None,
    ) -> NarrativeSourceFacts:
        claim_facts = [
            f"claim {c.claim_id or 'unknown'} status {c.status or 'unknown'} payer {c.payer_name or 'unknown'}"
            for c in claims
        ]
        procedure_facts = [f"{p.description or p.code or 'procedure'}" for p in procedures]
        note_facts = [n.summary_text for n in clinical_notes]
        ledger_facts: list[str] = []
        limitations: list[str] = []
        if ledger is None or not ledger.available:
            ledger_facts.append("patient A/R unavailable from approved exports")
            limitations.append("No verified patient A/R source; do not state a balance.")
        limitations.append("Source facts only; nothing has been submitted or exported.")
        return NarrativeSourceFacts(
            patient_label=display_name,
            claim_facts=claim_facts,
            procedure_facts=procedure_facts,
            clinical_note_facts=note_facts,
            ledger_facts=ledger_facts,
            limitations=limitations,
        )

    def _patient_level_ar_available(self, ar_rows: list[dict]) -> bool:
        if not ar_rows:
            return False
        for row in ar_rows:
            if not isinstance(row, dict):
                continue
            if any(str(row.get(key) or "").strip() for key in ("PatientName", "patient_name", "MRN", "mrn", "patient_id")):
                return True
        return False

    def _source_metadata(self, source_status: dict, row_count: int) -> SoftDentSourceMetadata:
        return SoftDentSourceMetadata(
            source_adapter="exports",
            source_name=str(source_status.get("source_file") or "") or None,
            source_backend=str(source_status.get("source_backend") or "unknown"),
            source_modified_at_utc=str(source_status.get("modified_at_utc") or "") or None,
            loaded_at_utc=datetime.now(timezone.utc).isoformat(),
            row_count=row_count,
        )

    def _patient_source_metadata(self, claim_count: int, note_count: int) -> list[SoftDentSourceMetadata]:
        return [
            self._source_metadata(_claim_source_status(), claim_count),
            self._source_metadata(_clinical_note_source_status(), note_count),
        ]

    def _audit(
        self,
        *,
        actor: str,
        roles: set[str] | None,
        workflow_reason: str,
        response_mode: str,
        display_name: str,
        claims: list[dict],
        notes: list[dict],
        ledger_used: bool,
        missing_codes: list[str],
    ) -> None:
        claim_ids = [
            _row_value(row, ("ClaimId", "claim_id", "claimnumber", "claim"))
            for row in claims
            if _row_value(row, ("ClaimId", "claim_id", "claimnumber", "claim"))
        ]
        note_ids = [
            _row_value(row, ("NoteId", "note_id"))
            for row in notes
            if _row_value(row, ("NoteId", "note_id"))
        ]
        record_softdent_read_audit(
            actor=actor,
            roles_used=sorted(roles) if roles is not None else [],
            workflow_reason=workflow_reason,
            response_mode=response_mode,
            patient_display_name=display_name,
            patient_ref_hash=_hash_ref(display_name),
            chart_ref_hash=_hash_ref(display_name),
            claim_ids=claim_ids,
            clinical_note_ids=note_ids,
            ledger_record_ids=(["patient-ledger"] if ledger_used else []),
            source_adapter="exports",
            source_metadata=[],
            missing_data_codes=list(missing_codes),
            external_action_performed=False,
        )


def _hash_ref(value: str) -> str | None:
    import hashlib

    normalized = str(value or "").strip().lower()
    if not normalized:
        return None
    return "sd-" + hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


_BROKER_SINGLETON: SoftDentReadBroker | None = None


def get_softdent_read_broker() -> SoftDentReadBroker:
    global _BROKER_SINGLETON
    if _BROKER_SINGLETON is None:
        _BROKER_SINGLETON = SoftDentReadBroker()
    return _BROKER_SINGLETON
