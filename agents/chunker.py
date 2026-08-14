"""Chunker agent: layout-aware (per-page) + semantic (paragraph-first) chunking.

Pure text processing -- no DB or embedding calls here, so ingestion can be
retried/inspected before anything is written to the graph.
"""

from __future__ import annotations

from pathlib import Path

from state import IngestState
from utils import chunk_page_text, load_pdf_pages, new_id


def chunker(state: IngestState) -> dict:
    file_path = state["file_path"]
    doc_name = Path(file_path).name
    doc_id = new_id("doc")

    try:
        pages = load_pdf_pages(file_path)
    except Exception as exc:  # malformed / unreadable PDF
        return {"error": f"Failed to read {doc_name}: {exc}"}

    chunks = []
    for page_number, page_text in enumerate(pages, start=1):
        for piece in chunk_page_text(page_text):
            chunks.append(
                {
                    "chunk_id": new_id("chk"),
                    "doc_id": doc_id,
                    "doc_name": doc_name,
                    "page": page_number,
                    "text": piece,
                }
            )

    return {
        "doc_id": doc_id,
        "doc_name": doc_name,
        "pages": pages,
        "chunks": chunks,
        "error": None,
    }
