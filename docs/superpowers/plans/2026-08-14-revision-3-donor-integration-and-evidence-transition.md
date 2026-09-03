# Revision 3 Donor Integration and Evidence Transition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the approved Revision 3 architecture operational as canonical documentation, register both new donors without copying or modifying them, and publish a fresh immutable Phase 0 candidate evidence root bound to the new repository subject.

**Architecture:** Preserve Revision 1, Revision 2, both prior evidence directories, and every donor byte. Add immutable authority and donor-governance records, detailed donor/reference documentation, and a manifest-driven authority resolver that replaces the evidence collector's hard-coded canonical-status claim. Generate a new candidate root only after all documentation, tests, offline checks, and donor-preservation comparisons pass.

**Tech Stack:** CPython 3.11 standard library, canonical JSON, Markdown, PowerShell read-only inventory commands, local Git with no remote, and the existing `market_platform_foundation` Phase 0 tools.

## Global Constraints

- The workspace root is a collection directory; `integrated-market-platform/` is the only canonical Git repository.
- Do not edit, move, rename, copy from, execute, install from, or initialize Git inside any donor/reference project.
- Do not edit Revision 1, Revision 2, Revision 3, either prior hash-addressed Phase 0 evidence directory, or any existing approved governance artifact.
- Revision 3 is approved only at SHA-256 `7C6AE5FC9037CA37D44CD1A2FAACD0CB821192920C46CF001541DCD2121FEB35`.
- The approval statement is exactly: `I approve foundation.canonical_specification.revision_3 at SHA-256 7C6AE5FC9037CA37D44CD1A2FAACD0CB821192920C46CF001541DCD2121FEB35.`
- Phase 0 remains blocked pending postroot reviews, approvals, acceptance index, and deterministic final gate.
- Phase 0A, provider/broker connections, market-model implementation, whale ingestion, AI integration, paper orders, and live trading remain unauthorized.
- No network access, package installation, provider access, remote Git operation, or donor runtime execution is permitted.
- Never publish secret values, account identifiers, password hashes, database rows, conversation/message contents, or sensitive absolute paths.
- No football data, donor database, forecast CSV, or donor source file enters the canonical repository.
- Preserve separate evidence dimensions; do not create an opaque universal whale score or buy score.
- Preserve forecast -> strategy -> intent -> independent risk -> authorized execution -> accounting separation.

---

### Task 1: Record the exact Revision 3 authority

**Files:**

- Create: `docs/superpowers/governance/2026-08-14-foundation-revision-3-approval.json`
- Create: `manifests/phase0/canonical-authority.json`
- Create: `docs/superpowers/governance/2026-08-14-revision-3-repository-registration-supplement.json`

**Interfaces:**

- Consumes: approved Revision 3 bytes at SHA-256 `7C6AE5FC9037CA37D44CD1A2FAACD0CB821192920C46CF001541DCD2121FEB35`.
- Produces: one exact approval record and one active-authority manifest for the evidence resolver.

- [ ] **Step 1: Reverify the approved specification and clean repository state**

Run:

```powershell
Get-FileHash -Algorithm SHA256 -LiteralPath docs\superpowers\specs\2026-08-14-integrated-market-platform-foundation-design-revision-3.md
git -c safe.directory=C:/Users/adame/Desktop/market-trading-platform/integrated-market-platform status --short --branch
git -c safe.directory=C:/Users/adame/Desktop/market-trading-platform/integrated-market-platform remote -v
```

Expected: the specification hash is exactly `7C6AE5FC9037CA37D44CD1A2FAACD0CB821192920C46CF001541DCD2121FEB35`, branch is `main`, the worktree is clean, and no remote is printed. Stop without writing on any difference.

- [ ] **Step 2: Create the canonical approval record**

Write this canonical JSON plus one LF and no BOM:

```json
{"approval_date":"2026-08-14","approval_statement":"I approve foundation.canonical_specification.revision_3 at SHA-256 7C6AE5FC9037CA37D44CD1A2FAACD0CB821192920C46CF001541DCD2121FEB35.","approver_capacities":["PROJECT_OWNER","RELEASE_OWNER"],"artifact_type":"CANONICAL_SPECIFICATION_APPROVAL","effect":"Revision 3 becomes the sole forward-looking canonical foundation authority while Revision 2 continues to control the authorized Phase 0 safety subject; no phase transition or later-phase implementation is authorized.","logical_id":"foundation.canonical_specification.revision_3.approval","principal_id":"PROJECT-PRINCIPAL-001","sanitization":{"absolute_paths_included":false,"account_identifiers_included":false,"credential_values_included":false,"remote_urls_included":false},"schema_version":"1.0.0","specification_logical_id":"foundation.canonical_specification.revision_3","specification_sha256":"7C6AE5FC9037CA37D44CD1A2FAACD0CB821192920C46CF001541DCD2121FEB35","status":"APPROVED"}
```

