# Security

## Supported surface

This is a local, single-user Streamlit application backed by a self-hosted
ArcadeDB container. There is no hosted deployment, no multi-tenant mode, and
no remote API surface beyond what you choose to run on your own machine.

## Where secrets and data live

- `OLLAMA_BASE_URL`, `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `AGNES_API_KEY`,
  and the ArcadeDB credentials are read from your local `.env` (or your
  shell environment, which takes precedence) — never hardcoded, never sent
  anywhere except the provider or database each value belongs to.
- `.env` is not committed; keep it that way. `.env.example` holds
  placeholders only.
- Ingested documents, extracted entities/relationships, and generated
  summaries are persisted in ArcadeDB, backed by the `arcadedata-data/`
  Docker volume on your machine. This is not ephemeral — it survives
  restarting the Streamlit process. Use the sidebar's per-document delete
  or full reset to remove it, or delete the volume directory directly.

## ArcadeDB default credentials

`launch.cmd` and the README's manual setup both start ArcadeDB with the
password `playwithdata` (ArcadeDB's own documented default) and publish
ports `2480`/`2424` on all interfaces (`-p 2480:2480`, not
`-p 127.0.0.1:2480:2480`). This is fine for a single-user machine on a
trusted network, but if your machine is reachable from an untrusted
network:

- change `JAVA_OPTS="-Darcadedb.server.rootPassword=..."` to a real password
  and set `ARCADEDB_PASSWORD` in `.env` to match;
- bind the container to loopback instead (`-p 127.0.0.1:2480:2480 -p 127.0.0.1:2424:2424`).

## Operator responsibility

You are responsible for:

- keeping your own API keys and `.env` file secure;
- the documents you ingest — see [DISCLAIMER.md](DISCLAIMER.md);
- securing the ArcadeDB container per the note above if your machine is
  network-reachable;
- reviewing generated answers, summaries, and comparisons before relying on
  them.

The maintainer does not receive your documents, extracted knowledge graph,
generated answers, or credentials through this project.

## Reporting a vulnerability

Please report security issues privately through this repository's
[GitHub private vulnerability reporting form](https://github.com/pypi-ahmad/document-intelligence-agent/security/advisories/new)
rather than a public issue. Include the affected file/flow, a minimal
reproduction, and the potential impact. Do not include real API keys,
documents, or other personal data in the report — use synthetic examples.

There is no fixed response-time guarantee and no paid bug bounty — this is
a free, community-maintained project.
