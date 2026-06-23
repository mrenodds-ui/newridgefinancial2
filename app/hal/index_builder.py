from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Any

from app.services import get_kpi_data

from .financial_tools import build_financial_snapshot_documents
from .sanitization import sanitize_hal_text
from .storage import get_hal_storage_path
from .vector_store import rebuild_hal_collection


BASE_SOURCE_FILES = (
    Path(__file__).resolve().parents[2] / "README.md",
    Path(__file__).resolve().parents[2] / "docs" / "API.md",
    Path(__file__).resolve().parents[2] / "docs" / "hal_phi_rag_architecture.md",
    Path(__file__).resolve().parents[2] / "docs" / "hal_auth_audit_plan.md",
    Path(__file__).resolve().parents[2] / "docs" / "softdent_bridge_automation.md",
)

ACCOUNTING_DOCS_DIR = Path(__file__).resolve().parents[2] / "docs" / "accounting"


def _get_document_source_files() -> list[Path]:
    accounting_source_files = sorted(ACCOUNTING_DOCS_DIR.glob("*.md")) if ACCOUNTING_DOCS_DIR.exists() else []
    return [*BASE_SOURCE_FILES, *accounting_source_files]


def _chunk_markdown(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    contents = path.read_text(encoding="utf-8")
    chunks = [chunk.strip() for chunk in re.split(r"\n\s*\n", contents) if chunk.strip()]
    built_chunks: list[dict[str, str]] = []
    for index, chunk in enumerate(chunks, start=1):
        sanitized = sanitize_hal_text(chunk)
        sanitized_text = str(sanitized["sanitized_text"])
        built_chunks.append(
            {
                "source_id": f"{path.stem}-{index}",
                "title": f"{path.stem} chunk {index}",
                "category": "documentation",
                "sanitized_content": sanitized_text,
            }
        )
    return built_chunks


def _build_kpi_documents() -> list[dict[str, str]]:
    built_at = datetime.now(timezone.utc).date().isoformat()
    kpis = get_kpi_data()
    summary_lines = [f"{item['name']}: {item['value']}" for item in kpis]
    content = (
        f"Current calculated KPI snapshot as of {built_at}. "
        + " ".join(summary_lines)
        + " HAL should use these values as financial context rather than patient-level raw records."
    )
    sanitized = sanitize_hal_text(content)
    sanitized_text = str(sanitized["sanitized_text"])
    return [
        {
            "source_id": "kpi-current-summary",
            "title": "Current KPI summary",
            "category": "kpi",
            "sanitized_content": sanitized_text,
        }
    ]


def _build_local_hal_document_bundle() -> tuple[list[dict[str, str]], int]:
    source_files = _get_document_source_files()
    kpi_documents = _build_kpi_documents()
    financial_documents = build_financial_snapshot_documents()

    documents: list[dict[str, str]] = []
    for source_path in source_files:
        documents.extend(_chunk_markdown(source_path))
    documents.extend(kpi_documents)
    documents.extend(financial_documents)

    source_count = len(source_files) + len(kpi_documents) + len(financial_documents)
    return documents, source_count


def build_local_hal_documents() -> list[dict[str, str]]:
    documents, _source_count = _build_local_hal_document_bundle()
    return documents


def refresh_hal_index() -> dict[str, Any]:
    documents, source_count = _build_local_hal_document_bundle()
    metadata = rebuild_hal_collection(documents)
    metadata["refreshed_at_utc"] = datetime.now(timezone.utc).isoformat()
    metadata["source_count"] = source_count
    metadata["storage_path"] = str(get_hal_storage_path())
    return metadata