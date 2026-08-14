"""Query Router: classifies a question into a retrieval/answering strategy.

If the UI already forced a mode (Multi-hop / Compare / Contradictions), that
choice is respected as-is -- the router only runs classification in "Auto".
"""

from __future__ import annotations

import config
from state import QueryState

VALID_MODES = {"simple", "multihop", "comparison", "contradiction", "summary"}

_ROUTER_PROMPT = """Classify the question into exactly one category. Reply with only the
category word, nothing else.

Categories:
- simple: a single fact, answerable from one place in the documents
- multihop: requires connecting facts across multiple entities/sections to answer
- comparison: asks to compare information across two or more documents
- contradiction: asks to find conflicting/inconsistent statements across documents
- summary: asks for an overview/summary of a document or the whole corpus

Question: {question}

Category:"""


def router(state: QueryState) -> dict:
    requested = state.get("requested_mode", "auto")
    if requested and requested != "auto":
        return {"resolved_mode": requested}

    llm = config.get_llm("local")
    raw = llm.invoke(_ROUTER_PROMPT.format(question=state["question"])).content.strip().lower()
    resolved = next((mode for mode in VALID_MODES if mode in raw), "simple")
    return {"resolved_mode": resolved}
