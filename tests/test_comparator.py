from agents.comparator import _grouped_context
from state import QueryState


def test_grouped_context_groups_by_document():
    state: QueryState = {
        "retrieved_chunks": [
            {"doc_name": "A.pdf", "page": 1, "text": "Alpha claim."},
            {"doc_name": "B.pdf", "page": 3, "text": "Beta claim."},
            {"doc_name": "A.pdf", "page": 2, "text": "Another alpha claim."},
        ]
    }
    context, doc_count = _grouped_context(state)
    assert doc_count == 2
    assert "=== A.pdf ===" in context
    assert "=== B.pdf ===" in context
    assert "p.1: Alpha claim." in context
    assert "p.2: Another alpha claim." in context


def test_grouped_context_empty_input():
    empty_state: QueryState = {"retrieved_chunks": []}
    context, doc_count = _grouped_context(empty_state)
    assert context == ""
    assert doc_count == 0
