# Post-BUILD35 Repository Closure Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a deterministic, whole-repository closure audit after BUILD35 without inventing BUILD36 or deleting historical material during classification.

**Architecture:** A canonical JSON inventory classifies every discovered top-level Python subsystem and historical tool namespace, plus required repository surfaces. A stdlib-only validator enforces closed classifications, exact discovered-path coverage, path existence, and classification-specific disposition rules; a concise engineering report explains the resulting authority and remediation decisions.

**Tech Stack:** CPython 3.11 standard library, JSON, `unittest`, existing manifest-driven validation.

## Global Constraints

- Campaign identity is `POST-BUILD35-REPOSITORY-CLOSURE-001`; this is not BUILD36.
- Allowed classifications are exactly `CANONICAL`, `WRAPPED`, `RETAINED_SUPPORTING`, `SUPERSEDED`, `DUPLICATE`, `DEAD`, and `UNINTEGRATED`.
- Classification is non-destructive; removal, consolidation, integration, or retirement is a separately reviewed follow-on action.
- Existing BUILD35 authority remains controlling until this audit explicitly records a narrower canonical responsibility.
- Runtime code remains CPython 3.11 and standard-library-only.
- Live validation is out of scope because no live-provider boundary changes.

---

### Task 1: Closure audit validator

**Files:**
- Create: `tools/repository_closure.py`
- Create: `tests/validation/test_repository_closure.py`

**Interfaces:**
- Consumes: a JSON audit path and repository root.
- Produces: `load_closure_audit(path: Path, repository_root: Path) -> ClosureAudit` and `ClosureAuditError`.

- [ ] **Step 1: Write failing synthetic-repository tests**

Test valid exact coverage, missing discovered coverage, invalid classification, and required canonical targets for wrapper-like dispositions.

- [ ] **Step 2: Run the focused test and verify RED**

Run: `.venv\Scripts\python.exe -m unittest tests.validation.test_repository_closure -v`

Expected: FAIL because `tools.repository_closure` does not exist.

- [ ] **Step 3: Implement the minimal stdlib-only validator**

Parse the closed schema, validate normalized relative paths and existing scope, discover configured child directories and Python files, reject missing or multiply classified coverage, and enforce classification-specific fields.

- [ ] **Step 4: Run the focused test and verify GREEN**

Run: `.venv\Scripts\python.exe -m unittest tests.validation.test_repository_closure -v`

Expected: PASS.

### Task 2: Canonical classification inventory

**Files:**
- Create: `artifacts/repository-closure/POST_BUILD35_SUBSYSTEM_CLASSIFICATION.json`
- Modify: `tests/validation/test_repository_closure.py`

**Interfaces:**
- Consumes: BUILD35 authority map, runtime composition/import evidence, validation manifest, provider duplication audit, and repository paths.
- Produces: one classification and disposition for every audited subsystem/surface.

- [ ] **Step 1: Write a failing repository-contract test**

Require the canonical artifact to validate, contain all seven classifications, retain BUILD35 as predecessor, and declare no classification-time deletion.

- [ ] **Step 2: Run the focused test and verify RED**

Expected: FAIL because the classification artifact is absent.

- [ ] **Step 3: Add the classification artifact**

Classify active authorities, compatibility wrappers, supporting contracts/evidence, superseded acceptance generations, unjustified duplicates, dead namespaces, and viable but uncomposed subsystems with evidence and follow-on dispositions.

- [ ] **Step 4: Run the focused test and verify GREEN**

Expected: PASS with exact discovered coverage.

### Task 3: Closure report and validation routing

**Files:**
- Create: `docs/engineering/POST_BUILD35_REPOSITORY_CLOSURE_AUDIT.md`
- Modify: `tools/validation_manifest.json`
- Modify: `README.md`

**Interfaces:**
- Consumes: validated classification artifact.
- Produces: human-readable findings, remediation queue, and changed-test routing.

- [ ] **Step 1: Route audit changes to the validation suite**

Add the validator, artifact, and report paths to the `validation` suite source globs.

- [ ] **Step 2: Publish the engineering report**

Document scope, definitions, classification summary, canonical authority conclusions, and non-destructive follow-on work.

- [ ] **Step 3: Update repository status**

Link the closure audit from `README.md` and state that the next campaign is post-BUILD35 closure, not BUILD36.

- [ ] **Step 4: Run changed and domain validation**

Run: `.venv\Scripts\python.exe tools\validate.py changed`

Run: `.venv\Scripts\python.exe tools\validate.py domain core`

Expected: PASS.

### Task 4: Full closure verification

**Files:**
- Verify only; do not rewrite historical artifacts.

**Interfaces:**
- Consumes: completed audit changes.
- Produces: offline full-suite evidence and final worktree review.

- [ ] **Step 1: Run the audit CLI**

Run: `.venv\Scripts\python.exe tools\repository_closure.py --audit artifacts\repository-closure\POST_BUILD35_SUBSYSTEM_CLASSIFICATION.json --repository-root .`

Expected: JSON summary with `status` equal to `PASS`.

- [ ] **Step 2: Run full offline validation**

Run: `.venv\Scripts\python.exe tools\validate.py full`

Expected: PASS with no live tests.

- [ ] **Step 3: Review diffs and preserve unrelated user changes**

Run: `git status --short` and `git diff --check`.

Expected: only closure-audit changes plus pre-existing user changes; no whitespace errors.

