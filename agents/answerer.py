"""Answerer: generates a grounded, cited answer from retrieved context.

Simple factual questions go to the local Ollama model (cheap, fast).
Everything else (multi-hop, summary) goes to the configured complex model
(GPT via OPENAI_BASE_URL, or Agnes), which has the reasoning headroom for
connecting facts across chunks and communities.
"""

from __future__ import annotations

import config
from state import QueryState

_ANSWER_PROMPT = """Answer the question using ONLY the context below. Cite every factual
claim inline with [DocumentName p.Page]. If the context does not contain the answer,
say so explicitly instead of guessing.

Question: {question}

Context:
{context}

Answer:"""


def _build_context(state: QueryState) -> str:
    parts = []
    for summary in state.get("community_context", []):
        parts.append(f"[Knowledge graph cluster summary] {summary['summary']}")
    for chunk in state.get("retrieved_chunks", []):
        parts.append(f"[{chunk['doc_name']} p.{chunk['page']}] {chunk['text']}")
    return "\n\n".join(parts)


def answerer(state: QueryState) -> dict:
    chunks = state.get("retrieved_chunks", [])
    community_context = state.get("community_context", [])
    if not chunks and not community_context:
        return {
            "answer": "I couldn't find relevant information in the knowledge base "
            "to answer this question.",
            "citations": [],
        }

    mode = state.get("resolved_mode", "simple")
    llm = config.get_llm("local" if mode == "simple" else "complex")
    context = _build_context(state)

    answer = llm.invoke(_ANSWER_PROMPT.format(question=state["question"], context=context)).content

    seen = set()
    citations = []
    for chunk in chunks:
        key = (chunk["doc_name"], chunk["page"])
        if key not in seen:
            seen.add(key)
            citations.append({"doc_name": chunk["doc_name"], "page": chunk["page"]})

    return {"answer": answer, "citations": citations}
