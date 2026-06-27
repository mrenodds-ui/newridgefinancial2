from contextlib import contextmanager
import json
import os
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

import app.hal.document_rag as document_rag_module

from app.auth import clear_user_registry_cache


TEST_AUTH_USERS_JSON = json.dumps(
    [
        {
            "username": "admin",
            "display_name": "Administrator",
            "password": "password",
            "roles": ["dashboard:read", "hal:operator", "hal:index:refresh", "admin"],
        },
        {
            "username": "reviewer",
            "display_name": "Reviewer",
            "password": "reviewer-password",
            "roles": ["dashboard:read", "hal:operator"],
        }
    ]
)

os.environ["APP_AUTH_USERS_JSON"] = TEST_AUTH_USERS_JSON

from app.main import app


client = TestClient(app)


class _FakeCollection:
    def __init__(self):
        self._records: list[dict[str, object]] = []

    def add(self, ids, documents, metadatas):
        for record_id, document, metadata in zip(ids, documents, metadatas):
            self._records.append({"id": record_id, "document": document, "metadata": metadata})

    def count(self):
        return len(self._records)

    def query(self, query_texts, n_results, include):
        del query_texts, include
        subset = self._records[:n_results]
        return {
            "ids": [[str(item["id"]) for item in subset]],
            "documents": [[str(item["document"]) for item in subset]],
            "metadatas": [[dict(item["metadata"]) for item in subset]],
            "distances": [[0.0 for _ in subset]],
        }

    def delete(self, where):
        document_id = str(where.get("document_id") or "")
        self._records = [item for item in self._records if item["metadata"].get("document_id") != document_id]


def setup_function():
    os.environ["APP_AUTH_USERS_JSON"] = TEST_AUTH_USERS_JSON
    runtime_dir = Path(__file__).resolve().parent / ".document_rag_runtime" / uuid4().hex
    os.environ["HAL_ALLOWED_BASE_PATH"] = str(runtime_dir)
    os.environ["HAL_SQLITE_PATH"] = str(runtime_dir / "hal_test.sqlite3")
    os.environ["HAL_AI_WORKSPACE_PATH"] = str(runtime_dir / "AI_Workspace")
    os.environ["HAL_DOCUMENT_RAG_CHROMA_PATH"] = str(runtime_dir / "AI_Workspace" / "document_rag" / "chroma")
    clear_user_registry_cache()


def basic_auth():
    return ("admin", "password")


def reviewer_auth():
    return ("reviewer", "reviewer-password")


def test_document_rag_upload_and_ask(monkeypatch):
    captured_prompt: dict[str, object] = {}
    captured_runtime: dict[str, object] = {}
    fake_collection = _FakeCollection()

    monkeypatch.setattr(document_rag_module, "get_document_rag_collection", lambda: fake_collection)

    def fake_require_lane_runtime(alias, *, purpose):
        captured_runtime["alias"] = alias
        captured_runtime["purpose"] = purpose
        captured_runtime["base_url"] = document_rag_module.get_frontend_base_url()
        return captured_runtime["base_url"]

    monkeypatch.setattr(document_rag_module, "require_lane_runtime", fake_require_lane_runtime)

    def fake_generate_response_result(*, base_url, profile, prompt, timeout_seconds, seed=None):
        del seed
        captured_prompt["prompt"] = prompt
        captured_runtime["generation_base_url"] = base_url
        assert base_url
        assert profile["model"] == config.DEFAULT_FRONTEND_MODEL
        assert timeout_seconds >= 1
        return {
            "response_text": "Revenue grew 12% year over year according to q2-earnings-notes.md.",
            "metrics": {},
            "raw_body": {},
        }

    monkeypatch.setattr(document_rag_module, "generate_response_result", fake_generate_response_result)

    upload_response = client.post(
        "/api/hal9000/document-rag/documents",
        auth=basic_auth(),
        files={
            "file": (
                "q2-earnings-notes.md",
                b"Q2 earnings notes\n\nRevenue grew 12% year over year. Operating margin improved by 180 basis points.",
                "text/markdown",
            )
        },
    )

    assert upload_response.status_code == 200
    upload_payload = upload_response.json()
    assert upload_payload["document"]["source_name"] == "q2-earnings-notes.md"
    assert upload_payload["document"]["stored_path"] == ""
    assert upload_payload["document"]["chunk_count"] >= 1

    list_response = client.get("/api/hal9000/document-rag/documents", auth=basic_auth())
    assert list_response.status_code == 200
    list_payload = list_response.json()
    assert list_payload["count"] == 1
    assert list_payload["items"][0]["source_name"] == "q2-earnings-notes.md"
    assert list_payload["items"][0]["stored_path"] == ""

    ask_response = client.post(
        "/api/hal9000/document-rag/ask",
        auth=basic_auth(),
        json={"question": "What happened to revenue in Q2?", "top_k": 3},
    )

    assert ask_response.status_code == 200
    ask_payload = ask_response.json()
    assert ask_payload["grounded"] is True
    assert "Revenue grew 12%" in ask_payload["answer"]
    assert ask_payload["document_count"] == 1
    assert ask_payload["retrieved_context"]
    assert any(item["title"] == "q2-earnings-notes.md" for item in ask_payload["retrieved_context"])
    assert "q2-earnings-notes.md" in str(captured_prompt.get("prompt") or "")
    assert captured_runtime["alias"] == "chat"
    assert captured_runtime["base_url"] == captured_runtime["generation_base_url"]