Run `Get-FileHash -Algorithm SHA256` on the record. Expected: `922C14AFC16E4BB7F042703D064B0783F2C049F5060982545355194D2638CE70`.

- [ ] **Step 3: Create the active canonical-authority manifest**

Write canonical JSON with these exact semantic bindings:

```json
{
  "active_specification": {
    "approval_logical_id": "foundation.canonical_specification.revision_3.approval",
    "approval_path": "docs/superpowers/governance/2026-08-14-foundation-revision-3-approval.json",
    "approval_sha256": "922C14AFC16E4BB7F042703D064B0783F2C049F5060982545355194D2638CE70",
    "logical_id": "foundation.canonical_specification.revision_3",
    "path": "docs/superpowers/specs/2026-08-14-integrated-market-platform-foundation-design-revision-3.md",
    "sha256": "7C6AE5FC9037CA37D44CD1A2FAACD0CB821192920C46CF001541DCD2121FEB35"
  },
  "incorporated_specifications": [
    {
      "logical_id": "foundation.canonical_specification.revision_1",
      "path": "docs/superpowers/specs/2026-08-13-integrated-market-platform-foundation-design.md",
      "sha256": "B4EAE3240F6F968A6B393263D849013259A00187E209C8632E38DE890996D04D"
    },
    {
      "logical_id": "foundation.canonical_specification.revision_2",
      "path": "docs/superpowers/specs/2026-08-14-integrated-market-platform-foundation-design-revision-2.md",
      "sha256": "56F6C424EF83BE6042E06D716F3BBE87A1E1B7FE7EBEB15B7EECD875131BC06A"
    }
  ],
  "manifest_version": "1.0.0",
  "phase0_authority": {
    "logical_id": "foundation.canonical_specification.revision_2",
    "path": "docs/superpowers/specs/2026-08-14-integrated-market-platform-foundation-design-revision-2.md",
    "sha256": "56F6C424EF83BE6042E06D716F3BBE87A1E1B7FE7EBEB15B7EECD875131BC06A"
  },
  "phase0_status": "BLOCKED_PENDING_POSTROOT_ACCEPTANCE",
  "status": "EFFECTIVE"
}
```

Serialize it with recursively sorted keys and compact separators using `write_canonical_json`; do not hand-format the committed manifest.

- [ ] **Step 4: Register the new immutable authority artifacts**

Create the registration supplement as canonical JSON. It must bind the Revision 3 path/hash, approval path/hash, authority-manifest path/hash, this implementation-plan path/hash, the prior repository-registration logical ID/hash, `repository_root_id: ROOT-2E7C91F4`, `status: REGISTERED_SUPPLEMENT`, and sanitization flags all `false`. It must state that no prior registration record is superseded or edited.

- [ ] **Step 5: Verify and commit only Task 1 files**

Run:

```powershell
git -c safe.directory=C:/Users/adame/Desktop/market-trading-platform/integrated-market-platform diff --check
python -m unittest discover -s tests/phase0 -v
```

Expected: no diff errors and all existing tests pass.

Commit:

```powershell
git -c safe.directory=C:/Users/adame/Desktop/market-trading-platform/integrated-market-platform add docs/superpowers/governance/2026-08-14-foundation-revision-3-approval.json manifests/phase0/canonical-authority.json docs/superpowers/governance/2026-08-14-revision-3-repository-registration-supplement.json
git -c safe.directory=C:/Users/adame/Desktop/market-trading-platform/integrated-market-platform commit -m "docs: register revision 3 authority"
```

---

### Task 2: Make canonical authority resolution fail closed

**Files:**

- Create: `src/market_platform_foundation/authority.py`
- Create: `tests/phase0/test_authority.py`
- Modify: `src/market_platform_foundation/evidence.py`
- Modify: `tests/phase0/test_pipeline.py`

**Interfaces:**

