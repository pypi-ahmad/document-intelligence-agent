"""Verifier: checks the generated answer against its source chunks.

Every answer gets a cheap local groundedness pass. Comparison/contradiction
answers additionally get a complex-model cross-document consistency pass,
since spotting a real contradiction needs more reasoning than a local model
reliably provides.
"""

from __future__ import annotations

import config
from state import QueryState
from utils import safe_json_loads

_GROUNDEDNESS_PROMPT = """Check whether the ANSWER is fully supported by the CONTEXT.
Return ONLY JSON: {{"grounded": true|false, "unsupported_claims": ["..."]}}

CONTEXT:
{context}

ANSWER:
{answer}"""

_CONTRADICTION_PROMPT = """Look across these source excerpts (from possibly different
documents) and identify any statements that directly contradict each other.
Return ONLY JSON: {{"contradictions": [{{"claim": "...", "doc_a": "...", "doc_a_says": "...",
"doc_b": "...", "doc_b_says": "..."}}]}}. If there are none, return an empty list.

EXCERPTS:
{context}"""


def _context_block(state: QueryState) -> str:
    return "\n\n".join(
        f"[{c['doc_name']} p.{c['page']}] {c['text']}" for c in state.get("retrieved_chunks", [])
    )


def verifier(state: QueryState) -> dict:
    answer = state.get("answer", "")
    if not answer:
        return {"verification": {"grounded": False, "unsupported_claims": [], "contradictions": []}}

    context = _context_block(state)
    local_llm = config.get_llm("local")
    raw = local_llm.invoke(_GROUNDEDNESS_PROMPT.format(context=context, answer=answer)).content
    parsed = safe_json_loads(raw)
    verification = (
        parsed
        if isinstance(parsed, dict) and "grounded" in parsed
        else {"grounded": True, "unsupported_claims": []}
    )
    verification.setdefault("contradictions", [])

    mode = state.get("resolved_mode", "simple")
    if mode in ("contradiction", "comparison") and context:
        complex_llm = config.get_llm("complex")
        raw_contra = complex_llm.invoke(_CONTRADICTION_PROMPT.format(context=context)).content
        parsed_contra = safe_json_loads(raw_contra)
        contradictions = (
            parsed_contra.get("contradictions") if isinstance(parsed_contra, dict) else None
        )
        if isinstance(contradictions, list):
            verification["contradictions"] = contradictions

    return {"verification": verification}
