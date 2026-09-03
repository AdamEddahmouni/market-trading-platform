# Monorepo History Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a complete, organized, reproducible paper trail for every commit reachable from every local ref in the parent and child repositories.

**Architecture:** A standard-library Python generator reads Git object data from the independent source repositories and emits deterministic JSONL and Markdown audit artifacts in the parent repository. CI validates the committed artifacts and the existing workspace manifest without requiring child repositories in hosted checkouts.

**Tech Stack:** Python 3.11 standard library, Git CLI, Markdown, JSONL, GitHub Actions.

## Global Constraints

- Child repositories are read-only inputs; no child commit, checkout, ref, remote, visibility, or working-tree mutation is permitted.
- Every reachable commit from every local Git ref is included.
- Commit messages and linked documentation are the only rationale sources.
- Missing rationale is labeled, never inferred as fact.
- Generated output must be deterministic.
- Parent `main` remains protected and changes land through a PR.

---

### Task 1: Define and test Git history parsing

**Files:**
- Create: `tests/test_history_ledger.py`
- Create: `tools/generate_history_ledger.py`

**Interfaces:**
- `parse_commit_object(raw: bytes) -> dict[str, object]`
- `rationale_status(subject: str, body: str) -> str`
- `render_repository_markdown(repository: str, records: list[dict[str, object]]) -> str`

- [ ] **Step 1: Write failing parser and rendering tests**
- [ ] **Step 2: Run `python -m unittest tests.test_history_ledger -v` and confirm the missing implementation fails**
- [ ] **Step 3: Implement standard-library commit parsing and deterministic rendering**
- [ ] **Step 4: Run the focused tests and confirm they pass**
- [ ] **Step 5: Commit the parser and tests**

### Task 2: Generate the complete audit artifact

**Files:**
- Modify: `tools/generate_history_ledger.py`
- Create: `docs/history/WORK_LEDGER.jsonl`
- Create: `docs/history/REFS.json`
- Create: `docs/history/INDEX.md`
- Create: `docs/history/repositories/*.md`

**Interfaces:**
- `generate(root: Path, output_dir: Path, check: bool = False) -> None`
- `collect_repository_history(root: Path, repository: str) -> tuple[list[dict[str, object]], dict[str, str]]`

- [ ] **Step 1: Add tests for all-ref collection and stable output**
- [ ] **Step 2: Run the focused tests and confirm the new behavior fails**
- [ ] **Step 3: Implement parent and manifest-child ref discovery**
- [ ] **Step 4: Emit complete JSONL, refs, index, and repository timelines**
- [ ] **Step 5: Run generation and focused tests**
- [ ] **Step 6: Commit the generated audit artifacts**

### Task 3: Add freshness and CI enforcement

**Files:**
- Modify: `tools/generate_history_ledger.py`
- Modify: `.github/workflows/monorepo-guardrails.yml`
- Modify: `docs/MONOREPO_WORKFLOW.md`

- [ ] **Step 1: Add tests for `--check` and malformed ledger detection**
- [ ] **Step 2: Run tests and confirm the checks fail before implementation**
- [ ] **Step 3: Implement deterministic temporary regeneration and comparison**
- [ ] **Step 4: Add the audit freshness command to CI**
- [ ] **Step 5: Document regeneration and rationale provenance**
- [ ] **Step 6: Run local validation, tests, and diff checks**
- [ ] **Step 7: Commit, push a review branch, and open a PR**

### Task 4: Merge and verify

- [ ] **Step 1: Wait for required CI checks**
- [ ] **Step 2: Merge through protected PR flow**
- [ ] **Step 3: Verify parent `main`, audit artifacts, and branch protection**