def test_document_rag_grounded_false_for_insufficient_context_answer(monkeypatch):
    fake_collection = _FakeCollection()

    monkeypatch.setattr(document_rag_module, "get_document_rag_collection", lambda: fake_collection)
    monkeypatch.setattr(document_rag_module, "require_lane_runtime", lambda *args, **kwargs: document_rag_module.get_frontend_base_url())
    monkeypatch.setattr(
        document_rag_module,
        "generate_response_result",
        lambda **kwargs: {
            "response_text": document_rag_module.INSUFFICIENT_DOCUMENT_CONTEXT_ANSWER,
            "metrics": {},
            "raw_body": {},
        },
    )

    upload_response = client.post(
        "/api/hal9000/document-rag/documents",
        auth=basic_auth(),
        files={
            "file": (
                "board-notes.md",
                b"Board notes\n\nCollections improved in April.",
                "text/markdown",
            )
        },
    )

    assert upload_response.status_code == 200

    ask_response = client.post(
        "/api/hal9000/document-rag/ask",
        auth=basic_auth(),
        json={"question": "What happened to revenue in Q2?", "top_k": 3},
    )

    assert ask_response.status_code == 200
    ask_payload = ask_response.json()
    assert ask_payload["answer"] == document_rag_module.INSUFFICIENT_DOCUMENT_CONTEXT_ANSWER
    assert ask_payload["grounded"] is False


def test_document_rag_skips_generation_when_retrieval_has_no_usable_content(monkeypatch):
    monkeypatch.setattr(document_rag_module, "get_document_rag_document_count", lambda: 1)
    monkeypatch.setattr(
        document_rag_module,
        "query_document_rag",
        lambda *args, **kwargs: [
            {
                "source_id": "doc-1:chunk:1",
                "title": "empty.md",
                "category": "uploaded_document",
                "content": "",
                "excerpt": "Page 1, chunk 1:",
            }
        ],
    )
    monkeypatch.setattr(
        document_rag_module,
        "require_lane_runtime",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("runtime check should not run without support")),
    )
    monkeypatch.setattr(
        document_rag_module,
        "generate_response_result",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("generation should not run without support")),
    )

    ask_response = client.post(
        "/api/hal9000/document-rag/ask",
        auth=basic_auth(),
        json={"question": "What changed?", "top_k": 3},
    )

    assert ask_response.status_code == 200
    ask_payload = ask_response.json()
    assert ask_payload["answer"] == document_rag_module.INSUFFICIENT_DOCUMENT_CONTEXT_ANSWER
    assert ask_payload["grounded"] is False
    assert ask_payload["retrieved_context"][0]["title"] == "empty.md"


def test_document_rag_question_handles_retrieved_context_without_source_id(monkeypatch):
    captured: dict[str, object] = {}

    monkeypatch.setattr(document_rag_module, "get_document_rag_document_count", lambda: 1)
    monkeypatch.setattr(
        document_rag_module,
        "query_document_rag",
        lambda *args, **kwargs: [
            {
                "title": "empty.md",
                "category": "uploaded_document",
                "content": "",
                "excerpt": "Page 1, chunk 1:",
            }
        ],
    )

    def fake_record_hal_audit(**kwargs):
        captured.update(kwargs)
        return {"audit_id": "hal-doc-rag-test"}

    monkeypatch.setattr(document_rag_module, "record_hal_audit", fake_record_hal_audit)

    payload = document_rag_module.answer_document_rag_question(
        question="What changed?",
        actor="hal_operator",
        top_k=3,
    )

    assert payload["answer"] == document_rag_module.INSUFFICIENT_DOCUMENT_CONTEXT_ANSWER
    assert payload["grounded"] is False
    assert captured["retrieval_ids"] == ["empty.md"]


def test_document_rag_requires_uploaded_documents():
    response = client.post(
        "/api/hal9000/document-rag/ask",
        auth=basic_auth(),
        json={"question": "What changed in the 10-K?"},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "No document RAG files have been uploaded yet."}


def test_document_rag_upload_rejects_invalid_pdf(monkeypatch):
    fake_collection = _FakeCollection()

    monkeypatch.setattr(document_rag_module, "get_document_rag_collection", lambda: fake_collection)
    monkeypatch.setattr(
        document_rag_module,
        "PdfReader",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("bad pdf")),
    )

    response = client.post(
        "/api/hal9000/document-rag/documents",
        auth=basic_auth(),
        files={
            "file": (
                "broken.pdf",
                b"%PDF-1.7 broken",
                "application/pdf",
            )
        },
    )

    assert response.status_code == 400
    assert response.json() == {"detail": document_rag_module.INVALID_PDF_ERROR_MESSAGE}


