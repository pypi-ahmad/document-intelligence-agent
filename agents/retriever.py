"""Retriever: hybrid vector + graph (multi-hop) retrieval."""

from __future__ import annotations

from functools import lru_cache

import config
from db.arcade_client import get_client
from embeddings import embed_text
from state import QueryState
from utils import safe_json_loads

_ENTITY_EXTRACT_PROMPT = """Extract the key named entities (people, organizations, products,
locations, concepts) mentioned in this question. Return ONLY JSON: {{"entities": ["..."]}}

Question: {question}"""


@lru_cache(maxsize=1)
def _entity_llm():
    from langchain_ollama import ChatOllama

    return ChatOllama(
        model=config.OLLAMA_MODEL,
        base_url=config.OLLAMA_BASE_URL,
        temperature=0,
        format="json",
        num_predict=config.LOCAL_MAX_TOKENS,
        reasoning=False,
    )


def _extract_question_entities(question: str) -> list[str]:
    response = _entity_llm().invoke(_ENTITY_EXTRACT_PROMPT.format(question=question))
    parsed = safe_json_loads(response.content)
    if isinstance(parsed, dict) and isinstance(parsed.get("entities"), list):
        return [str(e) for e in parsed["entities"] if e]
    return []


def retriever(state: QueryState) -> dict:
    client = get_client()
    question = state["question"]
    mode = state.get("resolved_mode", "simple")
    doc_filter = state.get("doc_filter")

    vector_hits = client.vector_search(embed_text(question), config.TOP_K_VECTOR)
    if doc_filter:
        vector_hits = [h for h in vector_hits if h["doc_name"] in doc_filter]

    reasoning_path = [f"vector search: {len(vector_hits)} candidate chunks"]

    entity_names = _extract_question_entities(question)
    matched = client.entities_by_name(entity_names) if entity_names else []
    entity_ids = [e["id"] for e in matched]

    graph_chunks: list[dict] = []
    community_context: list[dict] = []
    if entity_ids:
        reasoning_path.append(
            f"matched entities in question: {', '.join(e['name'] for e in matched)}"
        )
        hops = config.MAX_HOPS if mode in ("multihop", "comparison", "contradiction") else 1
        neighbor_entities, hop_trace = client.multi_hop_neighbors(entity_ids, hops)
        reasoning_path.extend(hop_trace)

        all_entity_ids = list({*entity_ids, *(e["id"] for e in neighbor_entities)})
        graph_chunks = client.chunks_mentioning_entities(
            all_entity_ids, doc_filter, limit=config.TOP_K_FINAL
        )
        community_context = client.communities_for_entities(all_entity_ids)
        if community_context:
            reasoning_path.append(f"pulled {len(community_context)} community summaries")

    merged: dict[str, dict] = {c["id"]: c for c in vector_hits}
    for chunk in graph_chunks:
        merged.setdefault(chunk["id"], chunk)

    ranked = sorted(merged.values(), key=lambda c: c.get("distance", 1.0))[: config.TOP_K_FINAL]

    return {
        "entities_in_question": entity_names,
        "retrieved_chunks": ranked,
        "community_context": community_context[:5],
        "reasoning_path": reasoning_path,
    }
