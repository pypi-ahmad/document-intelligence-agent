"""Shared state schemas for the two LangGraph pipelines (ingestion, query)."""

from __future__ import annotations

from typing import Any, TypedDict

# ---------------------------------------------------------------------------
# Ingestion pipeline: chunker -> graph_builder
# ---------------------------------------------------------------------------


class IngestState(TypedDict, total=False):
    file_path: str
    doc_id: str
    doc_name: str
    pages: list[str]  # page[i] = text of page i+1
    chunks: list[dict[str, Any]]  # {chunk_id, doc_id, doc_name, page, text}
    entities_created: int
    relations_created: int
    error: str | None


# ---------------------------------------------------------------------------
# Query pipeline: router -> retriever -> answerer|comparator -> verifier
# ---------------------------------------------------------------------------

QueryMode = str  # "auto" | "simple" | "multihop" | "comparison" | "contradiction" | "summary"


class QueryState(TypedDict, total=False):
    question: str
    requested_mode: QueryMode  # what the UI mode selector asked for
    resolved_mode: QueryMode  # what the router decided to actually run
    doc_filter: list[str] | None  # restrict to these doc names, if any

    entities_in_question: list[str]
    retrieved_chunks: list[dict[str, Any]]
    community_context: list[dict[str, Any]]
    reasoning_path: list[str]  # human-readable trace of retrieval hops

    answer: str
    citations: list[dict[str, Any]]
    comparison_result: dict[str, Any] | None
    verification: dict[str, Any] | None
    error: str | None
