# Usage

A step-by-step walkthrough of the Streamlit app, plus troubleshooting. For
setup instructions, see the [README](README.md#installation--setup) first.

## Starting the app

- Windows one-click: double-click `launch.cmd`.
- Linux/macOS one-step: `./launch.sh` (run `chmod +x launch.sh` once first
  if needed).
- Either script installs `uv` if missing, runs `uv sync` (creating `.venv`
  in the project root), pulls the two required Ollama models if they
  aren't already present, starts (or reuses) the ArcadeDB container, and
  launches Streamlit — this is the full first-time setup, not just a
  daily-start shortcut.
- Manual (any OS): make sure Ollama is running and ArcadeDB's Docker
  container is up (see the README's manual setup), then run
  `uv run streamlit run app.py`.

The first launch after starting the app can take a minute — the local
Ollama model gets warmed up (loaded into memory) before the UI is usable,
with a spinner explaining why.

If the app immediately errors with "Cannot reach ArcadeDB," the container
isn't running — start it per the README, or re-run `launch.cmd`/`launch.sh`.

## Sidebar: Ingest documents

1. Either upload one or more PDFs directly, or type a server-side folder
   path (the app will recursively find every `.pdf` under it).
2. Click **Ingest**. A progress bar shows chunking + graph-building
   per document, then a final "Detecting communities + summarizing..."
   step that runs once for the whole batch.
3. When it finishes, the page reloads and the knowledge-graph stats update.

Each PDF becomes its own `Document` node; re-ingesting the same file again
creates a second, separate document rather than updating the first — delete
the old one first if you want to replace it.

## Sidebar: Knowledge graph

- **Stats** — live counts of documents, chunks, entities, relations, and
  communities in the graph.
- **Documents** (expander) — every ingested document by name, each with a
  🗑 button. Deleting a document removes its chunks and the document itself,
  and also drops any entities that were *only* mentioned by that document's
  chunks (so the graph doesn't accumulate orphaned nodes).
- **Hierarchical summaries** (expander) — the corpus-wide summary (if any
  document has been ingested), then level-1 "super-community" summaries,
  then level-0 community summaries. These are generated once per ingestion
  batch, not live — ingest again to refresh them after adding documents.
- **Reset knowledge base** — a two-step confirmation that permanently
  deletes every document, chunk, entity, relation, and summary. There is no
  undo; the `arcadedb-data/` volume itself is untouched by "delete one
  document," but a full reset drops and recreates the database.

## Asking questions

1. Pick a **Mode**: Auto, Simple QA, Multi-hop, Comparison, Contradiction
   Detection, or Summary. Auto lets the router classify each question;
   any other mode forces that pipeline branch regardless of what the
   question looks like.
2. Optionally restrict the question to specific documents via **Restrict to
   documents**.
3. Type your question in the chat box. The response includes:
   - the answer text, with inline `[DocumentName p.Page]`-style citations
     baked into comparison/contradiction answers, and a separate
     **Sources** panel for every mode;
   - a **Comparison table** (comparison/contradiction modes only), grouped
     by aspect, showing what each document says and whether they agree,
     partially agree, or conflict;
   - a **Reasoning path** expander showing the retrieval steps taken
     (vector search hit count, matched entities, graph hops, community
     summaries pulled) — most useful for multi-hop questions;
   - a **Verification** expander showing whether the answer was judged
     grounded in its sources, any unsupported claims flagged, and (for
     comparison/contradiction modes) any contradictions found by the
     cross-document consistency pass.

### Example questions by mode

- *Simple*: "What was Acme's revenue in 2023?"
- *Multi-hop*: "How does the vendor mentioned in the contract relate to the
  compliance requirements in the audit report?"
- *Comparison*: "How does the pricing model in Document A differ from
  Document B?"
- *Contradiction*: "Are there any conflicting statements about the project
  deadline across these documents?"
- *Summary*: "Summarize this document" / "Summarize everything I've
  ingested."

Chat history persists for the current browser session (Streamlit
`session_state`) but is not saved anywhere — reloading the page clears it.
The underlying knowledge graph in ArcadeDB is unaffected either way.

## Configuration

Two things you can change without touching code (see the README's
Environment Variables and Configuration Options sections for the full
list):

- **Which provider handles "complex" reasoning** (multi-hop, summary,
  comparison, contradiction, and cross-document verification) —
  `COMPLEX_LLM_PROVIDER=openai` (default, any OpenAI-compatible endpoint)
  or `COMPLEX_LLM_PROVIDER=agnes`.
- **Which local model does extraction/routing/simple answers** —
  `OLLAMA_MODEL`, e.g. a larger model for better quality at the cost of
  latency.

## Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| "Cannot reach ArcadeDB" on startup | The container isn't running. Start it per the README's manual `docker run` command, or re-run `launch.cmd`/`launch.sh`. |
| App warms up the local model on every restart | Expected — Ollama unloads idle models from memory; the warm-up spinner runs once per app process start, not once ever. |
| Ingestion finishes but entities/communities are empty | The local model may not be reliably returning valid JSON for extraction. Try a larger `OLLAMA_MODEL`, or check the terminal for extraction errors (they're logged, not raised, so ingestion still completes). |
| "AGNES_API_KEY is not set but COMPLEX_LLM_PROVIDER=agnes" (or the OpenAI equivalent) | Set the matching API key in `.env` and restart the app, or switch `COMPLEX_LLM_PROVIDER` back to a provider you do have a key for. |
| A question routes to the wrong mode in Auto | Force the mode explicitly instead of relying on the router's classification — it's a single LLM call and can misclassify ambiguous questions. |
| Comparison/Contradiction mode says "only one document matched" | The retriever didn't find relevant chunks in more than one document for that question — try broadening the question or removing the document filter. |
| Deleted a document but its entities still show up | Only entities *exclusively* mentioned by that document's chunks are dropped on delete; an entity also mentioned in another surviving document is kept (by design — it's still valid knowledge). |

For anything not covered here, see [SUPPORT.md](SUPPORT.md).
