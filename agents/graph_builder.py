"""Graph Builder agent: embeddings + entity/relation extraction -> ArcadeDB.

Uses the local Ollama model in JSON mode for entity/relation extraction
(cheap, runs per chunk) and the local embedding model for chunk vectors.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import config
from db.arcade_client import get_client
from embeddings import embed_texts
from state import IngestState
from utils import safe_json_loads

_EXTRACTION_PROMPT = """Extract entities and relationships from the text below.

Return ONLY JSON with this exact shape:
{{"entities": [{{"name": "...", "type": "PERSON|ORG|LOCATION|PRODUCT|EVENT|CONCEPT|OTHER",
"description": "..."}}],
"relations": [{{"source": "...", "relation": "...", "target": "...", "description": "..."}}]}}

Rules:
- "source" and "target" in relations must exactly match a "name" in entities.
- Only extract entities/relations clearly stated in the text. If none, return empty lists.
- Keep descriptions to one short sentence.

Text:
{text}
"""


@lru_cache(maxsize=1)
def _extraction_llm():
    from langchain_ollama import ChatOllama

    return ChatOllama(
        model=config.OLLAMA_MODEL,
        base_url=config.OLLAMA_BASE_URL,
        temperature=0,
        format="json",
        num_predict=config.LOCAL_MAX_TOKENS,
        reasoning=False,
    )


def extract_entities_relations(text: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    response = _extraction_llm().invoke(_EXTRACTION_PROMPT.format(text=text))
    parsed = safe_json_loads(response.content)
    if not isinstance(parsed, dict):
        return [], []
    entities = [e for e in parsed.get("entities", []) if isinstance(e, dict) and e.get("name")]
    relations = [
        r
        for r in parsed.get("relations", [])
        if isinstance(r, dict) and r.get("source") and r.get("target") and r.get("relation")
    ]
    return entities, relations


def graph_builder(state: IngestState) -> dict:
    if state.get("error"):
        return {}

    client = get_client()
    doc_id, doc_name = state["doc_id"], state["doc_name"]
    chunks = state.get("chunks", [])

    client.create_document(doc_id, doc_name, state["file_path"], len(state.get("pages", [])))

    vectors = embed_texts([c["text"] for c in chunks])

    entities_created = 0
    relations_created = 0

    for chunk, vector in zip(chunks, vectors, strict=True):
        client.create_chunk(
            chunk["chunk_id"], doc_id, doc_name, chunk["page"], chunk["text"], vector
        )

        entities, relations = extract_entities_relations(chunk["text"])
        entity_id_by_name: dict[str, str] = {}
        for entity in entities:
            entity_id = client.upsert_entity(
                entity["name"], entity.get("type", "OTHER"), entity.get("description", "")
            )
            entity_id_by_name[entity["name"]] = entity_id
            client.create_mention(chunk["chunk_id"], entity_id)
            entities_created += 1

        for relation in relations:
            source_id = entity_id_by_name.get(relation["source"]) or client.upsert_entity(
                relation["source"], "OTHER", ""
            )
            target_id = entity_id_by_name.get(relation["target"]) or client.upsert_entity(
                relation["target"], "OTHER", ""
            )
            client.create_relation(
                source_id, relation["relation"], target_id, relation.get("description", "")
            )
            relations_created += 1

    return {"entities_created": entities_created, "relations_created": relations_created}
