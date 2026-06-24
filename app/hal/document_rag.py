from __future__ import annotations

from contextlib import suppress
import hashlib
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import chromadb
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader

from app.config_runtime import get_env_setting
from app.ai_local_config import (
    LocalAIConfigError,
    load_local_model_profile_config,
    require_lane_runtime,
    resolve_lane_profile,
)
from app.evaluation.client import generate_response_result

from .audit import record_hal_audit
from .sanitization import sanitize_hal_text
from .safety import append_ai_activity_log, ensure_within_ai_workspace, get_ai_workspace_path, workspace_relative_path
from .storage import hal_connection
from .vector_store import get_embedding_function


DOCUMENT_RAG_MODE = "langchain-document-rag-v1"
DOCUMENT_RAG_COLLECTION_NAME = "hal_document_rag"
from app.ai_local_config import get_frontend_base_url

DEFAULT_OLLAMA_BASE_URL = get_frontend_base_url()
DEFAULT_DOCUMENT_RAG_LLM_BASE_URL = os.getenv("LITELLM_PROXY_BASE_URL", DEFAULT_OLLAMA_BASE_URL)
LOCAL_MODEL_PROFILE_CONFIG_PATH = Path(__file__).resolve().parents[2] / "evals" / "local_model_profiles.json"
SUPPORTED_EXTENSIONS = {".csv", ".json", ".md", ".pdf", ".txt"}
DOCUMENT_GUARDRAILS = [
    "uploaded files only",
    "grounded answer only",
    "insufficient context fallback",
    "audit log recorded",
]
INSUFFICIENT_DOCUMENT_CONTEXT_ANSWER = "I do not have enough grounded context in the uploaded files to answer that."
INVALID_PDF_ERROR_MESSAGE = "The uploaded PDF is invalid or unreadable."


def _slugify_file_name(source_name: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "-", source_name).strip("-.")
    return sanitized[:120] or "document.txt"


def _document_rag_root() -> Path:
    configured = get_env_setting("HAL_DOCUMENT_RAG_ROOT", "").strip()
    candidate = Path(configured) if configured else (get_ai_workspace_path() / "document_rag")
    root = ensure_within_ai_workspace(candidate)
    root.mkdir(parents=True, exist_ok=True)
    return root


def get_document_rag_upload_dir() -> Path:
    upload_dir = ensure_within_ai_workspace(_document_rag_root() / "uploads")
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir


def get_document_rag_chroma_path() -> Path:
    configured = get_env_setting("HAL_DOCUMENT_RAG_CHROMA_PATH", "").strip()
    candidate = Path(configured) if configured else (_document_rag_root() / "chroma")
    chroma_path = ensure_within_ai_workspace(candidate)
    chroma_path.mkdir(parents=True, exist_ok=True)
    return chroma_path


def get_document_rag_client() -> chromadb.ClientAPI:
    return chromadb.PersistentClient(path=str(get_document_rag_chroma_path()))


def get_document_rag_collection() -> chromadb.Collection:
    client = get_document_rag_client()
    return client.get_or_create_collection(
        name=DOCUMENT_RAG_COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
        embedding_function=get_embedding_function(),
    )