- Consumes: `manifests/phase0/canonical-authority.json` and every file/hash it binds.
- Produces: `resolve_canonical_authority(repository_root: Path) -> dict[str, object]` and evidence content that reports observed authority instead of a hard-coded `true`.

- [ ] **Step 1: Write failing authority-resolution tests**

Add tests that build a temporary repository with canonical JSON helpers and assert:

```python
def test_approved_revision_3_is_the_only_active_authority(self):
    result = resolve_canonical_authority(self.root)
    self.assertEqual(result["status"], "PASS")
    self.assertTrue(result["one_canonical_specification"])
    self.assertEqual(
        result["active_logical_id"],
        "foundation.canonical_specification.revision_3",
    )

def test_changed_active_specification_fails(self):
    self.active_spec.write_text("changed\n", encoding="utf-8")
    result = resolve_canonical_authority(self.root)
    self.assertEqual(result["status"], "FAIL")
    self.assertIn("ACTIVE_SPECIFICATION_HASH_MISMATCH", result["reason_codes"])

def test_missing_approval_blocks(self):
    self.approval.unlink()
    result = resolve_canonical_authority(self.root)
    self.assertEqual(result["status"], "BLOCKED")
    self.assertIn("APPROVAL_RECORD_MISSING", result["reason_codes"])

def test_wrong_approval_binding_fails(self):
    approval = load_json_strict(self.approval)
    approval["specification_sha256"] = "0" * 64
    write_canonical_json(self.approval, approval)
    result = resolve_canonical_authority(self.root)
    self.assertEqual(result["status"], "FAIL")
    self.assertIn("APPROVAL_BINDING_MISMATCH", result["reason_codes"])
```

Run: `python -m unittest tests.phase0.test_authority -v`.

Expected: import failure because `authority.py` does not exist.

- [ ] **Step 2: Implement the resolver**

Implement these rules in `authority.py`:

```python
from __future__ import annotations

from pathlib import Path

from .canonical import load_json_strict, sha256_bytes


def _result(status: str, reasons: list[str], **values: object) -> dict[str, object]:
    return {"reason_codes": sorted(set(reasons)), "status": status, **values}


def _verify_bound_file(root: Path, row: dict[str, object], missing: str, mismatch: str) -> tuple[str | None, str | None]:
    path = root / str(row.get("path", ""))
    if not path.is_file():
        return missing, None
    actual = sha256_bytes(path.read_bytes())
    if actual != str(row.get("sha256", "")):
        return mismatch, actual
    return None, actual


def resolve_canonical_authority(repository_root: Path) -> dict[str, object]:
    root = repository_root.resolve()
    manifest_path = root / "manifests" / "phase0" / "canonical-authority.json"
    if not manifest_path.is_file():
        return _result("BLOCKED", ["AUTHORITY_MANIFEST_MISSING"], one_canonical_specification=False)
    try:
        manifest = load_json_strict(manifest_path)
    except (OSError, UnicodeError, ValueError):
        return _result("FAIL", ["AUTHORITY_MANIFEST_INVALID"], one_canonical_specification=False)
    if not isinstance(manifest, dict) or manifest.get("status") != "EFFECTIVE":
        return _result("BLOCKED", ["AUTHORITY_MANIFEST_NOT_EFFECTIVE"], one_canonical_specification=False)
    active = manifest.get("active_specification")
    phase0 = manifest.get("phase0_authority")
    incorporated = manifest.get("incorporated_specifications")
    if not isinstance(active, dict) or not isinstance(phase0, dict) or not isinstance(incorporated, list):
        return _result("FAIL", ["AUTHORITY_MANIFEST_SHAPE_INVALID"], one_canonical_specification=False)
    reason, _actual = _verify_bound_file(root, active, "ACTIVE_SPECIFICATION_MISSING", "ACTIVE_SPECIFICATION_HASH_MISMATCH")
    if reason:
        return _result("BLOCKED" if reason.endswith("MISSING") else "FAIL", [reason], one_canonical_specification=False)
    approval_path = root / str(active.get("approval_path", ""))
    if not approval_path.is_file():
        return _result("BLOCKED", ["APPROVAL_RECORD_MISSING"], one_canonical_specification=False)
    approval_sha256 = sha256_bytes(approval_path.read_bytes())
    if approval_sha256 != str(active.get("approval_sha256", "")):
        return _result("FAIL", ["APPROVAL_RECORD_HASH_MISMATCH"], one_canonical_specification=False)
    try:
        approval = load_json_strict(approval_path)
    except (OSError, UnicodeError, ValueError):
        return _result("FAIL", ["APPROVAL_RECORD_INVALID"], one_canonical_specification=False)
    if not isinstance(approval, dict) or any(
        (
            approval.get("status") != "APPROVED",
            approval.get("logical_id") != active.get("approval_logical_id"),
            approval.get("specification_logical_id") != active.get("logical_id"),
            approval.get("specification_sha256") != active.get("sha256"),
        )
    ):
        return _result("FAIL", ["APPROVAL_BINDING_MISMATCH"], one_canonical_specification=False)
    for row in [phase0, *incorporated]:
        if not isinstance(row, dict):
            return _result("FAIL", ["INCORPORATED_BINDING_INVALID"], one_canonical_specification=False)
        reason, _actual = _verify_bound_file(root, row, "INCORPORATED_SPECIFICATION_MISSING", "INCORPORATED_SPECIFICATION_HASH_MISMATCH")
        if reason:
            return _result("BLOCKED" if reason.endswith("MISSING") else "FAIL", [reason], one_canonical_specification=False)
    return _result(
        "PASS",
        [],
        active_logical_id=str(active["logical_id"]),
        active_path=str(active["path"]),
        active_sha256=str(active["sha256"]),
        approval_logical_id=str(active["approval_logical_id"]),
        approval_sha256=approval_sha256,
        authority_manifest_sha256=sha256_bytes(manifest_path.read_bytes()),
        incorporated_specification_count=len(incorporated),
        one_canonical_specification=True,
        phase0_status=str(manifest.get("phase0_status", "BLOCKED")),
    )
```

