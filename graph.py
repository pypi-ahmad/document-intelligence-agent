"""LangGraph wiring: ingestion pipeline and query pipeline."""

from __future__ import annotations

from functools import lru_cache

from langgraph.graph import END, StateGraph

from agents.answerer import answerer
from agents.chunker import chunker
from agents.comparator import comparator
from agents.graph_builder import graph_builder
from agents.retriever import retriever
from agents.router import router
from agents.verifier import verifier
from state import IngestState, QueryState


@lru_cache(maxsize=1)
def get_ingestion_graph():
    """chunker -> graph_builder"""
    graph = StateGraph(IngestState)  # ty: ignore[invalid-argument-type]
    graph.add_node("chunker", chunker)
    graph.add_node("graph_builder", graph_builder)
    graph.set_entry_point("chunker")
    graph.add_edge("chunker", "graph_builder")
    graph.add_edge("graph_builder", END)
    return graph.compile()


def _branch_after_retrieval(state: QueryState) -> str:
    if state.get("resolved_mode") in ("comparison", "contradiction"):
        return "comparator"
    return "answerer"


@lru_cache(maxsize=1)
def get_query_graph():
    """router -> retriever -> (answerer | comparator) -> verifier"""
    graph = StateGraph(QueryState)  # ty: ignore[invalid-argument-type]
    graph.add_node("router", router)
    graph.add_node("retriever", retriever)
    graph.add_node("answerer", answerer)
    graph.add_node("comparator", comparator)
    graph.add_node("verifier", verifier)

    graph.set_entry_point("router")
    graph.add_edge("router", "retriever")
    graph.add_conditional_edges(
        "retriever", _branch_after_retrieval, {"answerer": "answerer", "comparator": "comparator"}
    )
    graph.add_edge("answerer", "verifier")
    graph.add_edge("comparator", "verifier")
    graph.add_edge("verifier", END)
    return graph.compile()