def _ensure_document_rag_schema(connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS hal_document_rag_documents (
            document_id TEXT PRIMARY KEY,
            source_name TEXT NOT NULL,
            stored_path TEXT NOT NULL,
            mime_type TEXT NOT NULL,
            sha256 TEXT NOT NULL,
            uploaded_at_utc TEXT NOT NULL,
            uploaded_by TEXT NOT NULL,
            page_count INTEGER NOT NULL,
            chunk_count INTEGER NOT NULL,
            content_char_count INTEGER NOT NULL
        )
        """
    )
    connection.execute(
        "DROP INDEX IF EXISTS idx_hal_document_rag_documents_source_name"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_hal_document_rag_documents_source_name ON hal_document_rag_documents(source_name)"
    )


def _decode_text_bytes(content: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="ignore")


def _load_source_documents(file_path: Path, content: bytes, source_name: str) -> tuple[list[Document], int]:
    extension = file_path.suffix.lower()
    if extension == ".pdf":
        safe_file_path = ensure_within_ai_workspace(file_path)
        try:
            reader = PdfReader(str(safe_file_path))
            documents: list[Document] = []
            for page_index, page in enumerate(reader.pages, start=1):
                page_text = (page.extract_text() or "").strip()
                if not page_text:
                    continue
                documents.append(
                    Document(
                        page_content=page_text,
                        metadata={
                            "source_name": source_name,
                            "page_number": page_index,
                        },
                    )
                )
            return documents, len(reader.pages)
        except Exception as exc:
            raise ValueError(INVALID_PDF_ERROR_MESSAGE) from exc

    text = _decode_text_bytes(content).strip()
    if not text:
        return [], 1
    return [Document(page_content=text, metadata={"source_name": source_name, "page_number": 1})], 1


def _build_chunk_payloads(source_documents: list[Document], *, document_id: str, source_name: str) -> tuple[list[str], list[str], list[dict[str, Any]]]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1200,
        chunk_overlap=200,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    split_documents = splitter.split_documents(source_documents)
    chunk_ids: list[str] = []
    chunk_texts: list[str] = []
    metadatas: list[dict[str, Any]] = []

    for chunk_index, chunk in enumerate(split_documents, start=1):
        sanitized = sanitize_hal_text(chunk.page_content)
        sanitized_text = str(sanitized["sanitized_text"]).strip()
        if not sanitized_text:
            continue

        page_number = int(chunk.metadata.get("page_number") or 1)
        chunk_ids.append(f"{document_id}:chunk:{chunk_index}")
        chunk_texts.append(sanitized_text)
        metadatas.append(
            {
                "document_id": document_id,
                "source_name": source_name,
                "title": source_name,
                "category": "uploaded_document",
                "page_number": page_number,
                "chunk_index": chunk_index,
            }
        )

    return chunk_ids, chunk_texts, metadatas


def _cleanup_failed_document_rag_upload(*, stored_path: Path, document_id: str, collection: Any | None) -> None:
    if collection is not None:
        with suppress(Exception):
            collection.delete(where={"document_id": document_id})
    with suppress(FileNotFoundError):
        stored_path.unlink()


def ingest_document_rag_upload(*, file_name: str, content: bytes, content_type: str, actor: str) -> dict[str, Any]:
    source_name = Path(file_name or "document.txt").name.strip() or "document.txt"
    extension = Path(source_name).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError("Supported document types are PDF, TXT, MD, CSV, and JSON.")

    document_id = f"doc-{uuid4().hex[:12]}"
    sha256 = hashlib.sha256(content).hexdigest()
    stored_file_name = f"{document_id}-{_slugify_file_name(source_name)}"
    stored_path = ensure_within_ai_workspace(get_document_rag_upload_dir() / stored_file_name)

    with hal_connection() as connection:
        _ensure_document_rag_schema(connection)
        stored_path.write_bytes(content)
        collection: Any | None = None

        try:
            source_documents, page_count = _load_source_documents(stored_path, content, source_name)
            if not source_documents:
                raise ValueError("The uploaded file did not contain extractable text.")

            chunk_ids, chunk_texts, metadatas = _build_chunk_payloads(source_documents, document_id=document_id, source_name=source_name)
            if not chunk_texts:
                raise ValueError("The uploaded file did not produce usable text chunks after sanitization.")

            collection = get_document_rag_collection()
            collection.add(ids=chunk_ids, documents=chunk_texts, metadatas=metadatas)

            uploaded_at_utc = datetime.now(timezone.utc).isoformat()
            content_char_count = sum(len(text) for text in chunk_texts)
            stored_path_value = workspace_relative_path(stored_path)
            connection.execute(
                """
                INSERT INTO hal_document_rag_documents (
                    document_id,
                    source_name,
                    stored_path,
                    mime_type,
                    sha256,
                    uploaded_at_utc,
                    uploaded_by,
                    page_count,
                    chunk_count,
                    content_char_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    document_id,
                    source_name,
                    stored_path_value,
                    content_type or "application/octet-stream",
                    sha256,
                    uploaded_at_utc,
                    actor,
                    page_count,
                    len(chunk_texts),
                    content_char_count,
                ),
            )
        except Exception:
            _cleanup_failed_document_rag_upload(stored_path=stored_path, document_id=document_id, collection=collection)
            raise

    append_ai_activity_log(
        tier="tier_2",
        actor=actor,
        action="document-rag-upload",
        detail=f"Indexed uploaded document {source_name} into the local LangChain RAG library.",
    )

    return {
        "message": f"Indexed {source_name} for grounded document Q&A.",
        "document": {
            "document_id": document_id,
            "source_name": source_name,
            "stored_path": workspace_relative_path(stored_path),
            "mime_type": content_type or "application/octet-stream",
            "sha256": sha256,
            "uploaded_at_utc": uploaded_at_utc,
            "uploaded_by": actor,
            "page_count": page_count,
            "chunk_count": len(chunk_texts),
            "content_char_count": content_char_count,
        },
    }


