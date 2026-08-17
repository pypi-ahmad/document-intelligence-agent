# Modernization Plan — Document Intelligence Agent

Cites [ARCHITECTURE.md](ARCHITECTURE.md) for current-state detail; this document
is forward-looking only.

## 1. Executive summary

This is a young, actively-maintained Python project on a fully current stack
(LangGraph, Streamlit, ArcadeDB client, `uv`-pinned dependencies). It is not a
legacy-rescue case. Dependencies are already pinned (`pyproject.toml`/`uv.lock`),
and lint/typecheck (`ruff`, `ty`) are already configured and pass clean — the
only real gap is that neither runs automatically, and there is no test suite
or CI at all. The plan is deliberately one real phase: stand up CI for the
part of the codebase that can genuinely be tested without a live ArcadeDB or
Ollama server (lint, typecheck, and a small set of pure-logic unit tests), and
name the LLM/DB-integrated pipeline explicitly as **out of CI's reach for now**
rather than pretending otherwise.

## 2. Current state assessment

See [ARCHITECTURE.md](ARCHITECTURE.md) in full. Key facts this plan depends on:
`pyproject.toml` + `uv.lock` already exist and install cleanly; `ruff`/`ty` are
configured dev dependencies that pass clean today (verified live this session);
no test files or `.github/workflows/` exist (ARCHITECTURE.md § Commands &
Verification Inventory, § Data/APIs/CI/CD/testing). The app's own `bootstrap()`
already fails gracefully (`ArcadeDBError` with an actionable message,
`app.py:29-48,130-137`) when ArcadeDB isn't reachable — this matters below,
because it means the *absence* of live services in CI is a known, handled
condition, not an unhandled crash.

## 3. Feasibility spike result & strategy

**Spike performed 2026-08-17**, not assumed:

