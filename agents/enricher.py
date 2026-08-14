"""Graph Enricher: community detection + hierarchical summarization.

Runs once after an ingestion batch (not per-document, not inside the
per-document LangGraph -- summarizing communities mid-batch would waste
work that a later document could still change).

Hierarchy: chunk -> entity community (level 0) -> super-community (level 1)
-> document -> corpus.
"""

from __future__ import annotations

import networkx as nx

import config
from db.arcade_client import get_client
from utils import new_id, truncate

_COMMUNITY_PROMPT = """These entities and relationships form one cluster of a knowledge graph.

Entities: {entities}
Relationships: {relations}
Representative text excerpts: {excerpts}

Write a concise (3-5 sentence) summary of what this cluster is about."""

_MERGE_PROMPT = """These are summaries of related sub-clusters in a knowledge graph.

{summaries}

Write a concise (3-5 sentence) summary that captures the overall theme connecting them."""

_DOCUMENT_PROMPT = """Summarize this document in 4-6 sentences based on its key entities
and excerpts.

Document: {doc_name}
Key entities: {entities}
Excerpts: {excerpts}"""

_CORPUS_PROMPT = """Write a 5-8 sentence executive summary of a document corpus, given the
per-document summaries below. Note major shared themes and any notable differences.

{summaries}"""


def _build_graph() -> tuple[nx.Graph, dict[str, dict]]:
    client = get_client()
    entities, relations = client.all_entities_and_relations()
    graph = nx.Graph()
    by_id = {}
    for entity in entities:
        graph.add_node(entity["id"])
        by_id[entity["id"]] = entity
    for relation in relations:
        if relation["source"] in by_id and relation["target"] in by_id:
            graph.add_edge(relation["source"], relation["target"], label=relation.get("label", ""))
    return graph, by_id


def _summarize(prompt: str, use_complex: bool = False) -> str:
    llm = config.get_llm("complex" if use_complex else "local")
    return llm.invoke(prompt).content.strip()


def detect_and_summarize_communities() -> int:
    """Level-0 communities: louvain over the Entity/RELATES_TO graph."""
    client = get_client()
    graph, by_id = _build_graph()
    client.clear_communities()

    if graph.number_of_nodes() < 2:
        return 0

    communities = nx.algorithms.community.louvain_communities(graph, seed=42)
    level0_meta: list[tuple[str, list[str], str]] = []  # (community_id, entity_ids, summary)
    for community in communities:
        entity_ids = list(community)
        if len(entity_ids) < 2:
            continue
        names = ", ".join(by_id[e]["name"] for e in entity_ids[:15])
        relation_labels = {
            graph.edges[u, v].get("label", "")
            for u in entity_ids
            for v in graph.neighbors(u)
            if v in entity_ids
        }
        excerpts_rows = client.chunks_mentioning_entities(entity_ids, limit=5)
        excerpts = truncate(" | ".join(r["text"] for r in excerpts_rows), 1500)

        summary = _summarize(
            _COMMUNITY_PROMPT.format(
                entities=names,
                relations=", ".join(filter(None, relation_labels)) or "none",
                excerpts=excerpts or "none",
            )
        )
        community_id = new_id("com")
        client.create_community(community_id, level=0, summary=summary, entity_ids=entity_ids)
        level0_meta.append((community_id, entity_ids, summary))

    if len(level0_meta) > 1:
        _summarize_super_communities(level0_meta, graph)

    return len(level0_meta)


def _summarize_super_communities(
    level0_meta: list[tuple[str, list[str], str]], graph: nx.Graph
) -> None:
    """Level-1: cluster level-0 communities by real cross-community relation
    density (not co-occurrence guesswork), then summarize each cluster."""
    entity_to_community = {e: cid for cid, entity_ids, _ in level0_meta for e in entity_ids}
    summaries_by_id = {cid: summary for cid, _, summary in level0_meta}

    coarse = nx.Graph()
    coarse.add_nodes_from(summaries_by_id)
    for u, v in graph.edges():
        cu, cv = entity_to_community.get(u), entity_to_community.get(v)
        if cu and cv and cu != cv:
            if coarse.has_edge(cu, cv):
                coarse[cu][cv]["weight"] += 1
            else:
                coarse.add_edge(cu, cv, weight=1)

    if coarse.number_of_edges() == 0:
        return

    client = get_client()
    super_communities = nx.algorithms.community.louvain_communities(
        coarse, weight="weight", seed=42
    )
    for group in super_communities:
        if len(group) < 2:
            continue
        joined = "\n".join(f"- {summaries_by_id.get(cid, '')}" for cid in group)
        summary = _summarize(_MERGE_PROMPT.format(summaries=joined))
        parent_id = new_id("com")
        client.create_community(parent_id, level=1, summary=summary, entity_ids=[])
        for child_id in group:
            client.link_community_hierarchy(child_id, parent_id)


def summarize_document(doc_id: str, doc_name: str) -> str:
    client = get_client()
    rows = client.query("SELECT text FROM Chunk WHERE doc_id = :id LIMIT 20", {"id": doc_id})
    excerpts = truncate(" | ".join(r["text"] for r in rows), 3000)
    entity_rows = client.query(
        "SELECT DISTINCT name FROM (SELECT expand(out('MENTIONS')) "
        "FROM Chunk WHERE doc_id = :id) LIMIT 25",
        {"id": doc_id},
    )
    entities = ", ".join(r["name"] for r in entity_rows) or "none identified"

    summary = _summarize(
        _DOCUMENT_PROMPT.format(doc_name=doc_name, entities=entities, excerpts=excerpts or "none")
    )
    client.set_document_summary(doc_id, summary)
    return summary


def summarize_corpus() -> str:
    client = get_client()
    docs = client.list_documents()
    if not docs:
        return ""
    joined = "\n".join(f"- {d['name']}: {d['summary']}" for d in docs if d.get("summary"))
    if not joined:
        return ""
    summary = _summarize(_CORPUS_PROMPT.format(summaries=joined), use_complex=True)
    client.set_corpus_summary(summary)
    return summary


def run_enrichment(new_doc_ids: list[tuple[str, str]]) -> dict:
    """Full enrichment pass: document summaries for newly ingested docs,
    then corpus-wide community detection + hierarchical summaries."""
    for doc_id, doc_name in new_doc_ids:
        summarize_document(doc_id, doc_name)
    community_count = detect_and_summarize_communities()
    corpus_summary = summarize_corpus()
    return {"communities": community_count, "corpus_summary": corpus_summary}
