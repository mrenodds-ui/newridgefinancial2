"""Read-only SoftDent Daily End-of-Day report adapter for bounded A/R parsing.

Parses only label-driven A/R fields from the final page of an approved report export.
Never returns raw report text to callers.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover - optional dependency
    PdfReader = None  # type: ignore[misc, assignment]


SOFTDENT_END_OF_DAY_REPORT_PATH_ENV = "SOFTDENT_END_OF_DAY_REPORT_PATH"
SOFTDENT_END_OF_DAY_REPORT_DIR_ENV = "SOFTDENT_END_OF_DAY_REPORT_DIR"
SOFTDENT_EOD_AR_MAX_AGE_DAYS_ENV = "SOFTDENT_EOD_AR_MAX_AGE_DAYS"

DEFAULT_EOD_REPORT_DIR_NAME = "daily_end_of_day"
DEFAULT_EOD_LATEST_NAMES = (
    "softdent_daily_end_of_day_latest.txt",
    "softdent_daily_end_of_day_latest.pdf",
    "softdent_daily_end_of_day_latest.csv",
)
SUPPORTED_EOD_SUFFIXES = frozenset({".txt", ".pdf", ".csv", ".tsv"})

MISSING_SOFTDENT_EOD_REPORT_DATE = "missing_softdent_eod_report_date"
MISSING_SOFTDENT_EOD_REPORT = "missing_softdent_eod_report"

_DAYSHEET_DATE_PATTERN = re.compile(
    r"(?i)\b(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday),?\s+"
    r"(january|february|march|april|may|june|july|august|september|october|november|december)\s+"
    r"(\d{1,2}),\s+(\d{4})"
)

DATE_LABEL_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(?i)\breport\s+date\b\s*[:\-]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2})"), "report_date"),
    (re.compile(r"(?i)\bend\s+of\s+day\s+date\b\s*[:\-]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2})"), "report_date"),
    (re.compile(r"(?i)\bfor\s+date\b\s*[:\-]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2})"), "report_date"),
    (re.compile(r"(?i)\bbusiness\s+date\b\s*[:\-]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2})"), "report_date"),
    (_DAYSHEET_DATE_PATTERN, "daysheet_date"),
    (
        re.compile(
            r"(?i)\bdate\s+range\b\s*[:\-]?\s*"
            r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2})\s*(?:to|through|-)\s*"
            r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2})"
        ),
        "date_range",
    ),
)

GENERATED_LABEL_PATTERN = re.compile(
    r"(?i)\b(?:generated|printed|run\s+date)\b\s*[:\-]?\s*"
    r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2})"
)

FILENAME_DATE_PATTERNS = (
    re.compile(r"(?i)daily_end_of_day_(\d{4}-\d{2}-\d{2})"),
    re.compile(r"(?i)softdent_eod_(\d{8})"),
    re.compile(r"(?i)softdent_daily_end_of_day_(\d{4}-\d{2}-\d{2})"),
    re.compile(r"(?i)daysheet_(\d{4}-\d{2}-\d{2})"),
)

PAGE_MARKER_PATTERN = re.compile(r"(?i)^\s*page\s+(\d+)\s+of\s+(\d+)\s*$", re.MULTILINE)

CURRENCY_PATTERN = re.compile(r"\(?\s*\$?\s*([\d,]+(?:\.\d{2})?)\s*\)?")

AR_SECTION_MARKERS = (
    re.compile(r"(?i)\btotal\s+a/?r\b"),
    re.compile(r"(?i)\baccounts\s+receivable\b"),
    re.compile(r"(?i)\ba/?r\s+summary\b"),
    re.compile(r"(?i)\bnew\s+receivables\s+total\b"),
    re.compile(r"(?i)\breceivables\s+summary\b"),
)

FIELD_LABELS: dict[str, tuple[str, ...]] = {
    "total_ar": (
        "new receivables total",
        "total a/r",
        "total ar",
        "accounts receivable",
    ),
    "patient_ar": ("patient a/r", "patient ar", "patient balance"),
    "insurance_ar": ("insurance a/r", "insurance ar", "insurance balance"),
    "credits": ("credits", "credit balance", "total credits"),
    "collection_total": ("collections", "collection totals", "collection total"),
    "production_total": ("production", "production totals", "production total"),
}

AGING_LABELS: dict[str, tuple[str, ...]] = {
    "current": ("current",),
    "0-30": ("0-30", "0 - 30", "0 to 30"),
    "31-60": ("31-60", "31 - 60", "31 to 60"),
    "61-90": ("61-90", "61 - 90", "61 to 90"),
    "90+": ("90+", "over 90", "90 plus"),
}


class SoftDentEndOfDayReportInventoryItem(BaseModel):
    source_file: str
    source_modified_at_utc: str | None = None
    inferred_report_date: str | None = None
    format: str
    page_count: int | None = None


class SoftDentEndOfDayArSummary(BaseModel):
    available: bool = False
    report_date: str | None = None
    generated_at: str | None = None
    source_file: str | None = None
    source_modified_at_utc: str | None = None
    freshness_status: Literal["current", "stale", "unknown"] = "unknown"
    parse_status: Literal["available", "limited", "missing", "invalid", "stale"] = "missing"
    total_ar: Decimal | None = None
    patient_ar: Decimal | None = None
    insurance_ar: Decimal | None = None
    aging_buckets: dict[str, Decimal] = Field(default_factory=dict)
    credits: Decimal | None = None
    collection_total: Decimal | None = None
    production_total: Decimal | None = None
    office_scope: str | None = None
    provider_scope: str | None = None
    source_refs: list[str] = Field(default_factory=list)
    missing_data_codes: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    stale_reason: str | None = None
    page_number: int | None = None
    page_count: int | None = None

    def to_public_dict(self) -> dict[str, object]:
        """Bounded API payload without raw report content."""

        def _money(value: Decimal | None) -> float | None:
            if value is None:
                return None
            return float(value)

        return {
            "available": self.available,
            "report_date": self.report_date,
            "generated_at": self.generated_at,
            "source_file": self.source_file,
            "source_modified_at_utc": self.source_modified_at_utc,
            "freshness_status": self.freshness_status,
            "parse_status": self.parse_status,
            "total_ar": _money(self.total_ar),
            "patient_ar": _money(self.patient_ar),
            "insurance_ar": _money(self.insurance_ar),
            "aging_buckets": {key: _money(value) for key, value in self.aging_buckets.items()},
            "credits": _money(self.credits),
            "collection_total": _money(self.collection_total),
            "production_total": _money(self.production_total),
            "office_scope": self.office_scope,
            "provider_scope": self.provider_scope,
            "source_refs": list(self.source_refs),
            "missing_data_codes": list(self.missing_data_codes),
            "limitations": list(self.limitations),
            "stale_reason": self.stale_reason,
            "page_number": self.page_number,
            "page_count": self.page_count,
            "source_label": "Daily End-of-Day report A/R",
        }


@dataclass(frozen=True)
class _ParsedReportText:
    text: str
    page_number: int | None
    page_count: int | None


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _default_eod_report_dir() -> Path:
    return _project_root() / "app" / "data" / "imports" / "softdent" / DEFAULT_EOD_REPORT_DIR_NAME


def _max_age_days() -> int:
    raw = os.getenv(SOFTDENT_EOD_AR_MAX_AGE_DAYS_ENV, "2").strip()
    try:
        return max(1, int(raw))
    except ValueError:
        return 2


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _path_modified_at_utc(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()


def _normalize_date_token(token: str) -> str | None:
    token = token.strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%m-%d-%Y", "%m-%d-%y"):
        try:
            return datetime.strptime(token, fmt).date().isoformat()
        except ValueError:
            continue
    compact = re.fullmatch(r"(\d{8})", token)
    if compact:
        try:
            return datetime.strptime(compact.group(1), "%Y%m%d").date().isoformat()
        except ValueError:
            return None
    return None


def _parse_daysheet_date(match: re.Match[str]) -> str | None:
    month_name = match.group(1)
    day = int(match.group(2))
    year = int(match.group(3))
    try:
        parsed = datetime.strptime(f"{month_name} {day} {year}", "%B %d %Y")
    except ValueError:
        return None
    return parsed.date().isoformat()


def _parse_report_date_from_text(text: str) -> str | None:
    for pattern, kind in DATE_LABEL_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        if kind == "date_range":
            end_token = match.group(2)
            return _normalize_date_token(end_token)
        if kind == "daysheet_date":
            return _parse_daysheet_date(match)
        return _normalize_date_token(match.group(1))
    return None


def _parse_generated_at_from_text(text: str) -> str | None:
    match = GENERATED_LABEL_PATTERN.search(text)
    if not match:
        return None
    return _normalize_date_token(match.group(1))


def _parse_date_from_filename(path: Path) -> str | None:
    stem = path.stem
    for pattern in FILENAME_DATE_PATTERNS:
        match = pattern.search(stem)
        if not match:
            continue
        token = match.group(1)
        if len(token) == 8 and token.isdigit():
            token = f"{token[:4]}-{token[4:6]}-{token[6:8]}"
        return _normalize_date_token(token)
    return None


def _parse_currency_token(raw: str) -> Decimal | None:
    match = CURRENCY_PATTERN.search(raw)
    if not match:
        return None
    negative = "(" in raw and ")" in raw
    try:
        value = Decimal(match.group(1).replace(",", ""))
    except InvalidOperation:
        return None
    if negative:
        value = -value
    return value


def _normalize_label(line: str) -> str:
    return re.sub(r"\s+", " ", line.strip().lower())


def _line_matches_label(line: str, labels: tuple[str, ...]) -> bool:
    normalized = _normalize_label(line)
    if "previous receivables total" in normalized:
        return False
    if "today's receivables" in normalized or "todays receivables" in normalized:
        return False
    return any(label in normalized for label in labels)


def _value_on_same_line(line: str, labels: tuple[str, ...]) -> Decimal | None:
    if not _line_matches_label(line, labels):
        return None
    remainder = line
    for label in labels:
        idx = remainder.lower().find(label)
        if idx >= 0:
            remainder = remainder[idx + len(label) :]
            break
    return _parse_currency_token(remainder)


def _extract_scope(text: str) -> tuple[str | None, str | None]:
    office = None
    provider = None
    for line in text.splitlines():
        normalized = _normalize_label(line)
        if normalized.startswith("office:"):
            office = line.split(":", 1)[1].strip() or None
        if normalized.startswith("provider:"):
            provider = line.split(":", 1)[1].strip() or None
    return office, provider


def _split_pages(text: str) -> list[str]:
    if "\f" in text:
        pages = [page.strip() for page in text.split("\f") if page.strip()]
        if pages:
            return pages

    markers = list(PAGE_MARKER_PATTERN.finditer(text))
    if markers:
        pages: list[str] = []
        for index, marker in enumerate(markers):
            start = marker.end()
            end = markers[index + 1].start() if index + 1 < len(markers) else len(text)
            chunk = text[start:end].strip()
            if chunk:
                pages.append(chunk)
        if pages:
            return pages

    return [text.strip()] if text.strip() else []


def _extract_last_page_text(text: str) -> _ParsedReportText:
    pages = _split_pages(text)
    if not pages:
        return _ParsedReportText(text="", page_number=None, page_count=None)
    return _ParsedReportText(text=pages[-1], page_number=len(pages), page_count=len(pages))


def _read_pdf_text(path: Path) -> str:
    if PdfReader is None:
        return ""
    reader = PdfReader(str(path))
    pages: list[str] = []
    for page in reader.pages:
        pages.append(page.extract_text() or "")
    return "\f".join(pages)


def _read_report_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _read_pdf_text(path)
    for encoding in ("utf-8-sig", "utf-8", "cp1252"):
        try:
            return path.read_text(encoding=encoding)
        except (OSError, UnicodeDecodeError):
            continue
    return ""


def _locate_ar_sections(page_text: str) -> list[str]:
    lines = page_text.splitlines()
    sections: list[list[str]] = []
    current: list[str] = []
    in_section = False
    for line in lines:
        normalized = _normalize_label(line)
        is_marker = any(marker.search(normalized) for marker in AR_SECTION_MARKERS)
        if is_marker:
            if (
                in_section
                and _line_matches_label(line, FIELD_LABELS["total_ar"])
                and _value_on_same_line(line, FIELD_LABELS["total_ar"]) is not None
            ):
                current.append(line)
                continue
            if current:
                sections.append(current)
            current = [line]
            in_section = True
            continue
        if in_section:
            if normalized and any(
                normalized.startswith(prefix)
                for prefix in ("page ", "report date", "generated", "printed", "end of report")
            ):
                sections.append(current)
                current = []
                in_section = False
                continue
            current.append(line)
    if current:
        sections.append(current)
    return ["\n".join(section).strip() for section in sections if any(line.strip() for line in section)]


def _parse_ar_section(section_text: str) -> dict[str, object]:
    lines = [line for line in section_text.splitlines() if line.strip()]
    parsed: dict[str, object] = {"aging_buckets": {}}
    aging: dict[str, Decimal] = {}

    for index, line in enumerate(lines):
        next_line = lines[index + 1] if index + 1 < len(lines) else ""
        for field, labels in FIELD_LABELS.items():
            if parsed.get(field) is not None:
                continue
            value = _value_on_same_line(line, labels)
            if value is None and _line_matches_label(line, labels):
                value = _parse_currency_token(next_line)
            if value is not None:
                parsed[field] = value

        for bucket, labels in AGING_LABELS.items():
            if bucket in aging:
                continue
            value = _value_on_same_line(line, labels)
            if value is None and _line_matches_label(line, labels):
                value = _parse_currency_token(next_line)
            if value is not None:
                aging[bucket] = value

    parsed["aging_buckets"] = aging
    return parsed


def _reconcile_totals(parsed: dict[str, object]) -> tuple[bool, list[str]]:
    limitations: list[str] = []
    total = parsed.get("total_ar")
    patient = parsed.get("patient_ar")
    insurance = parsed.get("insurance_ar")
    if not isinstance(total, Decimal):
        return False, limitations
    if isinstance(patient, Decimal) and isinstance(insurance, Decimal):
        expected = patient + insurance
        if abs(expected - total) > Decimal("0.05"):
            limitations.append("Patient and insurance A/R do not reconcile to total A/R on the report.")
            return False, limitations
    return True, limitations


def _evaluate_freshness(*, report_date: str | None, modified_at_utc: str | None) -> tuple[str, str | None]:
    if not report_date:
        return "unknown", "Report business date could not be determined."
    try:
        report_day = date.fromisoformat(report_date)
    except ValueError:
        return "unknown", "Report business date is not a valid ISO date."

    today = datetime.now(timezone.utc).date()
    max_age = _max_age_days()
    if (today - report_day).days > max_age:
        return "stale", f"Report date {report_date} is older than {max_age} day(s)."

    if modified_at_utc:
        try:
            modified_day = datetime.fromisoformat(modified_at_utc).date()
            if (today - modified_day).days > max_age:
                return "stale", f"Source file modified at {modified_at_utc} exceeds freshness threshold."
        except ValueError:
            pass

    return "current", None


def _candidate_report_paths() -> list[Path]:
    candidates: list[Path] = []
    configured = os.getenv(SOFTDENT_END_OF_DAY_REPORT_PATH_ENV, "").strip()
    if configured:
        candidates.append(Path(configured))

    configured_dir = os.getenv(SOFTDENT_END_OF_DAY_REPORT_DIR_ENV, "").strip()
    search_dirs = []
    if configured_dir:
        search_dirs.append(Path(configured_dir))
    search_dirs.append(_default_eod_report_dir())

    for directory in search_dirs:
        if not directory.exists():
            continue
        for path in sorted(directory.iterdir(), key=lambda item: item.stat().st_mtime, reverse=True):
            if path.is_file() and path.suffix.lower() in SUPPORTED_EOD_SUFFIXES:
                candidates.append(path)

    for directory in search_dirs:
        for name in DEFAULT_EOD_LATEST_NAMES:
            latest = directory / name
            if latest.is_file():
                candidates.append(latest)

    deduped: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved in seen or not resolved.is_file():
            continue
        seen.add(resolved)
        deduped.append(resolved)
    return deduped


def _build_source_ref(report_date: str | None, suffix: str) -> str:
    day = report_date or "unknown"
    return f"softdent_eod:{day}:last_page:{suffix}"


class SoftDentEndOfDayReportAdapter:
    """Inventory and parse Daily End-of-Day report-derived A/R from the last page."""

    def inventory_reports(self) -> list[SoftDentEndOfDayReportInventoryItem]:
        items: list[SoftDentEndOfDayReportInventoryItem] = []
        for path in _candidate_report_paths():
            text = _read_report_text(path)
            last_page = _extract_last_page_text(text)
            report_date = _parse_report_date_from_text(text) or _parse_date_from_filename(path)
            items.append(
                SoftDentEndOfDayReportInventoryItem(
                    source_file=path.name,
                    source_modified_at_utc=_path_modified_at_utc(path),
                    inferred_report_date=report_date,
                    format=path.suffix.lower().lstrip("."),
                    page_count=last_page.page_count,
                )
            )
        return items

    def parse_latest_ar_summary(self) -> SoftDentEndOfDayArSummary:
        candidates = _candidate_report_paths()
        if not candidates:
            return SoftDentEndOfDayArSummary(
                available=False,
                parse_status="missing",
                missing_data_codes=[MISSING_SOFTDENT_EOD_REPORT, "missing_softdent_ar"],
                limitations=["Daily End-of-Day report is not available in the approved import lane."],
            )

        def sort_key(path: Path) -> tuple[str, float]:
            text = _read_report_text(path)
            report_date = _parse_report_date_from_text(text) or _parse_date_from_filename(path) or ""
            return report_date, path.stat().st_mtime

        latest = max(candidates, key=sort_key)
        return self.parse_report(latest)

    def parse_report(self, path: Path | str) -> SoftDentEndOfDayArSummary:
        report_path = Path(path)
        if not report_path.is_file():
            return SoftDentEndOfDayArSummary(
                available=False,
                parse_status="invalid",
                missing_data_codes=[MISSING_SOFTDENT_EOD_REPORT, "missing_softdent_ar"],
                limitations=["Daily End-of-Day report file was not found."],
            )

        if report_path.suffix.lower() not in SUPPORTED_EOD_SUFFIXES:
            return SoftDentEndOfDayArSummary(
                available=False,
                source_file=report_path.name,
                parse_status="invalid",
                missing_data_codes=[MISSING_SOFTDENT_EOD_REPORT, "missing_softdent_ar"],
                limitations=["Daily End-of-Day report format is not supported."],
            )

        text = _read_report_text(report_path)
        if not text.strip():
            return SoftDentEndOfDayArSummary(
                available=False,
                source_file=report_path.name,
                source_modified_at_utc=_path_modified_at_utc(report_path),
                parse_status="invalid",
                missing_data_codes=[MISSING_SOFTDENT_EOD_REPORT, "missing_softdent_ar"],
                limitations=["Daily End-of-Day report text could not be read."],
            )

        last_page = _extract_last_page_text(text)
        if not last_page.text.strip():
            return SoftDentEndOfDayArSummary(
                available=False,
                source_file=report_path.name,
                source_modified_at_utc=_path_modified_at_utc(report_path),
                parse_status="invalid",
                missing_data_codes=[MISSING_SOFTDENT_EOD_REPORT, "missing_softdent_ar"],
                limitations=["Daily End-of-Day report last page could not be extracted."],
            )

        report_date = _parse_report_date_from_text(text) or _parse_date_from_filename(report_path)
        generated_at = _parse_generated_at_from_text(text)
        modified_at = _path_modified_at_utc(report_path)
        office_scope, provider_scope = _extract_scope(text)

        if not report_date:
            return SoftDentEndOfDayArSummary(
                available=False,
                generated_at=generated_at,
                source_file=report_path.name,
                source_modified_at_utc=modified_at,
                freshness_status="unknown",
                parse_status="missing",
                office_scope=office_scope,
                provider_scope=provider_scope,
                page_number=last_page.page_number,
                page_count=last_page.page_count,
                missing_data_codes=[MISSING_SOFTDENT_EOD_REPORT_DATE, "missing_softdent_ar"],
                limitations=["Daily End-of-Day report business date is unavailable; A/R is not exposed."],
            )

        sections = _locate_ar_sections(last_page.text)
        if not sections:
            return SoftDentEndOfDayArSummary(
                available=False,
                report_date=report_date,
                generated_at=generated_at,
                source_file=report_path.name,
                source_modified_at_utc=modified_at,
                freshness_status="unknown",
                parse_status="missing",
                office_scope=office_scope,
                provider_scope=provider_scope,
                page_number=last_page.page_number,
                page_count=last_page.page_count,
                missing_data_codes=["missing_softdent_ar"],
                limitations=["Daily End-of-Day report last page does not contain a recognizable A/R section."],
            )

        if len(sections) > 1:
            return SoftDentEndOfDayArSummary(
                available=False,
                report_date=report_date,
                generated_at=generated_at,
                source_file=report_path.name,
                source_modified_at_utc=modified_at,
                freshness_status="unknown",
                parse_status="invalid",
                office_scope=office_scope,
                provider_scope=provider_scope,
                page_number=last_page.page_number,
                page_count=last_page.page_count,
                missing_data_codes=["missing_softdent_ar"],
                limitations=["Daily End-of-Day report last page has ambiguous A/R sections."],
            )

        parsed = _parse_ar_section(sections[0])
        total_ar = parsed.get("total_ar")
        if not isinstance(total_ar, Decimal):
            return SoftDentEndOfDayArSummary(
                available=False,
                report_date=report_date,
                generated_at=generated_at,
                source_file=report_path.name,
                source_modified_at_utc=modified_at,
                freshness_status="unknown",
                parse_status="missing",
                office_scope=office_scope,
                provider_scope=provider_scope,
                page_number=last_page.page_number,
                page_count=last_page.page_count,
                missing_data_codes=["missing_softdent_ar"],
                limitations=["Daily End-of-Day report A/R total is missing; HAL will not invent a balance."],
            )

        reconciled, reconcile_limits = _reconcile_totals(parsed)
        freshness_status, stale_reason = _evaluate_freshness(report_date=report_date, modified_at_utc=modified_at)

        aging_buckets = parsed.get("aging_buckets")
        if not isinstance(aging_buckets, dict):
            aging_buckets = {}

        source_refs = [
            _build_source_ref(report_date, "ar_summary"),
        ]
        if aging_buckets:
            source_refs.append(_build_source_ref(report_date, "aging_buckets"))

        limitations = [
            "Report-derived A/R from the Daily End-of-Day report last page only; not patient-level ledger access.",
        ]
        limitations.extend(reconcile_limits)

        if freshness_status == "stale":
            limitations.append("Daily End-of-Day report A/R is stale and must not drive patient prep or attention silently.")
            return SoftDentEndOfDayArSummary(
                available=False,
                report_date=report_date,
                generated_at=generated_at,
                source_file=report_path.name,
                source_modified_at_utc=modified_at,
                freshness_status="stale",
                parse_status="stale",
                total_ar=total_ar,
                patient_ar=parsed.get("patient_ar") if isinstance(parsed.get("patient_ar"), Decimal) else None,
                insurance_ar=parsed.get("insurance_ar") if isinstance(parsed.get("insurance_ar"), Decimal) else None,
                aging_buckets={key: value for key, value in aging_buckets.items() if isinstance(value, Decimal)},
                credits=parsed.get("credits") if isinstance(parsed.get("credits"), Decimal) else None,
                collection_total=parsed.get("collection_total") if isinstance(parsed.get("collection_total"), Decimal) else None,
                production_total=parsed.get("production_total") if isinstance(parsed.get("production_total"), Decimal) else None,
                office_scope=office_scope,
                provider_scope=provider_scope,
                source_refs=source_refs,
                missing_data_codes=["missing_softdent_ar"],
                limitations=limitations,
                stale_reason=stale_reason,
                page_number=last_page.page_number,
                page_count=last_page.page_count,
            )

        parse_status: Literal["available", "limited"] = "available" if reconciled else "limited"
        if parse_status == "limited":
            limitations.append("Parsed A/R fields are limited because totals do not fully reconcile.")

        return SoftDentEndOfDayArSummary(
            available=True,
            report_date=report_date,
            generated_at=generated_at,
            source_file=report_path.name,
            source_modified_at_utc=modified_at,
            freshness_status=freshness_status,
            parse_status=parse_status,
            total_ar=total_ar,
            patient_ar=parsed.get("patient_ar") if isinstance(parsed.get("patient_ar"), Decimal) else None,
            insurance_ar=parsed.get("insurance_ar") if isinstance(parsed.get("insurance_ar"), Decimal) else None,
            aging_buckets={key: value for key, value in aging_buckets.items() if isinstance(value, Decimal)},
            credits=parsed.get("credits") if isinstance(parsed.get("credits"), Decimal) else None,
            collection_total=parsed.get("collection_total") if isinstance(parsed.get("collection_total"), Decimal) else None,
            production_total=parsed.get("production_total") if isinstance(parsed.get("production_total"), Decimal) else None,
            office_scope=office_scope,
            provider_scope=provider_scope,
            source_refs=source_refs,
            missing_data_codes=[],
            limitations=limitations,
            stale_reason=stale_reason,
            page_number=last_page.page_number,
            page_count=last_page.page_count,
        )


_ADAPTER_SINGLETON: SoftDentEndOfDayReportAdapter | None = None


def get_softdent_end_of_day_report_adapter() -> SoftDentEndOfDayReportAdapter:
    global _ADAPTER_SINGLETON
    if _ADAPTER_SINGLETON is None:
        _ADAPTER_SINGLETON = SoftDentEndOfDayReportAdapter()
    return _ADAPTER_SINGLETON
