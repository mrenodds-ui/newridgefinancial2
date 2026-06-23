from __future__ import annotations

from .index_builder import refresh_hal_index
from .vector_store import count_hal_collection_documents, query_hal_collection


def retrieve_relevant_context(question: str, limit: int = 3) -> list[dict[str, str]]:
    if count_hal_collection_documents() == 0:
        refresh_hal_index()
    return query_hal_collection(question, limit=limit)