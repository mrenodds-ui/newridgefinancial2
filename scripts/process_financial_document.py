from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path

from pdfminer.high_level import extract_text as extract_pdf_text


SUPPORTED_EXTENSIONS = {
    ".bmp",
    ".jpeg",
    ".jpg",
    ".pdf",
    ".png",
    ".tif",
    ".tiff",
    ".txt",
}

AMOUNT_LINE_PATTERNS = {
    "total_amount": re.compile(r"\b(total|amount due|balance due|grand total|net amount)\b", re.IGNORECASE),
    "subtotal_amount": re.compile(r"\b(subtotal|sub total)\b", re.IGNORECASE),
    "tax_amount": re.compile(r"\b(tax|sales tax)\b", re.IGNORECASE),
}
INVOICE_NUMBER_PATTERN = re.compile(
    r"\b(?:invoice|inv|receipt|statement)\s*(?:number|no\.?|#)?\s*[:#-]?\s*([A-Z0-9-]{4,})\b",
    re.IGNORECASE,
)
DATE_PATTERN = re.compile(r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2})\b")
AMOUNT_PATTERN = re.compile(r"\(?\$?\s*-?\d{1,3}(?:,\d{3})*(?:\.\d{2})\)?|\(?\$?\s*-?\d+(?:\.\d{2})\)?")
OCR_DATE_CONFUSIONS = {
    "0": ("6", "8"),
    "3": ("8",),
    "6": ("0", "8"),
    "8": ("0", "6"),
}
VENDOR_WORD_NORMALIZATIONS = {
    "DENTAI": "Dental",
    "DENTAL": "Dental",
    "SUPPIY": "Supply",
    "SUPPLY": "Supply",
    "LAB0RATORY": "Laboratory",
    "LABORAT0RY": "Laboratory",
    "LABORATORY": "Laboratory",
    "SERVlCES": "Services",
    "SERVICES": "Services",
    "CLlNIC": "Clinic",
    "CLINIC": "Clinic",
    "ASS0CIATES": "Associates",
    "ASSOCIATES": "Associates",
    "C0MPANY": "Company",
    "COMPANY": "Company",
    "L_L_C": "LLC",
    "LTD": "Ltd",
    "INC": "Inc",
}


@dataclass(frozen=True)
class VendorRulePattern:
    pattern: str
    normalized: str


@dataclass(frozen=True)
class InvoiceLayoutRule:
    vendor: str
    prefix: str
    date_suffix_format: str


@dataclass
class ExtractedFinancialDocument:
    source_path: str
    source_name: str
    sha256: str
    processed_at_utc: str
    extractor: str
    document_type: str
    vendor_name: str | None
    invoice_number: str | None
    document_date: str | None
    total_amount: float | None
    subtotal_amount: float | None
    tax_amount: float | None
    currency: str
    text_preview: str
    raw_text: str
    correction_flags: list[str]
    confidence_label: str
    review_required: bool


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


@lru_cache(maxsize=1)
def load_vendor_rules() -> tuple[dict[str, str], list[VendorRulePattern], list[InvoiceLayoutRule]]:
    rules_path = project_root() / "scripts" / "local_accounting_vendor_rules.json"
    if not rules_path.exists():
        return {}, [], []

    payload = json.loads(rules_path.read_text(encoding="utf-8"))
    aliases = {
        str(key).upper(): str(value)
        for key, value in dict(payload.get("vendor_aliases") or {}).items()
        if str(key).strip() and str(value).strip()
    }
    patterns = [
        VendorRulePattern(pattern=str(item.get("pattern") or ""), normalized=str(item.get("normalized") or ""))
        for item in list(payload.get("vendor_match_patterns") or [])
        if str(item.get("pattern") or "").strip() and str(item.get("normalized") or "").strip()
    ]
    layouts = [
        InvoiceLayoutRule(
            vendor=str(item.get("vendor") or ""),
            prefix=str(item.get("prefix") or ""),
            date_suffix_format=str(item.get("date_suffix_format") or ""),
        )
        for item in list(payload.get("invoice_layout_rules") or [])
        if str(item.get("vendor") or "").strip() and str(item.get("prefix") or "").strip()
    ]
    return aliases, patterns, layouts


