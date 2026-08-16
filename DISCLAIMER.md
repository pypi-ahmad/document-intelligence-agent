# Disclaimer

Read this before you ingest real documents.

## No warranty

This software is MIT-licensed and provided **as is**, with no warranty of
any kind. See [LICENSE](LICENSE). The maintainer is not liable for damages
arising from using it, including an incorrect answer, a missed
contradiction, or a lost knowledge base.

## You run it, you own the data

This is not a hosted service. You run it on your own machine with your own
API keys and your own ArcadeDB container. The maintainer never receives
your documents, extracted knowledge graph, generated answers, or
credentials.

Everything the app builds lives on your machine:

- ingested PDFs are read locally and chunked in memory;
- extracted entities, relationships, chunk embeddings, and hierarchical
  summaries are persisted in ArcadeDB, backed by the `arcadedb-data/`
  Docker volume — this is not ephemeral, and it stays until you delete a
  document or reset the knowledge base from the sidebar (or delete the
  volume yourself);
- nothing leaves your machine except what's described below.

### What leaves your machine

- Chunk text sent to your local Ollama model (entity/relation extraction,
  routing, simple answers, embeddings) never leaves your machine unless you
  point `OLLAMA_BASE_URL` at a remote server yourself.
- Chunk text, retrieved context, and question text sent to the configured
  "complex" reasoning provider (an OpenAI-compatible endpoint, or Agnes AI)
  for multi-hop and summary answers, all comparison/contradiction answers,
  and the cross-document consistency pass that verifies those answers —
  **treat this exactly like sending that content to that provider
  yourself.** Simple-mode answers and base groundedness verification stay
  on the local model. If you don't want any document content leaving your
  machine, keep questions to Simple mode and don't configure a complex
  provider at all.

You decide what you upload and what questions you ask. You are responsible
for not exposing content you don't want reaching a configured cloud
provider.

## Answers are generated, not guaranteed

Every answer is grounded and cited against retrieved source chunks, and
passes a groundedness/consistency check — but this is model output, not a
guarantee of correctness. **You are responsible for reviewing any answer,
summary, or comparison before relying on it**, especially for
comparison/contradiction results across multiple documents.

## No financial support wanted

This project does not want or accept donations, sponsorship, or paid
support. Testing, bug reports, and pull requests are the help that
matters — see [SUPPORT.md](SUPPORT.md) and [CONTRIBUTING.md](CONTRIBUTING.md).

## Security

Do not use this disclaimer to report a vulnerability. Follow
[SECURITY.md](SECURITY.md) instead — including the note on ArcadeDB's
default credentials and network binding.
