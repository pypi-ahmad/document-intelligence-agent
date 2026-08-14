"""Comparator: multi-document comparison and contradiction specialist.

Runs instead of the plain answerer when resolved_mode is "comparison" or
"contradiction" -- it groups retrieved context by source document so the
complex model can reason about what each document individually says before
comparing them.
"""

from __future__ import annotations

import config
from state import QueryState
from utils import safe_json_loads

_COMPARE_PROMPT = """Compare what each document says in response to the question below.
Group by document. Note points of agreement, partial agreement, and direct conflict.

Return ONLY JSON:
{{"summary_answer": "2-4 sentence overview citing [DocumentName p.Page]",
  "comparison": [{{"aspect": "...", "by_document": {{"DocName": "what it says"}},
  "agreement": "agree|partial|conflict"}}]}}

Question: {question}

Context grouped by document:
{context}"""

_CONTRADICTION_ANSWER_PROMPT = """Find direct contradictions between documents relevant to
the question below, with evidence from each side.

Return ONLY JSON:
{{"summary_answer": "2-4 sentence overview citing [DocumentName p.Page]",
  "contradictions": [{{"claim": "...", "doc_a": "...", "doc_a_says": "...",
  "doc_b": "...", "doc_b_says": "..."}}]}}

Question: {question}

Context grouped by document:
{context}"""


def _grouped_context(state: QueryState) -> tuple[str, int]:
    by_doc: dict[str, list[str]] = {}
    for chunk in state.get("retrieved_chunks", []):
        by_doc.setdefault(chunk["doc_name"], []).append(f"p.{chunk['page']}: {chunk['text']}")
    blocks = [f"=== {doc} ===\n" + "\n".join(texts) for doc, texts in by_doc.items()]
    return "\n\n".join(blocks), len(by_doc)


def comparator(state: QueryState) -> dict:
    context, doc_count = _grouped_context(state)
    if not context:
        return {
            "answer": "I couldn't find relevant information in the knowledge base to compare.",
            "citations": [],
            "comparison_result": None,
        }

    mode = state.get("resolved_mode", "comparison")
    prompt = _CONTRADICTION_ANSWER_PROMPT if mode == "contradiction" else _COMPARE_PROMPT
    llm = config.get_llm("complex")
    raw = llm.invoke(prompt.format(question=state["question"], context=context)).content
    parsed = safe_json_loads(raw)

    if doc_count < 2:
        note = "\n\n(Note: only one document matched this question -- comparison is limited.)"
    else:
        note = ""

    if isinstance(parsed, dict):
        answer = (parsed.get("summary_answer") or raw) + note
    else:
        answer = raw + note
        parsed = None

    seen = set()
    citations = []
    for chunk in state.get("retrieved_chunks", []):
        key = (chunk["doc_name"], chunk["page"])
        if key not in seen:
            seen.add(key)
            citations.append({"doc_name": chunk["doc_name"], "page": chunk["page"]})

    return {"answer": answer, "citations": citations, "comparison_result": parsed}
