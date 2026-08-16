# Support

This is a free, open-source, community-driven project. Support is
best-effort — there's no paid support tier, no SLA, and no dedicated team
behind it. Thanks for giving it a try; bug reports and feature ideas are
genuinely welcome and help more than anything else.

## No donations, please

This project does not accept or want donations, sponsorship, or any other
financial support. If you'd like to support it, use one of the options
below instead — they're worth more than money here.

## How to help

- Star and share the [GitHub repository](https://github.com/pypi-ahmad/document-intelligence-agent).
- Try it against a synthetic or redistributable set of PDFs and report what
  breaks.
- File a [bug report](https://github.com/pypi-ahmad/document-intelligence-agent/issues/new?template=bug_report.yml)
  with reproducible steps.
- Suggest an improvement via the [feature request form](https://github.com/pypi-ahmad/document-intelligence-agent/issues/new?template=feature_request.yml).
- Open a pull request — see [CONTRIBUTING.md](CONTRIBUTING.md). There's no
  automated test suite yet, so adding one is an especially valuable
  contribution.

## Getting help

Search [existing issues](https://github.com/pypi-ahmad/document-intelligence-agent/issues)
before opening a new one. When reporting a problem, include:

- your OS, and whether you used `launch.cmd` or manual setup;
- which LLM providers/models were configured (local Ollama model, and the
  "complex" provider — OpenAI-compatible or Agnes AI);
- whether the issue happened during ingestion or during a query, and which
  mode (Simple, Multi-hop, Comparison, Contradiction, Summary);
- the exact error, with any API key values or document content removed.

Never post an API key, a real document, or extracted knowledge-graph
content in a public issue.

Report security vulnerabilities privately as described in
[SECURITY.md](SECURITY.md), not through a public issue.

## Out of scope

- Bugs in Ollama, ArcadeDB, or a configured cloud provider (OpenAI-compatible
  endpoint, Agnes AI) themselves — report those upstream, not here, unless
  this project's integration is clearly at fault.
- Answer quality issues that trace back to a small/weak local model choice —
  try a larger `OLLAMA_MODEL` first (see README's Configuration Options).
