from __future__ import annotations

from pathlib import Path
import shutil

import chromadb
from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2

from app.config_runtime import get_env_setting
from app.hal.safety import get_hal_allowed_base_path, resolve_dedicated_hal_directory


COLLECTION_NAME = "hal_local_index"


def get_embedding_provider_name() -> str:
    provider = get_env_setting("HAL_EMBEDDING_PROVIDER", "onnx-minilm").strip().lower()
    return provider or "onnx-minilm"


def get_hal_chroma_path() -> Path:
    configured = get_env_setting("HAL_CHROMA_PATH", "").strip()
    candidate = Path(configured) if configured else Path("hal_chroma")
    return resolve_dedicated_hal_directory(candidate, label="HAL vector store path", directory_name="hal_chroma")


def get_embedding_function():
    provider = get_embedding_provider_name()
    if provider == "onnx-minilm":
        return ONNXMiniLM_L6_V2(preferred_providers=["CPUExecutionProvider"])
    raise ValueError(f"Unsupported HAL_EMBEDDING_PROVIDER: {provider}")


def get_chroma_client() -> chromadb.ClientAPI:
    chroma_path = get_hal_chroma_path()
    chroma_path.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(chroma_path))


def get_hal_collection() -> chromadb.Collection:
    client = get_chroma_client()
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
        embedding_function=get_embedding_function(),
    )


def rebuild_hal_collection(documents: list[dict[str, str]]) -> dict[str, object]:
    client = get_chroma_client()
    try:
        client.delete_collection(name=COLLECTION_NAME)
    except Exception:
        pass

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
        embedding_function=get_embedding_function(),
    )
    if documents:
        collection.add(
            ids=[document["source_id"] for document in documents],
            documents=[document["sanitized_content"] for document in documents],
            metadatas=[
                {
                    "title": document["title"],
                    "category": document["category"],
                }
                for document in documents
            ],
        )

    return {
        "backend": "chroma",
        "embedding_provider": get_embedding_provider_name(),
        "vector_path": str(get_hal_chroma_path()),
        "document_count": len(documents),
    }


def query_hal_collection(question: str, limit: int = 3) -> list[dict[str, str]]:
    collection = get_hal_collection()
    if collection.count() == 0:
        return []

    results = collection.query(query_texts=[question], n_results=limit, include=["documents", "metadatas", "distances"])

    ids = (results.get("ids") or [[]])[0]
    documents = (results.get("documents") or [[]])[0]
    metadatas = (results.get("metadatas") or [[]])[0]

    snippets: list[dict[str, str]] = []
    for source_id, document, metadata in zip(ids, documents, metadatas):
        snippets.append(
            {
                "source_id": str(source_id),
                "title": str((metadata or {}).get("title", source_id)),
                "category": str((metadata or {}).get("category", "documentation")),
                "excerpt": str(document),
            }
        )
    return snippets


def count_hal_collection_documents() -> int:
    return int(get_hal_collection().count())


def clear_hal_vector_store() -> None:
    chroma_path = get_hal_chroma_path()
    if chroma_path == get_hal_allowed_base_path():
        raise ValueError("HAL vector store path cannot equal the HAL allowed base path.")
    if chroma_path.exists():
        shutil.rmtree(chroma_path)