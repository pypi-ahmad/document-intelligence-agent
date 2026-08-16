# Document Intelligence Agent

A GraphRAG document Q&A agent: LangGraph orchestrates chunking, entity/relation
extraction, community detection, hybrid retrieval, answering, verification,
and cross-document comparison over a knowledge graph stored in ArcadeDB, with
a Streamlit chat UI.

![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

**Repository:** [github.com/pypi-ahmad/document-intelligence-agent](https://github.com/pypi-ahmad/document-intelligence-agent)

## Contents

- [Open source and community](#open-source-and-community)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [How It Works](#how-it-works)
- [Installation & Setup](#installation--setup)
- [Environment Variables](#environment-variables)
- [Usage](#usage)
- [Configuration Options](#configuration-options)
- [Future Improvements](#future-improvements)
- [Documentation](#documentation)
- [License](#license)

## Open source and community

This is a free, open-source (MIT), community-driven project. Cloning,
forking, testing, filing bugs, suggesting features, and sending pull
requests are all welcome — see [CONTRIBUTING.md](CONTRIBUTING.md) and
[SUPPORT.md](SUPPORT.md). This project does not want or accept donations,
sponsorship, or paid support of any kind; testing and patches are worth
more here than money.

You run this entirely on your own machine, with your own API keys and your
own ArcadeDB container. Nobody but you sees your documents, extracted
knowledge graph, or generated answers — and you are responsible for
everything you ingest and every answer you rely on. See
[DISCLAIMER.md](DISCLAIMER.md) for the full breakdown, and
[SECURITY.md](SECURITY.md) for how to report a vulnerability (including an
important note on ArcadeDB's default credentials).

> [!IMPORTANT]
> Entity extraction, routing, and simple answers run on your local Ollama
> model. Multi-hop, comparison, contradiction, and cross-document
> verification questions are sent to whichever "complex" provider you
> configure (an OpenAI-compatible endpoint, or Agnes AI) — treat that
> exactly like sending the document content to that provider yourself.

## Features

- **Multi-document ingestion** — upload PDFs or point at a server-side folder; batch progress shown in the UI.
- **Knowledge graph construction** — entities and relationships are extracted per chunk and persisted as a graph (`Document → Chunk → Entity → Community`) in ArcadeDB.
- **Hierarchical summarization** — Louvain community detection over the entity graph, with summaries generated at the community, super-community, document, and corpus level.
- **Hybrid retrieval** — vector similarity search (ArcadeDB `LSM_VECTOR` index) combined with multi-hop graph traversal (BFS over `RELATES_TO` edges) and community-summary context.
- **Query routing** — an LLM classifies each question as simple / multi-hop / comparison / contradiction / summary and routes it to the matching pipeline branch.
- **Multi-document comparison & contradiction detection** — a dedicated comparator groups retrieved context by source document and reports agreement/conflict with evidence from each side.
- **Answer verification** — every answer gets a groundedness check against its cited source chunks; comparison/contradiction answers get an additional cross-document consistency pass.
- **Citations** — every answer cites `[DocumentName p.Page]`; the UI shows a sources panel, the reasoning path (for multi-hop), and the verification result.
- **Local-first LLMs, cloud for hard reasoning** — Ollama runs entity extraction, routing, and simple answers locally; a configurable "complex" provider (any OpenAI-compatible endpoint, or Agnes AI) handles multi-hop reasoning, comparison, and verification.
- **Persistent** — the knowledge graph lives in ArcadeDB (Docker volume), independent of the Streamlit process; restarting the app does not lose ingested documents.
- **Knowledge base management** — per-document delete, and a full reset, from the sidebar.

## Tech Stack

| Layer | Choice |
|---|---|
| UI | [Streamlit](https://streamlit.io/) |
| Orchestration | [LangGraph](https://github.com/langchain-ai/langgraph) |
| Graph database | [ArcadeDB](https://arcadedb.com/) (accessed over its HTTP REST API) |
| Local embeddings | Ollama (`nomic-embed-text-v2-moe` by default) |
| Local LLM | Ollama (`qwen3.5:2b` by default) — routing, entity/relation extraction, simple answers |
| Complex-reasoning LLM | Any OpenAI-compatible endpoint (`OPENAI_BASE_URL`), or [Agnes AI](https://www.agnes-ai.com/en/docs/overview) — multi-hop reasoning, comparison, verification |
| Community detection | [NetworkX](https://networkx.org/) (Louvain) |
| PDF parsing | [pypdf](https://pypdf.readthedocs.io/) |
| Package management | [uv](https://docs.astral.sh/uv/) |

## Project Structure

```
.
├── app.py                  # Streamlit UI: ingestion, chat, sidebar (stats, docs, summaries, reset)
├── graph.py                # LangGraph wiring: ingestion graph + query graph
├── state.py                # TypedDict state schemas for both graphs
├── config.py                # Env-driven config + get_llm("local" | "complex") factory
├── embeddings.py             # Local embedding model wrapper (Ollama)
├── utils.py                # PDF page extraction, chunking, JSON parsing helpers
├── agents/
│   ├── chunker.py           # Layout-aware (per-page) + paragraph-first chunking
│   ├── graph_builder.py     # Embeddings + entity/relation extraction -> ArcadeDB
│   ├── enricher.py          # Community detection + hierarchical summarization
│   ├── router.py            # Question -> {simple, multihop, comparison, contradiction, summary}
│   ├── retriever.py          # Hybrid vector + multi-hop graph retrieval
│   ├── answerer.py           # Grounded, cited answer generation
│   ├── verifier.py           # Groundedness + cross-document contradiction check
│   └── comparator.py         # Multi-document comparison / contradiction specialist
├── db/
│   └── arcade_client.py      # ArcadeDB HTTP REST client + full graph schema
├── launch.cmd                # One double-click: installs/checks deps, starts ArcadeDB + Streamlit
├── .env.example               # Template for all environment variables
└── pyproject.toml            # uv project + ruff/ty config
```

## How It Works

**Ingestion** (`chunker → graph_builder`, run once per document, then a single
`enricher` pass over the batch):

1. `chunker` extracts per-page text from a PDF and splits it into overlapping,
   paragraph-first chunks (page boundaries are preserved for citations).
2. `graph_builder` embeds every chunk (Ollama), asks the local LLM (JSON mode)
   to extract entities and relationships from it, and writes
   `Document -HAS_CHUNK-> Chunk -MENTIONS-> Entity -RELATES_TO-> Entity` into
   ArcadeDB.
3. After a batch finishes, `enricher` runs Louvain community detection over
   the entity graph, summarizes each community (and, if there's more than
   one, clusters communities by real cross-community relation density into a
   second summarization level), then summarizes each document and the whole
   corpus.

**Querying** (`router → retriever → answerer|comparator → verifier`):

1. `router` classifies the question (skipped if the UI mode selector already
   forced one).
2. `retriever` runs a vector search over chunk embeddings, extracts candidate
   entities from the question, does a BFS over `RELATES_TO` for multi-hop
   questions, and pulls in relevant community summaries.
3. `answerer` (simple questions) or `comparator` (comparison/contradiction
   questions) generates a grounded, cited answer — comparator groups context
   by source document first so the model can reason about what each document
   says before comparing them.
4. `verifier` checks the answer's groundedness against the retrieved chunks,
   and for comparison/contradiction questions, runs an additional pass
   specifically looking for conflicting statements across documents.

## Installation & Setup

### Prerequisites

- [Ollama](https://ollama.com/download) (local models)
- [Docker](https://www.docker.com/products/docker-desktop/) (for ArcadeDB)
- [uv](https://docs.astral.sh/uv/) (Python package manager)

### Quick start (Windows)

Double-click **`launch.cmd`**. It installs `uv` if missing, runs `uv sync`,
pulls the required Ollama models if they aren't already present, starts an
ArcadeDB container (data persisted to `.\arcadedb-data`), and launches the
app.

### Manual setup (any OS)

```bash
# 1. Install dependencies
uv sync

# 2. Pull the local models
ollama pull nomic-embed-text-v2-moe
ollama pull qwen3.5:2b

# 3. Start ArcadeDB
docker run -d --name docintel-arcadedb -p 2480:2480 -p 2424:2424 \
    -v "$(pwd)/arcadedb-data:/home/arcadedb/databases" \
    --env JAVA_OPTS="-Darcadedb.server.rootPassword=playwithdata" \
    arcadedata/arcadedb:26.5.1

# 4. Run the app
uv run streamlit run app.py
```

## Environment Variables

Copy `.env.example` to `.env` and fill in what you need — or just set these
in your shell/system environment (real environment variables always take
precedence over `.env`).

| Variable | Default | Purpose |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server |
| `OLLAMA_MODEL` | `qwen3.5:2b` | Local model: routing, entity extraction, simple answers |
| `EMBED_MODEL` | `nomic-embed-text-v2-moe` | Local embedding model |
| `OPENAI_API_KEY` | — | Key for the OpenAI-compatible "complex" LLM |
| `OPENAI_BASE_URL` | — | Base URL for the OpenAI-compatible endpoint |
| `OPENAI_MODEL` | `gpt-4o-mini` | Model name at that endpoint |
| `AGNES_API_KEY` | — | Key for [Agnes AI](https://www.agnes-ai.com/en/docs/overview) (alternative complex provider) |
| `AGNES_BASE_URL` | `https://apihub.agnes-ai.com/v1` | Agnes AI endpoint |
| `AGNES_MODEL` | `agnes-2.5-flash` | Agnes model name |
| `COMPLEX_LLM_PROVIDER` | `openai` | `openai` or `agnes` — which provider handles multi-hop/verification/comparison |
| `ARCADEDB_HOST` / `ARCADEDB_PORT` | `localhost` / `2480` | ArcadeDB server |
| `ARCADEDB_DATABASE` | `docintel` | Database name |
| `ARCADEDB_USER` / `ARCADEDB_PASSWORD` | `root` / `playwithdata` | ArcadeDB credentials |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | `900` / `150` | Chunking (characters) |
| `TOP_K_VECTOR` / `TOP_K_FINAL` | `8` / `6` | Retrieval breadth |
| `MAX_HOPS` | `2` | Multi-hop graph traversal depth |
| `LLM_TEMPERATURE` | `0.1` | Sampling temperature for all LLM calls |
| `LOCAL_MAX_TOKENS` | `768` | Output token cap for the local model |

## Usage

1. In the sidebar, upload one or more PDFs (or enter a server-side folder
   path) and click **Ingest**. Progress and resulting graph stats show live.
2. Pick a **Mode** — Auto, Simple QA, Multi-hop, Comparison, Contradiction
   Detection, or Summary — and optionally restrict to specific documents.
3. Ask a question in the chat box. The response includes a sources panel,
   and (for multi-hop/comparison/contradiction questions) a reasoning path
   and verification result.
4. Browse hierarchical summaries or delete/reset the knowledge base from the
   sidebar.

### Examples

- *Simple*: "What was Acme's revenue in 2023?"
- *Multi-hop*: "How does the vendor mentioned in the contract relate to the
  compliance requirements in the audit report?"
- *Comparison*: "How does the pricing model in Document A differ from
  Document B?"
- *Contradiction*: "Are there any conflicting statements about the project
  deadline across these documents?"

## Configuration Options

Swap the "complex" reasoning provider without touching code:

```bash
# Use your own OpenAI-compatible endpoint (default)
COMPLEX_LLM_PROVIDER=openai

# Or use Agnes AI (512K context, useful for large multi-document comparisons)
COMPLEX_LLM_PROVIDER=agnes
```

Bigger/smaller local model, if your hardware allows: set `OLLAMA_MODEL` to
any chat-capable model you've pulled (e.g. `qwen3.5:9b` for higher quality at
the cost of latency).

## Future Improvements

- Streamed token-by-token responses in the chat UI
- Re-ranking retrieved chunks with a cross-encoder before answering
- Incremental re-enrichment (only re-cluster communities touched by newly
  added documents, instead of a full recompute)
- Authentication/multi-tenant knowledge bases

## Documentation

| Document | What it is |
|---|---|
| [CONTRIBUTING.md](CONTRIBUTING.md) | How to set up, test, and send a PR |
| [SUPPORT.md](SUPPORT.md) | How to get help and report bugs |
| [SECURITY.md](SECURITY.md) | How to report a vulnerability, ArcadeDB credential/binding notes |
| [DISCLAIMER.md](DISCLAIMER.md) | No-warranty, data responsibility, and local-vs-cloud data flow |
| [LICENSE](LICENSE) | MIT license text |

This project does not want or accept donations, sponsorship, or paid
support of any kind.

## License

[MIT](LICENSE)

## Links

- Repository: https://github.com/pypi-ahmad/document-intelligence-agent

<p align="center">Made with ❤️ by Ahmad Mujtaba</p>