def list_document_rag_documents(*, limit: int = 20, search: str | None = None) -> dict[str, Any]:
    with hal_connection() as connection:
        _ensure_document_rag_schema(connection)
        where_sql = ""
        params: list[object] = []
        if search:
            where_sql = "WHERE source_name LIKE ?"
            params.append(f"%{search}%")

        count_query = f"SELECT COUNT(*) AS count FROM hal_document_rag_documents {where_sql}"
        total_count = int(connection.execute(count_query, params).fetchone()["count"])

        query = f"""
            SELECT
                document_id,
                source_name,
                stored_path,
                mime_type,
                sha256,
                uploaded_at_utc,
                uploaded_by,
                page_count,
                chunk_count,
                content_char_count
            FROM hal_document_rag_documents
            {where_sql}
            ORDER BY uploaded_at_utc DESC, source_name ASC
            LIMIT ?
        """
        rows = connection.execute(query, [*params, limit]).fetchall()

    return {
        "count": total_count,
        "limit": limit,
        "search": search,
        "items": [dict(row) for row in rows],
    }


def get_document_rag_document_count() -> int:
    with hal_connection() as connection:
        _ensure_document_rag_schema(connection)
        return int(connection.execute("SELECT COUNT(*) AS count FROM hal_document_rag_documents").fetchone()["count"])


def query_document_rag(question: str, *, limit: int = 4) -> list[dict[str, str]]:
    collection = get_document_rag_collection()
    if collection.count() == 0:
        return []

    results = collection.query(
        query_texts=[question],
        n_results=limit,
        include=["documents", "metadatas", "distances"],
    )

    ids = (results.get("ids") or [[]])[0]
    documents = (results.get("documents") or [[]])[0]
    metadatas = (results.get("metadatas") or [[]])[0]

    snippets: list[dict[str, str]] = []
    for source_id, document, metadata in zip(ids, documents, metadatas):
        metadata = metadata or {}
        source_name = str(metadata.get("source_name") or metadata.get("title") or source_id)
        page_number = int(metadata.get("page_number") or 1)
        chunk_index = int(metadata.get("chunk_index") or 1)
        document_text = str(document).strip()
        snippets.append(
            {
                "source_id": str(source_id),
                "title": source_name,
                "category": "uploaded_document",
                "content": document_text,
                "excerpt": f"Page {page_number}, chunk {chunk_index}: {document_text}",
            }
        )
    return snippets


def _build_document_answer_prompt(question: str, retrieved_context: list[dict[str, str]]) -> str:
    context_blocks = []
    for index, item in enumerate(retrieved_context, start=1):
        context_blocks.append(f"[{index}] File: {item['title']}\nContext: {item['excerpt']}")
    context_text = "\n\n".join(context_blocks)
    return (
        "You answer questions only from the uploaded-file context below. "
        "If the context does not support the answer, respond exactly with: "
        f"{INSUFFICIENT_DOCUMENT_CONTEXT_ANSWER} "
        "Do not invent figures, dates, or file citations. Mention source file names when relevant.\n\n"
        f"Question:\n{question}\n\n"
        f"Uploaded-file context:\n{context_text}\n"
    )