Use `any((...))` exactly as shown so every comparison is a Boolean and no status text alone can prove approval.

- [ ] **Step 3: Replace the evidence collector's hard-coded claim**

In `build_preassertion_content`, call:

```python
from .authority import resolve_canonical_authority

authority = resolve_canonical_authority(root)
```

Replace:

```python
"one_canonical_specification": True,
```

with:

```python
"canonical_authority": authority,
"one_canonical_specification": authority.get("one_canonical_specification", False),
```

Update `test_pipeline.py` so the collector test creates a valid temporary authority manifest or runs against the governed repository and asserts the authority status is `PASS`, the active logical ID is Revision 3, and the exact active hash matches.

- [ ] **Step 4: Run focused and full tests**

Run:

```powershell
python -m unittest tests.phase0.test_authority -v
python -m unittest tests.phase0.test_pipeline -v
python -m unittest discover -s tests/phase0 -v
```

Expected: zero failures and zero errors.

- [ ] **Step 5: Commit the fail-closed resolver**

```powershell
git -c safe.directory=C:/Users/adame/Desktop/market-trading-platform/integrated-market-platform add src/market_platform_foundation/authority.py src/market_platform_foundation/evidence.py tests/phase0/test_authority.py tests/phase0/test_pipeline.py
git -c safe.directory=C:/Users/adame/Desktop/market-trading-platform/integrated-market-platform commit -m "feat: verify canonical revision authority"
```

---

### Task 3: Publish donor inventories, rights, and traceability

**Files:**

- Create: `docs/research/donors/DS340W_NOTES.md`
- Create: `docs/research/donors/GRID_IQ_NOTES.md`
- Create: `docs/research/donors/DONOR_REUSE_MATRIX.md`
- Create: `docs/superpowers/governance/2026-08-14-donor-code-permissions.json`
- Create: `docs/superpowers/governance/2026-08-14-revision-3-donor-preservation-before.json`
- Create: `docs/superpowers/governance/2026-08-14-revision-3-donor-preservation-difference.json`
- Create: collection-root `DS340W_NOTES.md`
- Create: collection-root `GRID_IQ_NOTES.md`
- Modify: collection-root `PROJECT_NOTES_INDEX.md`

**Interfaces:**

- Consumes: read-only donor snapshots and Revision 3 reuse vocabulary.
- Produces: source-backed donor notes, rights record, component-to-canonical mapping, and value-blind proof that donor bytes were not changed.

- [ ] **Step 1: Capture a value-blind before inventory for the two new donors**

Use the preservation method already defined by `phase0.prototype_preservation`:

- enumerate files without following reparse points;
- exclude `.git`, dependency trees, caches, environments, generated build output, logs, and credential-like paths;
- do not read or publish credential values;
- represent credential-like paths only by opaque path ID, size, and metadata digest;
- represent files at least 10 MiB by size/metadata, not content hash;
- hash included records as `normalized_relative_path|byte_length|file_sha256`, sorted ordinally and LF-joined without a trailing LF.

The before record must contain separate rows for root IDs `PROTO-DS340W-001` and `PROTO-GRIDIQ-001`, observed nested paths, Git state `UNAVAILABLE_NO_GIT_METADATA`, safe file counts/digests, sensitive path counts/digests, large-file counts/digests, exclusions, and sanitization. It must not contain database rows, spreadsheet values, CSV values, secret values, remote URLs, or absolute paths.

- [ ] **Step 2: Write the DS-340W notes**

Required sections and facts:

- exact observed nested path and no Git metadata;
- purpose and R/nflverse dependencies;
- source code inspected, including ARIMA, ARIMAX, NN, preprocessing, fallback, parallelization, and output scripts;
- dataset inventory: workbook size/schema summary and all derived CSV filenames, row counts, and headers without row values;
- no repository license, lock, automated tests, or deterministic seed contract;
- explicit defect: actual holdout-period exogenous rows feed ARIMAX/NN comparison;
- classification table using `PORT_ADAPT`, `CONCEPT_ONLY`, and `DO_NOT_USE`;
- canonical destinations, phases, preconditions, and verification;
- statement that no football data or result is financial evidence.

- [ ] **Step 3: Write the GridIQ notes**

Required sections and facts:

- exact observed nested path and no Git metadata;
- FastAPI/SQLAlchemy/Pydantic backend and React/TypeScript frontend dependencies;
- representative Parquet, schedule, PBP cache, API, DTO, conversation, auth-state, query, validation, and chart code inspected;
- remote-first download, full-object memory load, fixed-path disk cache, season-count rather than byte bounds, missing-column fill, and downcast risks;
- license defect: root license absent and frontend license text incomplete;
- SQLite schema/count-only inventory: 196,608 bytes, 3 users, 12 conversations, 44 messages, and zero rows in game/play/cache tables at observation; no values inspected;
- explicit privacy exclusion for password hashes, users, messages, and conversations;
- dependency issues: `email-validator` unpinned and `pyarrow` required by README but absent from `requirements.txt`;
- no observed automated tests;
- classification table and canonical destinations.

- [ ] **Step 4: Write the exhaustive reuse matrix**

Create one row per meaningful component. Columns are:

```text
Donor | Component | Evidence path | Classification | Canonical destination | Phase | Preconditions | Verification | Rights state | Primary risk
```

At minimum include DS-340W ARIMA, ARIMAX, NN, preprocessing, fallback, entity parallelism, holdout comparison, dynamic installs, workbook, forecast/backtest outputs; and GridIQ Parquet projection, missing-column fill, schedule disk cache, PBP memory cache, TTL cache, FastAPI routers, DTO transformation, SQLAlchemy conversation persistence, model/token accounting, Gemini invocation, React Query, Zod, Zustand, charts, auth token storage, incomplete license, and bundled SQLite data.

- [ ] **Step 5: Record permissions conservatively**

The canonical JSON rights record must distinguish:

- user-reported Lucas email permission, with evidence state `PRIVATE_SOURCE_NOT_ATTACHED_TO_CANONICAL_REPOSITORY`;
- repository code-copy permission `ASSERTED_BUT_SCOPE_NOT_INDEPENDENTLY_VERIFIED`;
- DS-340W repository license `NOT_FOUND`;
- GridIQ root license `NOT_FOUND`;
- GridIQ frontend license `INCOMPLETE_TEXT_NOT_SUFFICIENT_FOR_MIT_CLAIM`;
- third-party dependency licenses `REQUIRE_SEPARATE_REVIEW`;
- nflverse rights `DONOR_UI_CLAIMS_CC_BY_4_0_NOT_INDEPENDENTLY_VERIFIED_IN_THIS_OFFLINE_TASK`;
- workbook/CSV/database rights `UNRESOLVED_DO_NOT_COPY_OR_REDISTRIBUTE`;
- direct-copy default `PROHIBITED_PENDING_ACCEPTED_ADR_DONOR_001`;
- preferred mode `INDEPENDENT_REIMPLEMENTATION`.

- [ ] **Step 6: Update the collection index without duplicating canonical notes**