| Check | Result |
|---|---|
| Installs from a committed lockfile without hand-patching | **Yes.** `uv sync --frozen` reports "Checked 82 packages" with zero changes needed — the existing `.venv` already matches `uv.lock` exactly. |
| Builds/compiles on a currently-supported toolchain | **Yes.** `uv run ruff check .` and `uv run ty check` both report "All checks passed!" (re-verified live this pass, matching ARCHITECTURE.md's earlier finding). |
| Boots | **Partially, verifiably.** ArcadeDB is not running in this environment right now; `get_client().is_ready()` returns `False` cleanly (no exception) — confirming `bootstrap()`'s graceful-failure path is real, not just claimed. Streamlit itself was not launched (out of scope for a docs/planning pass; the code-level trace is sufficient here). |
| Test runner executes, ≥1 meaningful test passes | **No test runner is wired up yet, but real pure-logic units exist and were verified live, standalone, with no LLM/DB/network involved:** `utils.safe_json_loads` (JSON parsing incl. fenced/malformed input), `utils.chunk_page_text` (paragraph-first splitting), `utils.truncate`, `utils.new_id`, and `agents.comparator._grouped_context` (groups retrieved chunks by document name) — all five ran correctly in isolation this pass. |

**Conclusion:** this system is **already past the dependency-pinning and
lint/typecheck bars** and has a genuine, if narrow, pure-logic surface ready to
be collected under `pytest`. Call this **Strategy C (wire up what's already
there)**, same as the other young/healthy repos audited this development
session — neither Strategy A (freeze-then-lift) nor B (walking-skeleton)
applies to a system that already builds, lints, and type-checks clean.

**Testability Milestone — split by component, not one blanket answer:**
- **Pure-logic utilities** (`utils.py`'s helpers, `agents/comparator.py`'s
  `_grouped_context`, and any other function with no LLM/DB call in its body):
  reaches the Testability Milestone **in Phase 1** — supported runtime (yes),
  lockfile install (yes), builds (yes), and a real test runner can execute
  ≥1 meaningful test for this slice specifically, in CI, with zero external
  services.
- **LLM/DB-integrated pipeline** (everything that calls `config.get_llm()`,
  `db.arcade_client`, or `embeddings.py`): does **not** cross the Testability
  Milestone in this phase. A meaningful automated test here needs either a
  live ArcadeDB + Ollama (or mocks substantial enough to be a different kind
  of test entirely — mocking away the actual LLM/DB behavior this pipeline
  exists to orchestrate). That is real infrastructure work, not a
  Phase-1-sized task, and is **explicitly out of scope** for this phase — see
  § 9 for the open question this leaves.

**CI Milestone:** Phase 1, for the pure-logic slice only. Lint and typecheck
run over the *whole* codebase (they don't need live services either); the
test step covers only the pure-logic slice.

**Safety-ladder rung chosen: L3 (partial gate), matching the economic triage
already applied to the other repos audited this session.** This is a solo
local tool with no production users and no SLA. The LLM/DB-integrated
pipeline — which is most of the actual product behavior — stays
**quarantined from CI** as a named residual risk: no committed API keys, no
attempt to stand up ArcadeDB+Ollama as CI service containers for what is
ultimately a very small planning-time investment for a project this size.
That pipeline's only safety net remains the manual verification checklist
already in `CONTRIBUTING.md` (ingest a document, exercise each query mode,
check citations/verification/comparison output by hand).

## 4. Target architecture

**Decision framework applied, per component:**

| Component | Verdict | Why |
|---|---|---|
| LangGraph pipelines, ArcadeDB client, Streamlit UI, `agents/`/`embeddings.py`/`config.py` | ✅ Keep as-is | Current stack, no EOL, `uv`-pinned already — the skill's own "don't gold-plate" rule applies directly |
| `pyproject.toml` / `uv.lock` | ✅ Keep as-is | Already exists, already correct — nothing to migrate |
| `ruff` / `ty` config | ✅ Keep as-is | Already configured, already passes clean |
| Pure-logic functions (`utils.py`, `agents/comparator.py::_grouped_context`) | 🔄 Wrap/adapt → collect under `pytest` | Not a code change — a collection-mechanism change. The logic itself is untouched. |
| CI | 🗑️→➕ Add (none exists to remove) | Author `.github/workflows/ci.yml`: lint + typecheck (whole repo) + pytest (pure-logic slice only) |

No "Upgrade in place," "Swap dependency," or "Rewrite" work is needed
anywhere — there is nothing old enough to upgrade and nothing broken enough
to rewrite. This mirrors the other two repos audited this session.

#### ADR: Test only the pure-logic slice in CI; quarantine the LLM/DB pipeline explicitly

- **Context:** the Testability Milestone requires a test runner that executes
  and passes ≥1 meaningful test *in CI*. Most of this codebase's logic is
  inseparably wired to a live Ollama call or a live ArcadeDB query.
- **Decision:** write real `pytest` tests only for functions genuinely
  callable with no LLM/DB/network dependency (`utils.py`'s four helpers,
  `agents/comparator.py::_grouped_context`), and state in
  `CONTRIBUTING.md`/`ARCHITECTURE.md` that the LLM/DB-integrated pipeline is
  *not* covered by automated tests today — this is honest scoping, not a
  gap being hidden.
- **Alternatives considered:** (a) mock ArcadeDB/Ollama at the HTTP layer to
  test more of `agents/graph_builder.py`/`agents/retriever.py` — rejected for
  Phase 1 as a larger, separate effort (building and maintaining a mock
  ArcadeDB REST surface) disproportionate to a solo local tool; (b) stand up
  ArcadeDB + Ollama as CI service containers for true integration tests —
  rejected as expensive (slow CI, needs model-pull time) for the same reason,
  and explicitly against `CONTRIBUTING.md`'s own stance of not committing
  test API keys or making live calls from CI (mirrors the other two repos'
  ADRs this session).
- **Consequences:** Phase 1 ships a real, if narrow, CI gate. The product's
  actual behavior (extraction quality, retrieval relevance, answer
  groundedness) remains manually verified only — named as residual risk, not
  silently accepted.

## 5. Per-feature migration analysis

Only one "feature" is migrating: the build/verification tooling itself. Every
product feature (ingestion, retrieval, answering, comparison, verification) is
unaffected — ✅ keep as-is, per § 4.

- **Current implementation:** `uv` + `pyproject.toml`/`uv.lock` (already
  correct), `ruff`/`ty` (already configured and passing), no test runner, no CI.
- **Migration strategy:** Strategy C (wire up what's already there — § 3),
  tactic: incremental refactor of verification tooling only, no logic changes.
- **Testability status:** the pure-logic slice crosses the Testability
  Milestone within this single phase, safety rung L3. The LLM/DB-integrated
  pipeline does not cross it this phase — residual risk named, manual
  verification remains its only net.
- **Dependencies and coupling:** touches only new files (`tests/`,
  `.github/workflows/ci.yml`) plus one doc update
  (`ARCHITECTURE.md`/`CONTRIBUTING.md` noting what CI does and doesn't cover)
  — nothing in `agents/`, `db/`, `graph.py`, `config.py`, `embeddings.py`, or
  `app.py` changes.
- **Effort estimate:** XS (extra small) — five small pure-function tests plus
  one CI YAML file. No logic changes, no dependency changes.
- **Risk assessment:** near-zero. The only failure mode is a CI runner
  Python-version mismatch with the pinned `uv.lock` resolution — mitigated by
  pinning the CI job's Python version to match what's locally verified working.
- **Acceptance criteria:** `uv sync --frozen` installs cleanly on a fresh
  clone/CI runner; `uv run pytest` collects and passes all new tests;
  `uv run ruff check .` and `uv run ty check` both pass; the new
  `.github/workflows/ci.yml` runs and is green on this phase's own PR.

## 6. Phased implementation plan

**Phase gating is regime-aware.** The pure-logic slice is **post-testability
("lit")** from the moment its tests are written — exit criteria are runnable
commands / green CI. The LLM/DB-integrated pipeline stays **pre-testability
("dark")** this phase — its only exit criterion is the existing manual
verification checklist, not a test suite it cannot run in CI.

**Hazard red-team (Phase 2.5), walked against every class:**

- **H1** (incomplete quarantine) — N/A: nothing is being removed. Cleared.
- **H2** (framework-major codemod) — N/A: no framework major version bump. Cleared.
- **H3** (runtime/deployment lockstep) — N/A: no runtime version change. Cleared.
- **H4** (route-class enumeration) — N/A: no edge/gateway/auth rewrite. Cleared.
- **H5** (stateful data-store major) — N/A: ArcadeDB itself is untouched by
  this phase; `arcadedb-data/` is not written to by anything in this plan. Cleared.
- **H6** (transitional-insecure state) — N/A: this phase introduces no
  weakened security state. (The existing ArcadeDB default-credential/binding
  concern is pre-existing and already tracked in `SECURITY.md`, not
  introduced or worsened by this phase.) Cleared.
- **H7** (stacked-PR trunk drift) — N/A in practice: single-phase plan, one
  branch from `main`, one PR back to `main`. Cleared by construction.
- **H8** (living-doc drift) — **Triggered.** This phase adds `tests/` and
  `.github/workflows/ci.yml` (new topology). **Plan action, folded into this
  phase's tasks:** update `ARCHITECTURE.md`'s Commands & Verification
  Inventory and Data/APIs/CI/CD/testing sections, and add a short note to
  `CONTRIBUTING.md` pointing at the new `pytest`/CI commands alongside the
  existing manual-verification checklist (not replacing it).

### Phase 1: Test the pure-logic slice, stand up CI (T-shirt size: XS)

**Goal:** Give the codebase its first real, automated, CI-enforced safety net
— scoped honestly to what can actually be tested without live services.
**Regime:** post-testability ("lit") for the pure-logic slice; the
LLM/DB-integrated pipeline remains pre-testability ("dark") and out of scope.
**Safety rung:** L3 (partial gate) — deliberate, not a downgrade from failure.
**Prerequisites:** none — this is the first and only phase.
**Duration estimate:** well under a sprint.

#### Tasks

| ID | Task | Component | Blocked by |
|----|------|-----------|------------|
| 1.1 | Add `pytest` as a dev dependency (`uv add --dev pytest`) | tooling | — |
| 1.2 | Create `tests/test_utils.py`: `safe_json_loads` (valid JSON, fenced JSON, malformed input → `None`), `chunk_page_text` (multi-chunk splitting, empty-text → `[]`), `truncate` (short text unchanged, long text truncated with ellipsis), `new_id` (prefix present) | tests | 1.1 |
| 1.3 | Create `tests/test_comparator.py`: `_grouped_context` (multi-document grouping, empty input → empty context) | tests | 1.1 |
| 1.4 | Author `.github/workflows/ci.yml`: `uv sync --frozen` → `uv run ruff check .` → `uv run ty check` → `uv run pytest -v`, on push/PR to `main`, pinned to the locally-verified Python version | CI | 1.2, 1.3 |
| 1.5 | Update `ARCHITECTURE.md`'s Commands & Verification Inventory and Data/APIs/CI/CD/testing sections to reflect the new `pytest`/CI reality (H8) | docs | 1.4 |
| 1.6 | Add a short "Automated checks" note to `CONTRIBUTING.md` pointing at `uv run pytest`, `ruff`, `ty`, alongside (not replacing) the existing manual verification checklist (H8) | docs | 1.4 |

#### Risks & Mitigations

- **Risk:** CI runner's Python version resolves dependencies differently
  than the local dev environment. → **Mitigation:** pin the CI job's Python
  version explicitly to match what `uv.lock` was generated against; verify
  green on the phase's own PR before merging.
- **Risk:** a future contributor assumes "CI is green" means the whole app
  works, including retrieval/answer quality. → **Mitigation:** task 1.5/1.6
  state explicitly, in the docs, what CI does and does not cover.

#### Decisions made

- **Dropped:** any attempt to test the LLM/DB-integrated pipeline in CI this
  phase (mocked or via service containers) — not deferred, actually dropped
  as a Phase-1 goal for a solo local tool of this size. Revisit only if the
  project gains real users/an SLA (see § 3 economic triage).
- **Resolved:** `pytest` as the test runner (matches the ecosystem norm and
  what's already implied by the dev-dependency-group pattern `ruff`/`ty`
  already use) — no further discussion needed to execute.

#### Verification & Exit Criteria (Definition of Done)

- [ ] `uv sync --frozen` installs cleanly (already true; re-confirmed after
      adding `pytest`).
- [ ] `uv run pytest -v` collects and passes all new tests.
- [ ] `uv run ruff check .` and `uv run ty check` both still pass.
- [ ] `.github/workflows/ci.yml` runs and is green on this phase's own PR —
      the authoritative signal for a lit-regime phase.
- [ ] `ARCHITECTURE.md` and `CONTRIBUTING.md` both reflect the new
      commands and explicitly scope what CI does/doesn't cover (H8 closed
      in the same PR).
- [ ] No behavior change asserted: the app still runs identically via
      `uv run streamlit run app.py`.

## 7. Execution governance

- **Branch per phase:** single branch (e.g. `modernize/ci-and-unit-tests`)
  cut from `main`, one PR back to `main`. No stacking risk (H7 cleared by
  construction).
- **Trunk:** confirmed `main` is the only branch in this repo.
- **Gate:** green CI on the PR is authoritative for the pure-logic slice
  (lit regime). The LLM/DB pipeline's "gate" remains the existing manual
  verification checklist (dark regime) — not blocked by this PR's CI.
- **CI Milestone and enforcement:** Phase 1 authors `.github/workflows/ci.yml`.
  **Turning it into a required status check / branch-protection rule is a
  manual step in GitHub → Settings → Branches that this plan cannot perform**
  — recorded as an open item in § 9.
- **Living docs:** `ARCHITECTURE.md`/`CONTRIBUTING.md` updates are tasks
  1.5–1.6 in the same phase, not a follow-up (H8).
- **`.github/copilot-instructions.md`:** confirmed no prior file existed at
  the start of this pass — the companion file is a fresh file, not a merge.

## 8. Migration safety net

- **Feature flags:** none needed — this phase changes no runtime behavior,
  only build/verification tooling.
- **Data migration:** none — ArcadeDB's schema and data are untouched.
- **Rollback plan:** revert the single PR. Nothing else depends on the new
  files, so reverting is a clean no-op for the rest of the app.
- **Transitional-insecure-state register:** empty — this phase introduces none.
- **Oracle & seam contracts:** none needed for a purely additive, no-behavior-
  change phase; the five new tests are their own oracle (each asserts a
  known-correct input→output pair for an existing, unchanged function).
- **Testing strategy:** `pytest` covers the pure-logic slice only. The
  LLM/DB-integrated pipeline (ingestion graph, query graph, ArcadeDB client,
  embeddings) remains covered only by `CONTRIBUTING.md`'s manual verification
  checklist — named residual risk, not silently accepted.
- **Observability:** N/A — no deployed service to observe.

## 9. Open questions / decisions needed from stakeholders

1. **Manual platform step the agent cannot perform:** after Phase 1's CI is
   green, a human must go to GitHub → Settings → Branches and add
   `.github/workflows/ci.yml`'s job as a required status check on `main` for
   it to actually block merges. Until that's done, CI runs but doesn't gate.
2. If real users or an SLA ever attach to this project, revisit whether the
   LLM/DB-integrated pipeline deserves a real integration-test investment
   (mocked ArcadeDB/Ollama, or CI service containers) — not urgent today,
   and deliberately dropped rather than deferred for the current project shape.
3. **`[DECISION NEEDED]`** Should a future pass also pin the two Ollama model
   names (`qwen3.5:2b`, `nomic-embed-text-v2-moe`) to specific registry
   digests, given `ollama pull <name>` can silently resolve to a different
   underlying model version over time (ARCHITECTURE.md's EOL scan)? Out of
   scope for this phase; flagged here so it isn't forgotten.