def windows_binary_candidates() -> dict[str, tuple[str, ...]]:
    return {
        "ocrmypdf": (
            str(project_root() / ".venv" / "Scripts" / "ocrmypdf.exe"),
            str(Path(sys.executable).resolve().parent / "ocrmypdf.exe"),
        ),
        "tesseract": (
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        ),
        "qpdf": (
            r"C:\Program Files\qpdf\bin\qpdf.exe",
            r"C:\Program Files\qpdf 12.3.2\bin\qpdf.exe",
        ),
    }


def default_db_path() -> Path:
    configured = os.getenv("LOCAL_AI_ACCOUNTING_DB_PATH", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()

    hal_path = os.getenv("HAL_SQLITE_PATH", "").strip()
    if hal_path:
        return Path(hal_path).expanduser().resolve()

    return project_root() / "hal_local.sqlite3"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract local OCR text from a receipt, invoice, bank statement, or text file and persist a normalized summary into SQLite.",
    )
    parser.add_argument("--input", required=True, help="Path to a PDF, image, or .txt file.")
    parser.add_argument("--db-path", default=str(default_db_path()), help="SQLite database path for normalized document storage.")
    parser.add_argument("--json-output", help="Optional path for a JSON copy of the normalized document record.")
    parser.add_argument("--skip-db", action="store_true", help="Do not write the normalized record into SQLite.")
    parser.add_argument("--print-text", action="store_true", help="Print extracted raw text to stdout after the JSON summary.")
    return parser.parse_args()