Change “five independent projects” to “seven independent donor/reference projects plus the canonical platform.” Add rows linking the two top-level note files. Make each new top-level note a short pointer to its detailed canonical note plus a warning that the donor remains external and unchanged.

- [ ] **Step 7: Capture the after inventory and compare**

Recompute the exact Step 1 method. The difference record must report `PASS` only when both donor safe inventory digests, sensitive metadata digests, large metadata digests, file counts, and no-Git states are equal. Any mismatch stops implementation as `UNAUTHORIZED_DRIFT`; do not restore or edit a donor.

- [ ] **Step 8: Verify and commit canonical Task 3 files**

Run `git diff --check`, link checks, a forbidden-claim scan, and the full unit suite. Then commit only canonical files:

```powershell
git -c safe.directory=C:/Users/adame/Desktop/market-trading-platform/integrated-market-platform add docs/research/donors docs/superpowers/governance/2026-08-14-donor-code-permissions.json docs/superpowers/governance/2026-08-14-revision-3-donor-preservation-before.json docs/superpowers/governance/2026-08-14-revision-3-donor-preservation-difference.json
git -c safe.directory=C:/Users/adame/Desktop/market-trading-platform/integrated-market-platform commit -m "docs: register donor research references"
```

The collection-root notes are not committed because the collection root is not a Git repository.

---

### Task 4: Connect the canonical navigation and roadmap

**Files:**

- Modify: `README.md`
- Create: `docs/research/donors/README.md`
- Create: `docs/roadmap/REVISION_3_ROADMAP.md`
- Create: `docs/architecture/SWIM_WITH_THE_WHALES.md`
- Create: `docs/architecture/MODEL_RESEARCH_AND_DATASETS.md`

**Interfaces:**

- Consumes: Revision 3 and the donor evidence/matrix from Task 3.
- Produces: navigable canonical documentation with one authority source and supplemental implementation guidance.

- [ ] **Step 1: Update the canonical README**

Keep the existing no-capability statement. Add:

- active canonical Revision 3 link and approved exact hash;
- Phase 0 status `BLOCKED_PENDING_POSTROOT_ACCEPTANCE`;
- explicit statement that existing candidate roots bind older repository subjects;
- links to donor index, reuse matrix, roadmap, whale doctrine, and model/dataset architecture;
- explicit no provider, broker, model, whale-ingestion, AI-trading, paper, or live capability statement.

- [ ] **Step 2: Create a donor navigation index**

List seven external donors, exact observed collection paths, detailed note links for the two new donors, reuse-matrix link, permissions record link, and the rule that donors are not clean-clone/runtime dependencies.

- [ ] **Step 3: Publish a roadmap projection without changing phase authorization**

Create a concise projection of Revision 3 Section 20. It must mark Phase 0 and 0A unchanged, add only decision considerations to Phase 1, keep Phases 2–4 prerequisites intact, add institutional interfaces to Phase 5, define gated Phase 5R, and keep Phases 6–8 unchanged. Later Whale Intelligence, Research Assistant, and Research UI tracks remain separately authorized.

- [ ] **Step 4: Publish doctrine and model/dataset implementation guidance**

The whale document must include observe -> verify -> contextualize -> align when justified, the eight evidence families, fact/measurement/hypothesis/strategy separation, contradiction states, aligned/neutral/contrarian strategy declarations, no score collapse, provenance chains, and no risk bypass.

The model/dataset document must include dataset identity, cache determinism, point-in-time timestamps, research abstractions, target versioning, train-only preprocessing, future-covariate rules, model provenance, baselines, predictive versus strategy metrics, and future tests. Both documents state that Revision 3 is authoritative if any summary conflicts.

- [ ] **Step 5: Verify no duplicate authority claim and commit**

Run:

```powershell
rg -n -i "sole canonical|authoritative|phase 0.*pass|13f.*live|universal.*whale.*score|llm.*broker" README.md docs
git -c safe.directory=C:/Users/adame/Desktop/market-trading-platform/integrated-market-platform diff --check
python -m unittest discover -s tests/phase0 -v
```

Expected: Revision 3 is the sole active forward-looking authority; summaries defer to it; no false Phase 0 completion, live-13F, score-collapse, or LLM-broker claim exists.

Commit:

