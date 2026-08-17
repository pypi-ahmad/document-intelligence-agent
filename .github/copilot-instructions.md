# Copilot instructions

This file gives GitHub Copilot (and any other agent reading it) the canonical
commands and phase-gating rules for this repo. Generated from
[MODERNIZATION_PLAN.md](../MODERNIZATION_PLAN.md); edit freely to match your
own gates as the project evolves.

## Canonical commands

| Command | Purpose |
|---|---|
| `uv sync --frozen` | Install every dependency from `uv.lock` — never hand-patch, regenerate the lock instead |
| `uv run streamlit run app.py` | Run the app (needs a live ArcadeDB container and Ollama server) |
| `uv run ruff check .` | Lint |
| `uv run ty check` | Typecheck |
| `uv run pytest -v` | Run the test suite (pure-logic slice only — see below) |

Run lint, typecheck, and tests before opening a pull request. All three
currently pass clean on `main`.

## What CI covers — and what it doesn't

`.github/workflows/ci.yml` runs lint + typecheck over the whole repo, and
`pytest` over a **pure-logic slice only**: functions with no LLM, database, or
network dependency (`utils.py`'s helpers, `agents/comparator.py`'s
`_grouped_context`). This is a deliberate, named scope — not an oversight.

The LLM/DB-integrated pipeline (ingestion graph, query graph, ArcadeDB client,
embeddings) is **not** covered by automated tests or CI. Verifying a change to
that pipeline means running the manual checklist in
[CONTRIBUTING.md](../CONTRIBUTING.md) (ingest a document, exercise each query
mode, check citations/verification/comparison output by hand) — do this before
opening a PR that touches `agents/`, `db/`, `graph.py`, `config.py`, or
`embeddings.py`.

## Phase-gating rules (regime-aware)

- **Post-testability ("lit") work** — anything covered by `pytest`/`ruff`/`ty`:
  gate on green CI on the PR. That is the authoritative signal.
- **Pre-testability ("dark") work** — anything touching the LLM/DB-integrated
  pipeline: gate on the manual verification checklist in `CONTRIBUTING.md`,
  not on a test suite that doesn't run against it. Do not block a PR here on
  a CI check that was never designed to cover this code.

## Branch and PR rules

- Trunk is `main` — the only branch in this repo. Branch from `main`, PR back
  to `main`. Do not stack a phase branch on top of a sibling phase branch.
- One focused change per PR. If a change touches both the CI-covered slice
  and the LLM/DB pipeline, call out both verification paths in the PR
  description (which CI check ran, and what you manually verified).
- **CI is not yet an enforced required status check.** `.github/workflows/ci.yml`
  runs on every push/PR to `main` but does not currently block merges — that
  requires a human to enable it under GitHub → Settings → Branches. Until
  then, treat a green CI run as a strong signal, not a hard gate.

## Living-doc discipline

Any change that adds/removes a test, a CI step, a dependency, or a script
(`launch.cmd`/`launch.sh`/equivalent) should update `ARCHITECTURE.md`'s
Commands & Verification Inventory and `CONTRIBUTING.md`'s setup/verification
sections in the same PR — don't let those docs drift from what's actually
runnable.