def _get_profile_timeout_seconds(profile: dict[str, object], *, default: int = 90) -> int:
    timeout_value = profile.get("timeout_seconds")
    try:
        timeout_seconds = int(timeout_value) if timeout_value is not None else default
    except (TypeError, ValueError):
        timeout_seconds = default
    return max(timeout_seconds, 1)


def _get_document_rag_generation_base_url() -> str:
    return DEFAULT_DOCUMENT_RAG_LLM_BASE_URL


def _has_grounded_retrieval_support(retrieved_context: list[dict[str, Any]]) -> bool:
    return any(str(item.get("content") or "").strip() for item in retrieved_context)


def _get_document_context_source_id(item: dict[str, Any]) -> str:
    source_id = str(item.get("source_id") or "").strip()
    if source_id:
        return source_id
    title = str(item.get("title") or "").strip()
    if title:
        return title
    return "document-rag-context"


def _is_insufficient_document_context_answer(answer: str) -> bool:
    normalized_answer = answer.strip()
    return normalized_answer == INSUFFICIENT_DOCUMENT_CONTEXT_ANSWER


def answer_document_rag_question(*, question: str, actor: str, top_k: int = 4) -> dict[str, Any]:
    if get_document_rag_document_count() == 0:
        raise ValueError("No document RAG files have been uploaded yet.")

    sanitized = sanitize_hal_text(question)
    sanitized_question = str(sanitized["sanitized_text"]).strip()
    if not sanitized_question:
        raise ValueError("Question did not contain usable text after sanitization.")

    retrieved_context = query_document_rag(sanitized_question, limit=top_k)
    has_retrieval_support = _has_grounded_retrieval_support(retrieved_context)
    if not retrieved_context or not has_retrieval_support:
        answer = INSUFFICIENT_DOCUMENT_CONTEXT_ANSWER
        audit = record_hal_audit(
            actor=actor,
            mode=DOCUMENT_RAG_MODE,
            sanitized_question=sanitized_question,
            retrieval_ids=[_get_document_context_source_id(item) for item in retrieved_context],
            response_summary=answer,
        )
        return {
            "mode": DOCUMENT_RAG_MODE,
            "answer": answer,
            "sanitized_question": sanitized_question,
            "sanitization_findings": sanitized["findings"],
            "retrieved_context": retrieved_context,
            "guardrails": DOCUMENT_GUARDRAILS,
            "audit_id": audit["audit_id"],
            "document_count": get_document_rag_document_count(),
            "grounded": False,
        }

    try:
        generation_base_url = _get_document_rag_generation_base_url()
        if generation_base_url == DEFAULT_OLLAMA_BASE_URL:
            generation_base_url = require_lane_runtime("chat", purpose="document RAG answer generation")
    except LocalAIConfigError as exc:
        raise RuntimeError(str(exc)) from exc

    profile_config = load_local_model_profile_config()
    chat_profile = resolve_lane_profile(profile_config, "chat")
    answer_result = generate_response_result(
        base_url=generation_base_url,
        profile=chat_profile,
        prompt=_build_document_answer_prompt(sanitized_question, retrieved_context),
        timeout_seconds=_get_profile_timeout_seconds(chat_profile),
    )
    answer = str(answer_result.get("response_text") or "").strip() or INSUFFICIENT_DOCUMENT_CONTEXT_ANSWER
    grounded = has_retrieval_support and not _is_insufficient_document_context_answer(answer)

    audit = record_hal_audit(
        actor=actor,
        mode=DOCUMENT_RAG_MODE,
        sanitized_question=sanitized_question,
        retrieval_ids=[_get_document_context_source_id(item) for item in retrieved_context],
        response_summary=answer[:240],
    )
    append_ai_activity_log(
        tier="tier_2",
        actor=actor,
        action="document-rag-ask",
        detail=f"Answered a grounded uploaded-file question using {len(retrieved_context)} retrieved chunks.",
    )
    return {
        "mode": DOCUMENT_RAG_MODE,
        "answer": answer,
        "sanitized_question": sanitized_question,
        "sanitization_findings": sanitized["findings"],
        "retrieved_context": retrieved_context,
        "guardrails": DOCUMENT_GUARDRAILS,
        "audit_id": audit["audit_id"],
        "document_count": get_document_rag_document_count(),
        "grounded": grounded,
    }