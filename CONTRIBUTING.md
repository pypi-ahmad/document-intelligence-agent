# Contributing

Thanks for looking at this project. Contributions of any size are welcome —
a bug report, a feature idea, a doc fix, or a pull request all count. This is
a free, community-driven project with no company behind it, so outside
testing and patches genuinely help it improve.

Read the [README](README.md) first for how the ingestion and query pipelines
work. Read [DISCLAIMER.md](DISCLAIMER.md) for the responsibility that comes
with running your own documents through it.

## Ground rules

- Keep the project local-first where the README says so: entity extraction,
  routing, and simple answers run on local Ollama models; only the
  "complex" reasoning provider (OpenAI-compatible endpoint or Agnes AI) is
  configurable to leave the machine.
- One focused change per pull request. Avoid drive-by refactors mixed into
  a feature or fix.
- Never commit `.env`, real documents, `arcadedb-data/`, or any exported
  knowledge-graph content. Use synthetic or clearly redistributable PDFs for
  any fixture you add.
- Update `README.md` (features, env var table, project structure, or the
  pipeline description) in the same PR when your change affects any of them.

## Local setup

```bash
uv sync
ollama pull nomic-embed-text-v2-moe
ollama pull qwen3.5:2b
docker run -d --name docintel-arcadedb -p 2480:2480 -p 2424:2424 \
    -v "$(pwd)/arcadedb-data:/home/arcadedb/databases" \
    --env JAVA_OPTS="-Darcadedb.server.rootPassword=playwithdata" \
    arcadedata/arcadedb:26.5.1
cp .env.example .env   # fill in the keys you want to test with
uv run streamlit run app.py
```

Windows users can run `launch.cmd` instead, which does all of the above.

## Manual verification

There's no automated test suite yet — that's an open item, not an oversight
to route around (see [Future Improvements](README.md#future-improvements)).
Before opening a pull request for a UI-visible or pipeline-behavior change:

1. Ingest at least one synthetic or redistributable PDF and confirm it
   completes (chunking → entity extraction → community enrichment).
2. Ask one question in each affected mode (Simple, Multi-hop, Comparison,
   Contradiction, or Summary) and confirm the answer, citations, and
   verification result look right.
3. If you touched deletion/reset, confirm the sidebar's per-document delete
   and full reset both still work against ArcadeDB.
4. Confirm no API key value or document content ends up in a log line,
   screenshot, or committed fixture.

Describe what you tested (and with which providers/models) in the PR
description. Adding the first real test suite is itself a very welcome
contribution.

## Reporting bugs and suggesting features

Use the [bug report form](https://github.com/pypi-ahmad/document-intelligence-agent/issues/new?template=bug_report.yml)
or the [feature request form](https://github.com/pypi-ahmad/document-intelligence-agent/issues/new?template=feature_request.yml).
Search existing issues first. Include your OS, which LLM providers/models
were configured, and whether the issue is in ingestion or querying.

Report security issues privately as described in [SECURITY.md](SECURITY.md),
not through a public issue.

## No financial support

This project does not want or accept donations, sponsorship, or paid
support. Time, testing, bug reports, and pull requests are the contributions
that help — see [SUPPORT.md](SUPPORT.md).

By contributing, you agree your contribution may be distributed under this
project's [MIT License](LICENSE).
