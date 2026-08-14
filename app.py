"""Streamlit UI for the Document Intelligence Agent."""

from __future__ import annotations

import tempfile
from pathlib import Path

import streamlit as st

import config
from agents.enricher import run_enrichment
from db.arcade_client import ArcadeDBError, get_client
from embeddings import embedding_dimensions
from graph import get_ingestion_graph, get_query_graph
from utils import discover_pdfs

st.set_page_config(page_title="Document Intelligence Agent", page_icon="📚", layout="wide")

MODE_LABELS = {
    "Auto": "auto",
    "Simple QA": "simple",
    "Multi-hop": "multihop",
    "Comparison": "comparison",
    "Contradiction Detection": "contradiction",
    "Summary": "summary",
}


@st.cache_resource
def bootstrap():
    client = get_client()
    if not client.is_ready():
        raise ArcadeDBError(
            "Cannot reach ArcadeDB. Start it with `launch.cmd` or "
            "`docker run --rm -p 2480:2480 -p 2424:2424 "
            '--env JAVA_OPTS="-Darcadedb.server.rootPassword=playwithdata" '
            "arcadedata/arcadedb:26.5.1`, then reload this page."
        )
    client.ensure_database()
    client.ensure_schema(embedding_dimensions())

    # First call to a not-yet-loaded Ollama model can take a while (model
    # has to be read off disk into memory) -- do that once now, with an
    # explanatory spinner, instead of surprising the first chat message.
    with st.spinner("Warming up local model (first run only, may take a minute)..."):
        config.get_llm("local").invoke("ready")

    return client


def _ingest_file(path: str) -> tuple[str, str] | None:
    result = get_ingestion_graph().invoke({"file_path": path})
    if result.get("error"):
        st.warning(result["error"])
        return None
    return result["doc_id"], result["doc_name"]


def _run_ingestion(paths: list[Path]) -> None:
    progress = st.progress(0.0, text="Starting ingestion...")
    new_docs: list[tuple[str, str]] = []
    for i, path in enumerate(paths):
        progress.progress(i / len(paths), text=f"Chunking + building graph: {path.name}")
        doc = _ingest_file(str(path))
        if doc:
            new_docs.append(doc)
    if new_docs:
        progress.progress(0.95, text="Detecting communities + summarizing...")
        run_enrichment(new_docs)
    progress.progress(1.0, text="Done.")
    st.success(f"Ingested {len(new_docs)}/{len(paths)} document(s).")
    st.cache_resource.clear()
    st.rerun()


def _render_citations(citations: list[dict]) -> None:
    if not citations:
        return
    with st.expander(f"Sources ({len(citations)})"):
        for c in citations:
            st.markdown(f"- **{c['doc_name']}**, page {c['page']}")


def _render_reasoning(path_steps: list[str]) -> None:
    if not path_steps:
        return
    with st.expander("Reasoning path"):
        for step in path_steps:
            st.markdown(f"- {step}")


def _render_verification(verification: dict | None) -> None:
    if not verification:
        return
    with st.expander("Verification"):
        grounded = verification.get("grounded", True)
        st.markdown("✅ Grounded in sources" if grounded else "⚠️ Possibly ungrounded")
        for claim in verification.get("unsupported_claims", []):
            st.markdown(f"- Unsupported: {claim}")
        for c in verification.get("contradictions", []):
            st.markdown(
                f"- **Contradiction**: {c.get('claim', '')}\n"
                f"  - *{c.get('doc_a', '?')}*: {c.get('doc_a_says', '')}\n"
                f"  - *{c.get('doc_b', '?')}*: {c.get('doc_b_says', '')}"
            )


def _render_comparison(comparison_result: dict | None) -> None:
    if not comparison_result:
        return
    rows = comparison_result.get("comparison")
    if rows:
        with st.expander("Comparison table", expanded=True):
            for row in rows:
                st.markdown(f"**{row.get('aspect', '')}** — _{row.get('agreement', '')}_")
                for doc, text in row.get("by_document", {}).items():
                    st.markdown(f"  - *{doc}*: {text}")