def compute_sha256(file_path: Path) -> str:
    digest = hashlib.sha256()
    with file_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ensure_database(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS local_accounting_documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_path TEXT NOT NULL,
                source_name TEXT NOT NULL,
                sha256 TEXT NOT NULL UNIQUE,
                processed_at_utc TEXT NOT NULL,
                extractor TEXT NOT NULL,
                document_type TEXT NOT NULL,
                vendor_name TEXT,
                invoice_number TEXT,
                document_date TEXT,
                total_amount REAL,
                subtotal_amount REAL,
                tax_amount REAL,
                currency TEXT NOT NULL,
                text_preview TEXT NOT NULL,
                raw_text TEXT NOT NULL,
                correction_flags_json TEXT NOT NULL DEFAULT '[]',
                confidence_label TEXT NOT NULL DEFAULT 'manual review',
                review_required INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        existing_columns = {
            str(row[1])
            for row in connection.execute("PRAGMA table_info(local_accounting_documents)").fetchall()
        }
        if "correction_flags_json" not in existing_columns:
            connection.execute("ALTER TABLE local_accounting_documents ADD COLUMN correction_flags_json TEXT NOT NULL DEFAULT '[]'")
        if "confidence_label" not in existing_columns:
            connection.execute("ALTER TABLE local_accounting_documents ADD COLUMN confidence_label TEXT NOT NULL DEFAULT 'manual review'")
        if "review_required" not in existing_columns:
            connection.execute("ALTER TABLE local_accounting_documents ADD COLUMN review_required INTEGER NOT NULL DEFAULT 0")
        connection.commit()


def write_document_record(db_path: Path, document: ExtractedFinancialDocument) -> None:
    ensure_database(db_path)
    payload = asdict(document)
    payload["correction_flags_json"] = json.dumps(document.correction_flags)
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            INSERT INTO local_accounting_documents (
                source_path,
                source_name,
                sha256,
                processed_at_utc,
                extractor,
                document_type,
                vendor_name,
                invoice_number,
                document_date,
                total_amount,
                subtotal_amount,
                tax_amount,
                currency,
                text_preview,
                raw_text,
                correction_flags_json,
                confidence_label,
                review_required
            ) VALUES (
                :source_path,
                :source_name,
                :sha256,
                :processed_at_utc,
                :extractor,
                :document_type,
                :vendor_name,
                :invoice_number,
                :document_date,
                :total_amount,
                :subtotal_amount,
                :tax_amount,
                :currency,
                :text_preview,
                :raw_text,
                :correction_flags_json,
                :confidence_label,
                :review_required
            )
            ON CONFLICT(sha256) DO UPDATE SET
                processed_at_utc=excluded.processed_at_utc,
                extractor=excluded.extractor,
                document_type=excluded.document_type,
                vendor_name=excluded.vendor_name,
                invoice_number=excluded.invoice_number,
                document_date=excluded.document_date,
                total_amount=excluded.total_amount,
                subtotal_amount=excluded.subtotal_amount,
                tax_amount=excluded.tax_amount,
                currency=excluded.currency,
                text_preview=excluded.text_preview,
                raw_text=excluded.raw_text,
                correction_flags_json=excluded.correction_flags_json,
                confidence_label=excluded.confidence_label,
                review_required=excluded.review_required
            """,
            payload,
        )
        connection.commit()


def build_correction_flags(
    *,
    raw_text: str,
    vendor_name: str | None,
    invoice_number: str | None,
    document_date: str | None,
) -> list[str]:
    flags: list[str] = []
    raw_upper = raw_text.upper()
    if vendor_name and vendor_name.upper() not in raw_upper:
        flags.append("vendor_normalized")
    if invoice_number and invoice_number.upper() not in raw_upper:
        flags.append("invoice_corrected")
    if document_date and document_date.upper() not in raw_upper:
        flags.append("date_corrected")
    return flags


def build_confidence_label(*, extractor: str, raw_text: str, correction_flags: list[str]) -> str:
    correction_count = len(correction_flags)
    if correction_count > 2:
        return "manual review"
    if correction_count > 0:
        return "review suggested"
    if extractor in {"plain_text", "pdf_text"}:
        return "high confidence"
    if len(raw_text.strip()) > 40:
        return "medium confidence"
    return "review suggested"


def resolve_executable(name: str) -> str | None:
    resolved = shutil.which(name)
    if resolved:
        return resolved

    for candidate in windows_binary_candidates().get(name, ()): 
        if candidate and Path(candidate).exists():
            return candidate
    return None


def build_subprocess_env() -> dict[str, str]:
    env = dict(os.environ)
    path_entries = env.get("PATH", "").split(os.pathsep) if env.get("PATH") else []
    for executable_name in ("tesseract", "qpdf"):
        resolved = resolve_executable(executable_name)
        if not resolved:
            continue
        binary_dir = str(Path(resolved).resolve().parent)
        if binary_dir not in path_entries:
            path_entries.insert(0, binary_dir)
    env["PATH"] = os.pathsep.join(path_entries)
    return env


def run_command(command: list[str], *, env: dict[str, str] | None = None) -> str:
    completed = subprocess.run(command, capture_output=True, text=True, check=False, env=env)
    if completed.returncode != 0:
        stderr = completed.stderr.strip() or completed.stdout.strip() or f"Command failed: {' '.join(command)}"
        raise RuntimeError(stderr)
    return completed.stdout


def extract_text(file_path: Path) -> tuple[str, str]:
    suffix = file_path.suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported input type: {suffix or '[no extension]'}")

    if suffix == ".txt":
        return file_path.read_text(encoding="utf-8", errors="ignore"), "plain_text"

    subprocess_env = build_subprocess_env()

    if suffix == ".pdf":
        ocrmypdf_path = resolve_executable("ocrmypdf")
        if not ocrmypdf_path:
            raise RuntimeError("ocrmypdf is not installed or could not be located. Install it to OCR PDF documents locally.")

        with tempfile.TemporaryDirectory(prefix="financial-ocr-") as temp_dir:
            temp_path = Path(temp_dir)
            output_pdf = temp_path / "ocr_output.pdf"
            sidecar_txt = temp_path / "ocr_sidecar.txt"
            command = [
                ocrmypdf_path,
                "--skip-text",
                "--sidecar",
                str(sidecar_txt),
                str(file_path),
                str(output_pdf),
            ]
            run_command(command, env=subprocess_env)
            if not sidecar_txt.exists():
                raise RuntimeError("ocrmypdf completed without a sidecar text file.")
            sidecar_text = sidecar_txt.read_text(encoding="utf-8", errors="ignore")
            if sidecar_text.strip() and "[OCR skipped on page(s)" not in sidecar_text:
                return sidecar_text, "ocrmypdf"

            embedded_text = extract_pdf_text(str(file_path)).strip()
            if embedded_text:
                return embedded_text, "pdf_text"
            return sidecar_text, "ocrmypdf"

    tesseract_path = resolve_executable("tesseract")
    if not tesseract_path:
        raise RuntimeError("tesseract is not installed or could not be located. Install it to OCR image receipts locally.")

    text = run_command([tesseract_path, str(file_path), "stdout", "--psm", "6"], env=subprocess_env)
    return text, "tesseract"


def clean_line(line: str) -> str:
    cleaned = line.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    cleaned = cleaned.replace("—", "-").replace("–", "-")
    cleaned = re.sub(r"^[^A-Za-z0-9$#(]+", "", cleaned)
    cleaned = re.sub(r"\b([A-Z]{3,})(20\d{2}-\d{2,4})\b", r"\1-\2", cleaned)
    return re.sub(r"\s+", " ", cleaned.strip())


def parse_amount(raw_value: str) -> float | None:
    cleaned = raw_value.replace("$", "").replace(",", "").replace(" ", "")
    if not cleaned:
        return None
    is_negative = cleaned.startswith("(") and cleaned.endswith(")")
    cleaned = cleaned.strip("()")
    try:
        value = float(cleaned)
    except ValueError:
        return None
    return -value if is_negative else value


def detect_document_type(text: str) -> str:
    lowered = text.lower()
    if "bank statement" in lowered or "account summary" in lowered:
        return "bank_statement"
    if "invoice" in lowered or "amount due" in lowered:
        return "invoice"
    if "receipt" in lowered or "thank you for your payment" in lowered:
        return "receipt"
    return "financial_document"


def detect_vendor_name(lines: list[str]) -> str | None:
    for line in lines[:8]:
        if not line:
            continue
        if re.search(r"[^\x20-\x7E]", line):
            continue
        if any(token in line.lower() for token in ("invoice", "receipt", "statement", "date", "phone", "www.")):
            continue
        if len(line) < 3:
            continue
        return normalize_vendor_name(line[:160])
    return None


def _vendor_lookup_candidates(value: str) -> list[str]:
    candidates: list[str] = []

    def add(candidate: str) -> None:
        normalized = re.sub(r"\s+", " ", candidate).strip(" -.,")
        if normalized and normalized not in candidates:
            candidates.append(normalized)

    add(value)

    tokens = value.split()
    if tokens:
        digit_letter_swaps = str.maketrans({
            "0": "O",
            "1": "I",
            "5": "S",
            "8": "B",
        })
        add(" ".join(token.translate(digit_letter_swaps) for token in tokens))

        lowercase_l_fixed = []
        for token in tokens:
            alpha_chars = [character for character in token if character.isalpha()]
            uppercase_chars = [character for character in alpha_chars if character.isupper()]
            if "l" in token and alpha_chars and len(uppercase_chars) >= max(1, len(alpha_chars) - 1):
                lowercase_l_fixed.append(token.replace("l", "I"))
            else:
                lowercase_l_fixed.append(token)
        add(" ".join(lowercase_l_fixed))

        ambiguous_i_fixed = []
        for token in tokens:
            if token.isupper() and len(token) >= 5 and "I" in token:
                ambiguous_i_fixed.append(token.replace("I", "L"))
            else:
                ambiguous_i_fixed.append(token)
        add(" ".join(ambiguous_i_fixed))

        ambiguous_o_fixed = []
        for token in tokens:
            if any(character.isdigit() for character in token) and "O" in token:
                ambiguous_o_fixed.append(token.replace("O", "0"))
            else:
                ambiguous_o_fixed.append(token)
        add(" ".join(ambiguous_o_fixed))

        ambiguous_s_fixed = []
        for token in tokens:
            if token.isupper() and len(token) >= 4 and "S" in token:
                ambiguous_s_fixed.append(token.replace("S", "5"))
            else:
                ambiguous_s_fixed.append(token)
        add(" ".join(ambiguous_s_fixed))

    return candidates


def normalize_vendor_name(value: str) -> str:
    cleaned = value.encode("ascii", errors="ignore").decode("ascii")
    cleaned = re.sub(r"[^A-Za-z0-9&.,'\- ]+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -.,")
    alias_rules, pattern_rules, _ = load_vendor_rules()
    for candidate in _vendor_lookup_candidates(cleaned):
        direct_alias = alias_rules.get(candidate.upper())
        if direct_alias:
            return direct_alias
        for rule in pattern_rules:
            if re.search(rule.pattern, candidate):
                return rule.normalized
    tokens = []
    for token in cleaned.split():
        token_key = token.upper().replace(".", "").replace("-", "_")
        if token_key in VENDOR_WORD_NORMALIZATIONS:
            tokens.append(VENDOR_WORD_NORMALIZATIONS[token_key])
            continue
        if token.isupper() and len(token) <= 4:
            tokens.append(token)
            continue
        tokens.append(token.capitalize())
    normalized = " ".join(tokens).strip()
    return normalized or value.strip()


def normalize_invoice_number(value: str, document_date: str | None = None, vendor_name: str | None = None) -> str:
    normalized = value.strip().replace(" ", "")
    normalized = normalized.replace(":", "-").replace("/", "-")
    normalized = re.sub(r"[^A-Z0-9-]", "", normalized.upper())
    normalized = re.sub(r"(?<=[A-Z])(?=20\d{2}-\d{2,4}\b)", "-", normalized)
    normalized = re.sub(r"-{2,}", "-", normalized).strip("-")
    _, _, layout_rules = load_vendor_rules()
    for rule in layout_rules:
      if vendor_name and vendor_name.lower() == rule.vendor.lower() and normalized.startswith(rule.prefix.upper()):
            if document_date and rule.date_suffix_format == "YYYY-MMDD":
                parsed_date = _parse_date_token(document_date)
                if parsed_date:
                    normalized = f"{rule.prefix.upper()}-{parsed_date.strftime('%Y-%m%d')}"
            break
    if document_date:
        parsed_date = _parse_date_token(document_date)
        if parsed_date:
            normalized = re.sub(
                r"(20\d{2})-(\d{4})$",
                lambda match: f"{match.group(1)}-{parsed_date.strftime('%m%d')}",
                normalized,
            )
    return normalized


def detect_invoice_number(lines: list[str], text: str, document_date: str | None = None, vendor_name: str | None = None) -> str | None:
    for line in lines:
        if "invoice" not in line.lower() and "receipt" not in line.lower() and "statement" not in line.lower():
            continue
        invoice_tail = re.split(r"invoice|receipt|statement", line, maxsplit=1, flags=re.IGNORECASE)[-1].strip(" :-#")
        if invoice_tail:
            return normalize_invoice_number(invoice_tail, document_date=document_date, vendor_name=vendor_name)
        match = INVOICE_NUMBER_PATTERN.search(line)
        if match:
            return normalize_invoice_number(match.group(1), document_date=document_date, vendor_name=vendor_name)
    match = INVOICE_NUMBER_PATTERN.search(text)
    return normalize_invoice_number(match.group(1), document_date=document_date, vendor_name=vendor_name) if match else None


def _parse_date_token(raw_value: str) -> datetime | None:
    normalized = raw_value.replace("-", "/") if "/" in raw_value or raw_value.count("-") == 2 else raw_value
    for date_format in ("%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d"):
        try:
            return datetime.strptime(normalized, date_format)
        except ValueError:
            continue
    return None


def _candidate_dates_from_ocr_confusions(raw_value: str) -> list[str]:
    candidates = {raw_value}
    for index, character in enumerate(raw_value):
        for replacement in OCR_DATE_CONFUSIONS.get(character, ()): 
            candidates.add(f"{raw_value[:index]}{replacement}{raw_value[index + 1:]}")
    if len(raw_value) >= 2:
        for first_index, first_character in enumerate(raw_value):
            first_replacements = OCR_DATE_CONFUSIONS.get(first_character, ())
            if not first_replacements:
                continue
            for second_index in range(first_index + 1, len(raw_value)):
                second_character = raw_value[second_index]
                second_replacements = OCR_DATE_CONFUSIONS.get(second_character, ())
                if not second_replacements:
                    continue
                for first_replacement in first_replacements:
                    for second_replacement in second_replacements:
                        mutated = list(raw_value)
                        mutated[first_index] = first_replacement
                        mutated[second_index] = second_replacement
                        candidates.add("".join(mutated))
    return list(candidates)


def _choose_best_date_token(raw_value: str) -> str | None:
    now = datetime.now()
    parsed_original = _parse_date_token(raw_value)
    if parsed_original and parsed_original <= now + timedelta(days=30):
        return raw_value

    valid_candidates: list[tuple[datetime, str]] = []
    for candidate in _candidate_dates_from_ocr_confusions(raw_value):
        parsed = _parse_date_token(candidate)
        if parsed is None:
            continue
        if parsed > now + timedelta(days=30):
            continue
        if parsed < now - timedelta(days=3650):
            continue
        valid_candidates.append((parsed, candidate))

    if not valid_candidates:
        return raw_value if parsed_original else None

    valid_candidates.sort(key=lambda item: (abs((now - item[0]).days), item[0]))
    return valid_candidates[0][1]


def detect_document_date(lines: list[str], text: str) -> str | None:
    prioritized_lines = [line for line in lines if "date" in line.lower()] + [line for line in lines if "date" not in line.lower()]
    for line in prioritized_lines:
        match = DATE_PATTERN.search(line)
        if not match:
            continue
        best_token = _choose_best_date_token(match.group(1))
        if best_token:
            return best_token
    match = DATE_PATTERN.search(text)
    if not match:
        return None
    return _choose_best_date_token(match.group(1))


def detect_amount_from_lines(lines: list[str], pattern: re.Pattern[str]) -> float | None:
    for line in lines:
        if not pattern.search(line):
            continue
        amounts = [parse_amount(match.group(0)) for match in AMOUNT_PATTERN.finditer(line)]
        amounts = [value for value in amounts if value is not None]
        if amounts:
            return amounts[-1]
    return None


def normalize_document(file_path: Path, raw_text: str, extractor: str) -> ExtractedFinancialDocument:
    lines = [clean_line(line) for line in raw_text.splitlines()]
    non_empty_lines = [line for line in lines if line]
    collapsed_text = "\n".join(non_empty_lines)
    preview = "\n".join(non_empty_lines[:12])[:1200]
    document_date = detect_document_date(non_empty_lines, collapsed_text)
    vendor_name = detect_vendor_name(non_empty_lines)
    invoice_number = detect_invoice_number(non_empty_lines, collapsed_text, document_date=document_date, vendor_name=vendor_name)
    correction_flags = build_correction_flags(
        raw_text=collapsed_text,
        vendor_name=vendor_name,
        invoice_number=invoice_number,
        document_date=document_date,
    )
    confidence_label = build_confidence_label(extractor=extractor, raw_text=collapsed_text, correction_flags=correction_flags)
    return ExtractedFinancialDocument(
        source_path=str(file_path.resolve()),
        source_name=file_path.name,
        sha256=compute_sha256(file_path),
        processed_at_utc=datetime.now(timezone.utc).isoformat(),
        extractor=extractor,
        document_type=detect_document_type(collapsed_text),
        vendor_name=vendor_name,
        invoice_number=invoice_number,
        document_date=document_date,
        total_amount=detect_amount_from_lines(non_empty_lines, AMOUNT_LINE_PATTERNS["total_amount"]),
        subtotal_amount=detect_amount_from_lines(non_empty_lines, AMOUNT_LINE_PATTERNS["subtotal_amount"]),
        tax_amount=detect_amount_from_lines(non_empty_lines, AMOUNT_LINE_PATTERNS["tax_amount"]),
        currency="USD",
        text_preview=preview,
        raw_text=collapsed_text,
        correction_flags=correction_flags,
        confidence_label=confidence_label,
        review_required=bool(correction_flags),
    )


def write_json_output(output_path: Path, document: ExtractedFinancialDocument) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(asdict(document), indent=2), encoding="utf-8")


def main() -> int:
    args = parse_args()
    input_path = Path(args.input).expanduser().resolve()
    if not input_path.exists() or not input_path.is_file():
        raise FileNotFoundError(f"Input file does not exist: {input_path}")

    raw_text, extractor = extract_text(input_path)
    document = normalize_document(input_path, raw_text, extractor)
    if args.json_output:
        write_json_output(Path(args.json_output).expanduser().resolve(), document)
    if not args.skip_db:
        write_document_record(Path(args.db_path).expanduser().resolve(), document)

    print(json.dumps(asdict(document), indent=2))
    if args.print_text:
        print(document.raw_text)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)