```powershell
git -c safe.directory=C:/Users/adame/Desktop/market-trading-platform/integrated-market-platform add README.md docs/research/donors/README.md docs/roadmap/REVISION_3_ROADMAP.md docs/architecture/SWIM_WITH_THE_WHALES.md docs/architecture/MODEL_RESEARCH_AND_DATASETS.md
git -c safe.directory=C:/Users/adame/Desktop/market-trading-platform/integrated-market-platform commit -m "docs: publish revision 3 roadmap guidance"
```

---

### Task 5: Bind a fresh immutable Phase 0 candidate evidence root

**Files:**

- Modify: `src/market_platform_foundation/evidence.py`
- Modify: `tests/phase0/test_pipeline.py`
- Create: `evidence/phase0/` one new hash-addressed run directory computed by the existing evaluator
- Preserve: both existing `evidence/phase0/2E1E...` and `evidence/phase0/6B31...` directories unchanged

**Interfaces:**

- Consumes: clean final documentation/code commits, active authority result, prior five-donor preservation difference, Revision 3 two-donor preservation difference, deterministic distribution inputs, and the active assertion registry.
- Produces: one coherent assertion run, aggregate, governance-verifier record, and candidate root for the new subject.

- [ ] **Step 1: Add the Revision 3 donor-preservation evidence member**

Extend `build_preassertion_content` to load:

```python
revision3_preservation_path = (
    root
    / "docs"
    / "superpowers"
    / "governance"
    / "2026-08-14-revision-3-donor-preservation-difference.json"
)
```

Return a new `phase0.revision3_donor_preservation_difference` content item containing its repository-relative path, byte length, SHA-256, declared result, and the two donor root IDs. Update the pipeline test's exact expected logical-ID set.

- [ ] **Step 2: Run focused red/green tests**

First add a test that fails because the new logical ID is absent. Then implement Step 1 and run:

```powershell
python -m unittest tests.phase0.test_pipeline -v
python -m unittest discover -s tests/phase0 -v
```

Expected: zero failures and zero errors.

- [ ] **Step 3: Commit the final evidence-source change**

```powershell
git -c safe.directory=C:/Users/adame/Desktop/market-trading-platform/integrated-market-platform add src/market_platform_foundation/evidence.py tests/phase0/test_pipeline.py
git -c safe.directory=C:/Users/adame/Desktop/market-trading-platform/integrated-market-platform commit -m "feat: bind revision 3 donor preservation evidence"
```

- [ ] **Step 4: Verify the clean subject before generation**

Run branch, HEAD, clean status, no-remote, authority-hash, donor-preservation, credential-location, import/route, full-test, and deterministic-build checks. Expected:

- clean `main`;
- no remote;
- authority resolver `PASS` for Revision 3;
- both new donors compare `PASS` without content changes;
- zero prohibited tracked credential-container paths;
- zero prohibited imports, dynamic loads, unresolved internal imports, or live/broker routes;
- full unit suite has zero failures/errors;
- two fresh builds have identical manifest/archive hashes.

- [ ] **Step 5: Produce one preselected evidence set and coherent assertion run**

Use the existing guarded tools. Create temporary inputs under a task-specific directory in the system temporary root, not under a donor. Bind:

- Revision 3 specification hash;
- Revision 3 approval and authority-manifest hashes;
- controlling Phase 0 plan and Revision 2 hashes;
- final Git subject manifest hash;
- active registry hash and mandatory-set hash;
- distribution/build, offline-install, denied-network, credential, import/route, registry, both preservation, and local-artifact evidence;
- assertion observations derived from evidence, never from desired status.

Set `GOV-001` `PASS` only if `resolve_canonical_authority` returns `PASS` with exactly one active Revision 3 specification. Keep the Phase 0 aggregate distinct from final Phase 0 acceptance.

Compute `$runId` from canonical run-manifest bytes with `run_id` omitted, create `evidence/phase0/$runId` once, and never overwrite an existing directory.

- [ ] **Step 6: Evaluate and verify the candidate root twice**

Run:

```powershell
python -I -m market_platform_foundation evaluate-phase0 --run-manifest $runManifest --output-dir $runDirectory
python -I -m market_platform_foundation verify-governance --evaluation-dir $runDirectory --output-dir $runDirectory
```

Independently recompute the ordered candidate tuple array and SHA-256 in a second temporary process. Expected: run IDs, result membership, aggregate, tuple array, member count, and candidate root match exactly. A passing assertion aggregate is still not a Phase 0 pass.