def _render_turn(turn: dict) -> None:
    st.write(turn.get("answer", ""))
    _render_citations(turn.get("citations", []))
    _render_comparison(turn.get("comparison_result"))
    _render_reasoning(turn.get("reasoning_path", []))
    _render_verification(turn.get("verification"))
    if turn.get("resolved_mode"):
        st.caption(f"Mode: {turn['resolved_mode']}")


try:
    client = bootstrap()
except ArcadeDBError as exc:
    st.error(str(exc))
    st.stop()
except Exception as exc:
    st.error(f"Startup failed: {exc}")
    st.stop()

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

st.title("📚 Document Intelligence Agent")
st.caption("GraphRAG over your documents — LangGraph + ArcadeDB + local & cloud LLMs")

with st.sidebar:
    st.header("Ingest documents")
    uploaded_files = st.file_uploader("Upload PDFs", type=["pdf"], accept_multiple_files=True)
    folder_path = st.text_input("...or a server-side folder path")

    if st.button("Ingest", type="primary", disabled=not (uploaded_files or folder_path)):
        paths: list[Path] = []
        if uploaded_files:
            tmp_dir = Path(tempfile.mkdtemp(prefix="docintel_"))
            for f in uploaded_files:
                dest = tmp_dir / f.name
                dest.write_bytes(f.getvalue())
                paths.append(dest)
        if folder_path:
            paths.extend(discover_pdfs(folder_path))
        if not paths:
            st.warning("No PDFs found.")
        else:
            _run_ingestion(paths)

    st.divider()
    st.header("Knowledge graph")
    stats = client.get_stats()
    c1, c2 = st.columns(2)
    c1.metric("Documents", stats["documents"])
    c1.metric("Entities", stats["entities"])
    c2.metric("Chunks", stats["chunks"])
    c2.metric("Relations", stats["relations"])
    st.metric("Communities", stats["communities"])

    docs = client.list_documents()
    with st.expander(f"Documents ({len(docs)})"):
        for d in docs:
            dc1, dc2 = st.columns([4, 1])
            dc1.write(d["name"])
            if dc2.button("🗑", key=f"del_{d['id']}"):
                client.delete_document(d["id"])
                st.rerun()

    with st.expander("Hierarchical summaries"):
        corpus_summary = client.get_corpus_summary()
        if corpus_summary:
            st.markdown("**Corpus**")
            st.caption(corpus_summary)
        for level in (1, 0):
            for community in client.list_communities(level=level):
                st.markdown(f"**Community (level {level})**")
                st.caption(community["summary"])

    st.divider()
    if st.button("⚠️ Reset knowledge base"):
        st.session_state.confirm_reset = True
    if st.session_state.get("confirm_reset"):
        st.error("This permanently deletes every document, chunk, entity, and summary.")
        rc1, rc2 = st.columns(2)
        if rc1.button("Confirm delete everything"):
            client.reset()
            client.ensure_schema(embedding_dimensions())
            st.session_state.confirm_reset = False
            st.session_state.chat_history = []
            st.rerun()
        if rc2.button("Cancel"):
            st.session_state.confirm_reset = False
            st.rerun()

mode_label = st.radio("Mode", list(MODE_LABELS), horizontal=True)
doc_filter = st.multiselect("Restrict to documents (optional)", [d["name"] for d in docs])

for turn in st.session_state.chat_history:
    with st.chat_message("user"):
        st.write(turn["question"])
    with st.chat_message("assistant"):
        _render_turn(turn)

question = st.chat_input("Ask a question about your documents...")
if question:
    with st.chat_message("user"):
        st.write(question)
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            result = get_query_graph().invoke(
                {
                    "question": question,
                    "requested_mode": MODE_LABELS[mode_label],
                    "doc_filter": doc_filter or None,
                }
            )
        _render_turn(result)
    st.session_state.chat_history.append({**result, "question": question})
