"""Small shared helpers: PDF loading, chunking, id/json utilities."""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path

import numpy as np
from langchain_text_splitters import RecursiveCharacterTextSplitter

import config

PDF_SUFFIX = ".pdf"


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def discover_pdfs(folder: str) -> list[Path]:
    return sorted(p for p in Path(folder).rglob(f"*{PDF_SUFFIX}") if p.is_file())


def load_pdf_pages(path: str) -> list[str]:
    """Return the text of each page of a PDF, in order (index 0 = page 1)."""
    from pypdf import PdfReader

    reader = PdfReader(path)
    return [(page.extract_text() or "").strip() for page in reader.pages]


def chunk_page_text(text: str) -> list[str]:
    """Layout-aware, paragraph-first chunking within a single page's text."""
    if not text.strip():
        return []
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=config.CHUNK_SIZE,
        chunk_overlap=config.CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    return [c.strip() for c in splitter.split_text(text) if c.strip()]


def safe_json_loads(text: str) -> dict | list | None:
    """Parse JSON out of an LLM response, tolerating ```json fences and stray prose."""
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"[\[{].*[\]}]", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                return None
        return None


def cosine_similarity(a: list[float], b: list[float]) -> float:
    va, vb = np.asarray(a), np.asarray(b)
    denom = np.linalg.norm(va) * np.linalg.norm(vb)
    if denom == 0:
        return 0.0
    return float(np.dot(va, vb) / denom)


def truncate(text: str, max_chars: int) -> str:
    return text if len(text) <= max_chars else text[:max_chars].rsplit(" ", 1)[0] + "…"