- [ ] **Step 7: Scan generated evidence before publication**

Verify every member hash, canonical JSON encoding, LF/no-BOM, logical-ID uniqueness, sanitization flags, no absolute path, no remote URL, no provider payload, no secret/account value, no donor data, and no postroot acceptance artifact. Confirm both old evidence directories' recursive digests are unchanged.

- [ ] **Step 8: Commit only the new immutable run directory**

```powershell
git -c safe.directory=C:/Users/adame/Desktop/market-trading-platform/integrated-market-platform add (Join-Path evidence/phase0 $runId)
git -c safe.directory=C:/Users/adame/Desktop/market-trading-platform/integrated-market-platform commit -m "chore: publish revision 3 phase 0 candidate root"
```

Do not create the two independent AI reviews, candidate-root approval records, acceptance index, final acceptance result, or Phase 0 `PASS` in this task.

---

### Task 6: Adversarial review and final handoff

**Files:**

- Modify only if the review discovers a defect: the smallest non-immutable supporting file that fixes it
- Never modify: approved Revision 3, prior evidence, donor paths, or the new finalized evidence directory

**Interfaces:**

- Consumes: complete Git history/diff, new candidate evidence, donor notes, reuse matrix, permissions, roadmap, doctrine, model/dataset guidance, and test output.
- Produces: the final structured report required by Revision 3 and the original donor-integration request.

- [ ] **Step 1: Run the adversarial claim and boundary review**

Search for look-ahead, actual future covariates, survivor/revision leakage, score collapse, provider/Gemini coupling, unsupported whale identity/intent, AI execution authority, DTO-as-contract language, duplicated architecture authority, premature implementation, license overclaim, 13F-as-live language, options-direction certainty, OHLCV-as-depth/aggressor claims, and profitability claims.

Expected: donor defects are described as defects; canonical proposals include guards; no prohibited claim appears as platform capability.

- [ ] **Step 2: Run fresh verification-before-completion commands**

Run:

```powershell
python -m unittest discover -s tests/phase0 -v
git -c safe.directory=C:/Users/adame/Desktop/market-trading-platform/integrated-market-platform diff --check 68d0069..HEAD
git -c safe.directory=C:/Users/adame/Desktop/market-trading-platform/integrated-market-platform status --short --branch
git -c safe.directory=C:/Users/adame/Desktop/market-trading-platform/integrated-market-platform remote -v
git -c safe.directory=C:/Users/adame/Desktop/market-trading-platform/integrated-market-platform log -8 --oneline --decorate
```

Also recompute Revision 3, approval, authority manifest, permissions, preservation, and candidate-root member hashes. Expected: all match, worktree is clean, no remote exists, and tests have zero failures/errors.

- [ ] **Step 3: Deliver the structured final report**

Report:

- repository branch, HEAD, clean state, no remote, prior and new evidence impact;
- both donor purposes, useful/unusable components, licenses, datasets, dependencies, and risks;
- exhaustive reuse matrix summary and links;
- exact Swim With the Whales architecture and no-risk-bypass rule;
- DS-340W model-research adoption and actual-future-xreg exclusion;
- GridIQ dataset/API/frontend/AI lessons and private-data exclusion;
- every canonical and collection-root file changed;
- roadmap changes and unchanged phases;
- explicit statement that Phase 0 did not become accepted;
- unresolved licenses, dataset rights, leakage, evidence ambiguity, and proposed ADRs;
- commands and exact verification results;
- next authorized action: two fresh-context read-only AI review classes and candidate-root approval under the existing procedure, not Phase 0A.

## Plan self-review result

- **Specification coverage:** Tasks 1–6 cover exact authority, seven-project inventory, both donor notes, component classification, licensing/data rights, model/dataset/API/UI/AI/whale architecture, traceability, roadmap, tests, security, evidence transition, adversarial review, and final report.
- **Placeholder scan:** Runtime-derived paths use named variables such as `$runId`; no unspecified implementation content or placeholder marker remains.
- **Type consistency:** `resolve_canonical_authority(Path) -> dict[str, object]` is the single authority interface consumed by evidence collection and tests. Logical IDs and hashes are consistent across the approved specification, approval record, manifest, evidence, and report.
- **Scope check:** The plan changes governance, documentation, and Phase 0 evidence only. It does not implement Phase 0A, market data, models, institutional ingestion, AI, strategy, risk, broker execution, or trading.