def test_load_source_documents_rejects_pdf_outside_ai_workspace(monkeypatch):
    outside_pdf = Path(os.environ["HAL_ALLOWED_BASE_PATH"]).resolve() / "outside.pdf"
    outside_pdf.parent.mkdir(parents=True, exist_ok=True)
    outside_pdf.write_bytes(b"%PDF-1.7 fake")

    monkeypatch.setattr(
        document_rag_module,
        "PdfReader",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("PdfReader should not run for out-of-workspace paths")),
    )

    try:
        document_rag_module._load_source_documents(outside_pdf, b"%PDF-1.7 fake", "outside.pdf")
    except ValueError as exc:
        assert "outside HAL AI workspace" in str(exc)
    else:
        raise AssertionError("Expected out-of-workspace PDF loads to be rejected")


def test_document_rag_upload_rolls_back_vectors_and_file_when_db_insert_fails(monkeypatch):
    fake_collection = _FakeCollection()
    original_hal_connection = document_rag_module.hal_connection

    monkeypatch.setattr(document_rag_module, "get_document_rag_collection", lambda: fake_collection)

    @contextmanager
    def failing_hal_connection():
        with original_hal_connection() as connection:
            class FailingConnection:
                def execute(self, sql, parameters=()):
                    if "INSERT INTO hal_document_rag_documents" in sql:
                        raise RuntimeError("db insert failed")
                    return connection.execute(sql, parameters)

                def __getattr__(self, name):
                    return getattr(connection, name)

            yield FailingConnection()

    monkeypatch.setattr(document_rag_module, "hal_connection", failing_hal_connection)

    with pytest.raises(RuntimeError, match="db insert failed"):
        document_rag_module.ingest_document_rag_upload(
            file_name="board-notes.md",
            content=b"Board notes\n\nCollections improved in April.",
            content_type="text/markdown",
            actor="admin",
        )

    upload_dir = document_rag_module.get_document_rag_upload_dir()
    assert fake_collection.count() == 0
    assert list(upload_dir.iterdir()) == []

    with original_hal_connection() as connection:
        document_rag_module._ensure_document_rag_schema(connection)
        count = int(connection.execute("SELECT COUNT(*) AS count FROM hal_document_rag_documents").fetchone()["count"])

    assert count == 0


def test_document_rag_same_name_uploads_do_not_overwrite_other_users(monkeypatch):
    fake_collection = _FakeCollection()

    monkeypatch.setattr(document_rag_module, "get_document_rag_collection", lambda: fake_collection)

    first_response = client.post(
        "/api/hal9000/document-rag/documents",
        auth=basic_auth(),
        files={
            "file": (
                "shared-notes.md",
                b"Admin upload\n\nRevenue grew in April.",
                "text/markdown",
            )
        },
    )

    second_response = client.post(
        "/api/hal9000/document-rag/documents",
        auth=reviewer_auth(),
        files={
            "file": (
                "shared-notes.md",
                b"Reviewer upload\n\nCollections improved in May.",
                "text/markdown",
            )
        },
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert first_response.json()["document"]["document_id"] != second_response.json()["document"]["document_id"]

    list_response = client.get("/api/hal9000/document-rag/documents", auth=basic_auth())
    assert list_response.status_code == 200
    payload = list_response.json()
    assert payload["count"] == 2
    shared_items = [item for item in payload["items"] if item["source_name"] == "shared-notes.md"]
    assert len(shared_items) == 2
    assert {item["uploaded_by"] for item in shared_items} == {"admin", "reviewer"}
    assert fake_collection.count() == 2


def test_document_rag_invalid_same_name_upload_preserves_existing_document(monkeypatch):
    fake_collection = _FakeCollection()

    monkeypatch.setattr(document_rag_module, "get_document_rag_collection", lambda: fake_collection)

    valid_response = client.post(
        "/api/hal9000/document-rag/documents",
        auth=basic_auth(),
        files={
            "file": (
                "board-notes.md",
                b"Board notes\n\nCollections improved in April.",
                "text/markdown",
            )
        },
    )

    invalid_response = client.post(
        "/api/hal9000/document-rag/documents",
        auth=basic_auth(),
        files={
            "file": (
                "board-notes.md",
                b"   \n\t  ",
                "text/markdown",
            )
        },
    )

    assert valid_response.status_code == 200
    assert invalid_response.status_code == 400
    assert invalid_response.json() == {"detail": "The uploaded file did not contain extractable text."}

    list_response = client.get("/api/hal9000/document-rag/documents", auth=basic_auth())
    assert list_response.status_code == 200
    payload = list_response.json()
    assert payload["count"] == 1
    assert payload["items"][0]["source_name"] == "board-notes.md"
    assert fake_collection.count() == 1