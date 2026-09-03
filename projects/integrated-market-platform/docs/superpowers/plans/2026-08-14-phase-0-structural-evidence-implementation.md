# Phase 0 Structural and Evidence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement only Phase 0 Steps 9 through 13: an offline-only structural package, deterministic safety evidence, one coherent assertion evaluation, a governance verifier, and a candidate evidence root.

**Architecture:** Build a CPython 3.11 standard-library-only modular package inside `ROOT-2E7C91F4`. A manifest-selected local installer, closed registry, AST-based dependency analysis, deny-first runtime guard, canonical evidence writer, assertion evaluator, and verifier share one canonical JSON implementation. No prototype code, market data, provider, broker, strategy, or external service enters the subject.

**Tech Stack:** CPython 3.11.x; Python standard library only; `unittest`; canonical JSON; SHA-256; local Git with no remote.

## Authority bindings

- Canonical candidate: `foundation.canonical_specification.revision_2`, SHA-256 `56F6C424EF83BE6042E06D716F3BBE87A1E1B7FE7EBEB15B7EECD875131BC06A`.
- Controlling plan: `phase0.governance_plan`, SHA-256 `EE22C688167F5016D7ED1953BB1DAE516BC6AB343655A7D96535C6605D37E904`.
- Repository decision: `phase0.adr_repo_001`, SHA-256 `5D0F30A0BBC558ADC32F9D924D9AF870964922C6CEFFEC3FFA7F74641FC3A612`.
- Repository mutation authorization: `phase0.repository_mutation_authorization`, SHA-256 `205F2A23401496B0AC75237ED27C9532FAE81721AE5A0EEA2129F04A1E606788`.
- Offline conformance design: `phase0.adr_off_001_conformance`, SHA-256 `0A9986F52100BAF2DA2C8A44D132042C94BB0D6844933CA09A9D48EAD0B353B4`.
- Target repository: opaque `ROOT-2E7C91F4`; the absolute map is protected execution data and never enters source, logs, commits, or evidence.

## Global Constraints

- Do not start any task until the Phase 0 implementation authorization is effective by exact-hash approval and every bound hash is freshly reverified.
- Work only inside `ROOT-2E7C91F4`; do not read prototype contents except the approved value-safe preservation comparison procedure.
- Python runtime is CPython 3.11; the observed patch is 3.11.15. A different major/minor version blocks execution.
- Third-party direct and transitive dependencies are exactly zero.
- Do not run a package manager, contact a registry, configure or contact a Git remote, retrieve Git LFS, or use an unmanifested cache.
- Do not implement Phase 0A, market-data parsing, provider retrieval, strategy logic, signals, risk decisions, orders, fills, positions, P&L, paper operation, or live operation.
- Broker/provider SDKs, network clients, live adapters, credential schemas, plugin discovery, dynamic module paths, subprocesses, native extensions, and prototype imports are prohibited.
- `socket` is allowed only in `offline_guard.py` and denial tests; `sysconfig` is allowed only in the local installer.
- Governance JSON is UTF-8 without BOM, LF terminated, recursively key-sorted, duplicate-key-free, and serialized with separators `(',', ':')` for hashed canonical bytes.
- No human-visible artifact may contain credential values, account identifiers, proxy values, absolute host paths, remote URLs, secret-derived fingerprints, or provider payloads.
- `BLOCKED` is used for missing subject, authority, tool, access, or evidence. `FAIL` is used only for contradictory executable evidence or an integrity rule that defines invalidity as failure.
- The deferred normative JSON schema/fixture/test-vector suite is not created by this plan. Focused unit tests validate this implementation without claiming that deferred deliverable exists.
- Every task ends with fresh tests and a local commit containing only task-scoped paths. No push occurs.

## File map

```text
ROOT-2E7C91F4/
  .gitignore
  README.md
  phase0-dependency-lock.json
  src/market_platform_foundation/
    __init__.py
    __main__.py
    canonical.py
    errors.py
    policy.py
    registry.py
    offline_guard.py
    analysis.py
    distribution.py
    credential_audit.py
    evidence.py
    assertions.py
    verifier.py
    offline/fixture_manifest.py
    execution/simulator.py
    contracts/__init__.py
    reference_data/__init__.py
    normalization/__init__.py
    data_quality/__init__.py
    storage/__init__.py
    replay/__init__.py
    features/__init__.py
    strategies/__init__.py
    risk/__init__.py
    portfolio/__init__.py
    attribution/__init__.py
    reporting/__init__.py
  tools/phase0/
    build_distribution.py
    offline_install.py
    run_evidence_pipeline.py
  manifests/phase0/
    assertion-predicates.json
    distribution-policy.json
    import-policy.json
    prohibited-targets.json
    registry.json
  tests/phase0/
    test_canonical.py
    test_registry.py
    test_offline_guard.py
    run_test_file.py
    test_distribution.py
    test_analysis.py
    test_credential_audit.py
    test_assertions.py
    test_verifier.py
    test_pipeline.py
  evidence/phase0/<run_id>/
    ... generated immutable evidence ...
```

The package modules each own one concern. Canonical layers are empty import-safe namespaces during Phase 0. `offline.fixture_manifest` and `execution.simulator` expose structural descriptors only. `evidence.py` writes artifacts; `assertions.py` evaluates predicates from finalized evidence; `verifier.py` validates authority, hashes, aggregation, and candidate-root construction without producing new predicate evidence.

---

### Task 1: Authorization preflight, package skeleton, and canonical bytes

**Files:**
- Create: `.gitignore`
- Create: `README.md`
- Create: `src/market_platform_foundation/__init__.py`
- Create: `src/market_platform_foundation/canonical.py`
- Create: `src/market_platform_foundation/errors.py`
- Create: all canonical layer `__init__.py` files listed in the file map
- Test: `tests/phase0/test_canonical.py`

**Interfaces:**
- Consumes: effective implementation authorization and the approved document hashes in this plan.
- Produces: `canonical_bytes(value: object) -> bytes`, `sha256_bytes(data: bytes) -> str`, `load_json_strict(path: Path) -> object`, `write_canonical_json(path: Path, value: object) -> str`, and `GovernanceError` subclasses.

- [ ] **Step 1: Reverify authority and repository state before writing**

Run the approved hash verifier against every bound document, verify `git remote` returns no names, verify the branch is `main`, verify the preservation difference report permits implementation, and verify the exact implementation-authorization hash. Expected: every hash matches, no remote exists, and every activation condition is true. Otherwise stop `BLOCKED` without writing.

- [ ] **Step 2: Write the failing canonicalization tests**

```python
import json
import tempfile
import unittest
from pathlib import Path

from market_platform_foundation.canonical import (
    canonical_bytes,
    load_json_strict,
    sha256_bytes,
    write_canonical_json,
)


class CanonicalTests(unittest.TestCase):
    def test_recursive_key_order_and_utf8_lf(self):
        self.assertEqual(canonical_bytes({"z": {"b": 1, "a": 2}, "a": "é"}), b'{"a":"\xc3\xa9","z":{"a":2,"b":1}}\n')

    def test_duplicate_key_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "duplicate.json"
            path.write_text('{"a":1,"a":2}\n', encoding="utf-8", newline="\n")
            with self.assertRaises(ValueError):
                load_json_strict(path)

    def test_writer_returns_file_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "value.json"
            digest = write_canonical_json(path, {"b": 2, "a": 1})
            self.assertEqual(digest, sha256_bytes(path.read_bytes()))
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"a": 1, "b": 2})
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `python -m unittest tests.phase0.test_canonical -v`  
Expected: import failure because `market_platform_foundation.canonical` does not exist.

- [ ] **Step 4: Implement the canonical primitives and empty namespaces**

```python
# src/market_platform_foundation/canonical.py
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def _pairs_no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def canonical_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def load_json_strict(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_pairs_no_duplicates)


def write_canonical_json(path: Path, value: object) -> str:
    data = canonical_bytes(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return sha256_bytes(data)
```

`errors.py` defines `GovernanceError`, `BlockedError`, `IntegrityError`, `OfflineBoundaryViolation`, and `PolicyViolation`. Every canonical layer file contains only a module docstring stating `Phase 0 structural namespace; no runtime capability.` The `.gitignore` excludes `__pycache__/`, `*.py[cod]`, `.venv*/`, `venv*/`, `.pytest*/`, `.coverage*`, `build/`, `dist/`, `*.log`, `.env*`, `*credential*`, `*secret*`, and temporary evidence staging directories; it does not ignore committed manifests or final evidence.

- [ ] **Step 5: Run tests and scan the created tree**

Run: `python -m unittest tests.phase0.test_canonical -v`  
Expected: 3 tests pass. Then run the approved value-blind path scan; expected: no tracked private-configuration path.

- [ ] **Step 6: Commit**

```text
git add .gitignore README.md src/market_platform_foundation tests/phase0/test_canonical.py
git commit -m "feat: add phase 0 canonical package skeleton"
```

### Task 2: Closed registry and structural adapters

**Files:**
- Create: `src/market_platform_foundation/policy.py`
- Create: `src/market_platform_foundation/registry.py`
- Create: `src/market_platform_foundation/offline/__init__.py`
- Create: `src/market_platform_foundation/offline/fixture_manifest.py`
- Create: `src/market_platform_foundation/execution/__init__.py`
- Create: `src/market_platform_foundation/execution/simulator.py`
- Create: `manifests/phase0/registry.json`
- Test: `tests/phase0/test_registry.py`

**Interfaces:**
- Consumes: strict JSON and canonical hashing from Task 1.
- Produces: `resolve_registry(registry_id: str) -> type`, `registry_snapshot() -> list[dict[str, str]]`, `ManifestOnlyReader`, and immutable `SimulatorDescriptor`.

- [ ] **Step 1: Write failing allowlist and rejection tests**

```python
import os
import unittest

from market_platform_foundation.registry import resolve_registry, registry_snapshot


class RegistryTests(unittest.TestCase):
    def test_only_two_literal_entries_exist(self):
        self.assertEqual([row["registry_id"] for row in registry_snapshot()], ["offline.fixture_manifest", "simulation.noop"])

    def test_unknown_identifier_fails_closed(self):
        with self.assertRaises(KeyError):
            resolve_registry("broker.live")

    def test_environment_cannot_supply_module(self):
        os.environ["ADAPTER_MODULE"] = "prototype.provider"
        try:
            with self.assertRaises(KeyError):
                resolve_registry(os.environ["ADAPTER_MODULE"])
        finally:
            del os.environ["ADAPTER_MODULE"]
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m unittest tests.phase0.test_registry -v`  
Expected: import failure because the registry does not exist.

- [ ] **Step 3: Implement a literal registry with no discovery**

```python
# src/market_platform_foundation/registry.py
from __future__ import annotations

from .execution.simulator import SimulatorDescriptor
from .offline.fixture_manifest import ManifestOnlyReader

_REGISTRY = {
    "offline.fixture_manifest": ManifestOnlyReader,
    "simulation.noop": SimulatorDescriptor,
}


def resolve_registry(registry_id: str) -> type:
    if registry_id not in _REGISTRY:
        raise KeyError(f"registry identifier is not allowed: {registry_id}")
    return _REGISTRY[registry_id]


def registry_snapshot() -> list[dict[str, str]]:
    return [
        {"implementation": f"{value.__module__}:{value.__name__}", "registry_id": key}
        for key, value in sorted(_REGISTRY.items())
    ]
```

`ManifestOnlyReader` accepts only an already parsed dictionary whose `fixture_kind` equals `SYNTHETIC_STRUCTURE_ONLY` and returns its sorted keys. `SimulatorDescriptor` is a frozen dataclass with only `registry_id="simulation.noop"` and `routing_capability=False`; it defines no submit, cancel, replace, account, fill, or transport method. `registry.json` contains exactly the two IDs and implementation strings above.

- [ ] **Step 4: Run tests and negative identifier cases**

Run: `python -m unittest tests.phase0.test_registry -v`  
Expected: 3 tests pass; every unknown or case-variant ID raises `KeyError`.

- [ ] **Step 5: Commit**

```text
git add src/market_platform_foundation/policy.py src/market_platform_foundation/registry.py src/market_platform_foundation/offline src/market_platform_foundation/execution manifests/phase0/registry.json tests/phase0/test_registry.py
git commit -m "feat: add closed offline registry"
```

### Task 3: Deny-first guard and fixed milestone CLI

**Files:**
- Create: `src/market_platform_foundation/offline_guard.py`
- Create: `src/market_platform_foundation/__main__.py`
- Create: `tests/phase0/run_test_file.py`
- Test: `tests/phase0/test_offline_guard.py`

**Interfaces:**
- Consumes: `OfflineBoundaryViolation`, registry snapshot, and canonical writer.
- Produces: `install_guard(log: list[dict[str, str]]) -> None`, `run_denial_self_test() -> list[dict[str, str]]`, and four literal CLI subcommands.

- [ ] **Step 1: Write failing denial tests**

```python
import socket
import subprocess
import unittest

from market_platform_foundation.errors import OfflineBoundaryViolation
from market_platform_foundation.offline_guard import install_guard


class OfflineGuardTests(unittest.TestCase):
    def test_ipv4_ipv6_loopback_and_dns_are_denied(self):
        log = []
        install_guard(log)
        for action in (
            lambda: socket.socket(socket.AF_INET, socket.SOCK_STREAM),
            lambda: socket.socket(socket.AF_INET6, socket.SOCK_STREAM),
            lambda: socket.getaddrinfo("localhost", 1),
        ):
            with self.assertRaises(OfflineBoundaryViolation):
                action()

    def test_process_spawn_is_denied(self):
        with self.assertRaises(OfflineBoundaryViolation):
            subprocess.Popen(["python", "--version"])
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m unittest tests.phase0.test_offline_guard -v`  
Expected: import failure because the guard does not exist.

- [ ] **Step 3: Implement the guard before any subject import**

`install_guard` is idempotent. It saves no callable escape hatch, replaces `socket.socket`, `socket.create_connection`, `socket.getaddrinfo`, `socket.gethostbyname`, and `socket.gethostbyname_ex` with one rejecting callable, and registers an audit hook rejecting events whose exact name is `socket.__new__`, `socket.getaddrinfo`, `subprocess.Popen`, or `os.system`. Each rejection logs only `event_category` and a fixed reason code. The CLI installs the guard before importing registry, analysis, evaluator, or verifier modules. It accepts only `verify-structure`, `emit-registry`, `evaluate-phase0`, and `verify-governance`; `argparse` rejects every other subcommand and unknown argument.

- [ ] **Step 4: Run tests in isolated mode**

Run: `python -I tests/phase0/run_test_file.py tests/phase0/test_offline_guard.py` using a tiny standard-library runner that adds only the repository `src` directory after installing the guard.  
Expected: IPv4, IPv6, loopback/DNS, and process-spawn attempts are rejected before OS communication or child creation; tests pass.

- [ ] **Step 5: Commit**

```text
git add src/market_platform_foundation/offline_guard.py src/market_platform_foundation/__main__.py tests/phase0/test_offline_guard.py tests/phase0/run_test_file.py
git commit -m "feat: enforce denied-network phase 0 entry points"
```

### Task 4: Zero-dependency lock, deterministic distribution, and clean local install

**Files:**
- Create: `phase0-dependency-lock.json`
- Create: `manifests/phase0/distribution-policy.json`
- Create: `src/market_platform_foundation/distribution.py`
- Create: `tools/phase0/build_distribution.py`
- Create: `tools/phase0/offline_install.py`
- Test: `tests/phase0/test_distribution.py`

**Interfaces:**
- Consumes: canonical hashing, approved path allowlist, CPython 3.11 runtime.
- Produces: deterministic source/distribution manifests, local zip application, verified clean copy installation, installed inventory, and sanitized install log.

- [ ] **Step 1: Write failing deterministic-build and prohibited-dependency tests**

```python
import tempfile
import unittest
from pathlib import Path

from market_platform_foundation.distribution import build_distribution, validate_lock


class DistributionTests(unittest.TestCase):
    def test_lock_has_zero_third_party_dependencies(self):
        report = validate_lock(Path("phase0-dependency-lock.json"))
        self.assertEqual(report["third_party_count"], 0)
        self.assertEqual(report["prohibited_matches"], [])

    def test_two_builds_are_byte_identical(self):
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            one = build_distribution(Path("."), Path(first))
            two = build_distribution(Path("."), Path(second))
            self.assertEqual(one["archive_sha256"], two["archive_sha256"])
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m unittest tests.phase0.test_distribution -v`  
Expected: import or missing-lock failure.

- [ ] **Step 3: Write the exact dependency lock and distribution policy**

The lock records `implementation="CPython"`, `major_minor="3.11"`, `tested_patch="3.11.15"`, `third_party=[]`, the exact allowlisted standard-library modules from ADR-OFF-001, the two module exceptions, and prohibited package/module patterns. `distribution-policy.json` includes only `src/market_platform_foundation/**`, the three `tools/phase0` scripts, `tests/phase0/**`, `manifests/phase0/**`, registered `docs/superpowers/**`, `README.md`, `.gitignore`, and the lock. It excludes `.git`, evidence staging, prototypes, LFS, logs, caches, environments, data, credentials, and files at least 10 MiB.

- [ ] **Step 4: Implement deterministic build and standard-library install**

`build_distribution` resolves every selected path under the repository root, rejects symlinks/reparse escapes, hashes source bytes, and writes sorted archive members with timestamp `(1980, 1, 1, 0, 0, 0)` and mode `0o644`. `offline_install.py` installs the guard first, validates the local artifact manifest, verifies an empty destination, copies only the expanded package into the clean venv's `sysconfig.get_path("purelib")`, and writes an installed inventory. It never invokes pip or another process.

- [ ] **Step 5: Verify clean installation without a cache**

Create a fresh venv using the authorized host interpreter, verify `include-system-site-packages = false`, delete no user cache, and do not invoke pip. Run the installer from the local source manifest with proxy variables removed by name. Expected: installed third-party distribution count is zero; local hashes match; denial self-tests pass; the installed CLI emits the same registry snapshot.

- [ ] **Step 6: Commit**

```text
git add phase0-dependency-lock.json manifests/phase0/distribution-policy.json src/market_platform_foundation/distribution.py tools/phase0/build_distribution.py tools/phase0/offline_install.py tests/phase0/test_distribution.py
git commit -m "feat: add zero-dependency offline distribution"
```

### Task 5: Resolved imports, dynamic-load scan, prohibited targets, and route reachability

**Files:**
- Create: `manifests/phase0/import-policy.json`
- Create: `manifests/phase0/prohibited-targets.json`
- Create: `src/market_platform_foundation/analysis.py`
- Test: `tests/phase0/test_analysis.py`

**Interfaces:**
- Consumes: repository source manifest, fixed entry points, protected-layer list, registry snapshot.
- Produces: resolved import graph, unresolved-import list, dynamic-load findings, entry-point inventory, prohibited-target catalogue, reachability graph, and empty-path results.

- [ ] **Step 1: Write failing adversarial graph tests**

```python
import tempfile
import unittest
from pathlib import Path

from market_platform_foundation.analysis import analyze_tree


class AnalysisTests(unittest.TestCase):
    def test_direct_broker_import_is_found(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "strategies").mkdir()
            (root / "strategies" / "bad.py").write_text("import ib_insync\n", encoding="utf-8")
            report = analyze_tree(root)
            self.assertEqual(report["prohibited_edges"][0]["target"], "ib_insync")

    def test_nonconstant_dynamic_import_is_blocking(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "bad.py").write_text("import importlib\nimportlib.import_module(name)\n", encoding="utf-8")
            report = analyze_tree(root)
            self.assertEqual(report["dynamic_load_findings"][0]["reason"], "NONCONSTANT_DYNAMIC_IMPORT")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m unittest tests.phase0.test_analysis -v`  
Expected: import failure because `analysis.py` does not exist.

- [ ] **Step 3: Implement AST resolution and combined reachability**

Parse every `.py` selected by the distribution manifest. Resolve absolute and relative imports to repository module names; retain external imports for lock comparison. Detect `__import__`, `importlib`, metadata entry points, `eval`, `exec`, pickle/marshal loads, ctypes, `subprocess`, `os.system`, shell helpers, and configuration-derived module strings. Reject syntax errors and unresolved internal imports. Build a graph whose nodes include modules, fixed CLI commands, registry IDs, implementation classes, sensitive call names, and prohibited target categories. Breadth-first search starts at every CLI and reports the complete path for any target; no flag-guarded target is exempt.

- [ ] **Step 4: Run the analyzer against source and adversarial fixtures**

Run: `python -m unittest tests.phase0.test_analysis -v` and then the `verify-structure` CLI.  
Expected: adversarial fixtures are detected; the governed source has zero prohibited edges, zero unresolved imports, zero nonconstant dynamic loads, and empty route sets for live submission, live market data, broker account access, and all other broker operations.

- [ ] **Step 5: Commit**

```text
git add manifests/phase0/import-policy.json manifests/phase0/prohibited-targets.json src/market_platform_foundation/analysis.py tests/phase0/test_analysis.py
git commit -m "feat: add phase 0 dependency and route analysis"
```

### Task 6: Value-blind credential and history audit

**Files:**
- Create: `src/market_platform_foundation/credential_audit.py`
- Test: `tests/phase0/test_credential_audit.py`

**Interfaces:**
- Consumes: current-tree file list, Git tracked/history object lists supplied as sanitized byte streams, ignore rules, and redaction rules.
- Produces: opaque current/history path manifests, private-container result, redacted finding counts, public-example review, and ignore-policy report.

- [ ] **Step 1: Write failing path-metadata and redaction tests**

```python
import unittest

from market_platform_foundation.credential_audit import classify_path, redact_match


class CredentialAuditTests(unittest.TestCase):
    def test_private_env_is_rejected_without_opening(self):
        result = classify_path("config/.env", tracked=True)
        self.assertEqual(result["classification"], "PROHIBITED_TRACKED_MATERIAL")
        self.assertFalse(result["content_read"])

    def test_match_output_contains_no_value_or_context(self):
        finding = redact_match("TOKEN_RULE", "PATH-0001", "abc-secret-value")
        self.assertEqual(set(finding), {"opaque_path_id", "revision_id", "rule_id", "sanitized_location"})
        self.assertNotIn("abc-secret-value", repr(finding))
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m unittest tests.phase0.test_credential_audit -v`  
Expected: import failure because the auditor does not exist.

- [ ] **Step 3: Implement metadata-first classification and value-redacted scanning**

Never open a private `.env`, key container, wallet, credential store, or path whose policy classification is prohibited from metadata. Generate random opaque `PATH-NNNN` IDs with the reversible map held only in process memory. For other governed current/history bytes, scanner rules may inspect content but output only opaque path ID, Git revision identifier, rule ID, and line number; matched text, hashes derived from matched values, and surrounding context are forbidden. Public examples pass only when all assigned values are members of the literal placeholder set `{CHANGEME, EXAMPLE, PLACEHOLDER, NOT_A_SECRET}`. History traversal uses local Git objects only and never a remote.

- [ ] **Step 4: Run tests and the current/history audit**

Run: `python -m unittest tests.phase0.test_credential_audit -v`. Then audit the accepted current tree and every locally reachable commit. Expected for `SEC-001` PASS: zero prohibited credential-container paths, zero unresolved redacted findings, examples use placeholders only, and private local configuration patterns are ignored. Otherwise emit truthful `FAIL` or `BLOCKED` and stop candidate-root construction until resolved under separate authority.

- [ ] **Step 5: Commit**

```text
git add src/market_platform_foundation/credential_audit.py tests/phase0/test_credential_audit.py
git commit -m "feat: add value-blind credential audit"
```

### Task 7: Evidence writer and finalized Step 10–11 artifacts

**Files:**
- Create: `src/market_platform_foundation/evidence.py`
- Create: `tools/phase0/run_evidence_pipeline.py`
- Test: `tests/phase0/test_pipeline.py`

**Interfaces:**
- Consumes: finalized outputs from Tasks 2–6, repository registration, preservation comparison, authority records, and implementation authorization.
- Produces: immutable evidence records with logical ID, scope, inputs, exclusions, procedure/tool versions, source manifest hash, sanitization, and content hash.

- [ ] **Step 1: Write failing artifact-finalization tests**

```python
import tempfile
import unittest
from pathlib import Path

from market_platform_foundation.evidence import finalize_artifact


class EvidenceTests(unittest.TestCase):
    def test_finalized_artifact_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "artifact.json"
            finalize_artifact(path, "phase0.registry_snapshot", {"rows": []})
            with self.assertRaises(FileExistsError):
                finalize_artifact(path, "phase0.registry_snapshot", {"rows": []})
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m unittest tests.phase0.test_pipeline.EvidenceTests -v`  
Expected: import failure because `evidence.py` does not exist.

- [ ] **Step 3: Implement staged, immutable evidence publication**

Write each artifact once to a run-specific staging directory, validate required metadata and sanitization, canonicalize, hash, rename atomically into the final run directory, then set an in-memory finalized guard. A pre-evaluation evidence index contains only artifacts that already exist and match. The pipeline emits the distribution manifest, registry snapshot, import boundary report, entry-point route report, credential audit, dependency lock report, local artifact manifest, denied-network protocol registration, denied-network install log, installed inventory, and source subject manifest.

- [ ] **Step 4: Produce and verify Step 10–11 evidence**

Run the pipeline once from a clean worktree and fresh venv under the guard. Expected: every artifact is finalized before assertion evaluation; no absolute path, secret/account value, proxy value, remote URL, provider payload, or prototype content appears; every selected evidence hash resolves.

- [ ] **Step 5: Commit source and tests, not generated run evidence yet**

```text
git add src/market_platform_foundation/evidence.py tools/phase0/run_evidence_pipeline.py tests/phase0/test_pipeline.py
git commit -m "feat: add immutable phase 0 evidence pipeline"
```

### Task 8: Active assertion registry and one coherent evaluation

**Files:**
- Create: `manifests/phase0/assertion-predicates.json`
- Create: `src/market_platform_foundation/assertions.py`
- Test: `tests/phase0/test_assertions.py`

**Interfaces:**
- Consumes: exact Section 9 predicates, finalized preselected evidence, subject manifest, approved authorities.
- Produces: active registry version `1.0.0`, `mandatory_set_hash`, pre-evaluation run manifest and `run_id`, and exactly one result for each active key.

- [ ] **Step 1: Write failing set-equality and one-run tests**

```python
import unittest

from market_platform_foundation.assertions import MANDATORY_IDS, validate_result_membership


class AssertionTests(unittest.TestCase):
    def test_mandatory_set_is_exact(self):
        self.assertEqual(MANDATORY_IDS, ("GOV-001", "GOV-002", "GOV-003", "GOV-004", "SAFE-001", "SAFE-002", "SAFE-003-STATIC", "SAFE-P0-001", "SEC-001"))

    def test_mixed_run_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_result_membership("RUN-A", [{"assertion_id": key, "run_id": "RUN-B"} for key in MANDATORY_IDS])
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m unittest tests.phase0.test_assertions -v`  
Expected: import failure because the evaluator does not exist.

- [ ] **Step 3: Register exact predicates and hashes**

`assertion-predicates.json` contains the nine exact predicate strings from Section 9, each with version `1.0.0`. Compute each predicate hash from canonical JSON containing only `assertion_id`, `assertion_version`, and `predicate`. Sort active IDs ordinally and hash that canonical array for `mandatory_set_hash`. The registry has exactly one ACTIVE key per ID and no retired key in version 1.0.0.

- [ ] **Step 4: Implement pre-evaluation binding and predicate evaluation**

Before evaluating, write a run manifest binding approved plan/spec/ADR/authorizations, registry hash, mandatory-set hash, subject-manifest hash, canonical configuration hash, tool versions, and the complete selected evidence set. Compute `run_id` with only `run_id` omitted. Evaluate every key even when one fails or blocks. Results include the exact fields required by Section 7, and `assertion_result_id` is computed with only that field omitted. No evaluator may add evidence after the run manifest is finalized.

- [ ] **Step 5: Run tests and one evaluation**

Run: `python -m unittest tests.phase0.test_assertions -v`, then `python -I -m market_platform_foundation evaluate-phase0 --run-manifest <sanitized-logical-input> --output-dir <run-dir>`. Expected: exactly nine results, all same `run_id`, registry, and subject hash; statuses reflect evidence truth and are not coerced to PASS.

- [ ] **Step 6: Commit**

```text
git add manifests/phase0/assertion-predicates.json src/market_platform_foundation/assertions.py tests/phase0/test_assertions.py
git commit -m "feat: evaluate the exact phase 0 assertion set"
```

### Task 9: Governance verifier, aggregate, and candidate root

**Files:**
- Create: `src/market_platform_foundation/verifier.py`
- Test: `tests/phase0/test_verifier.py`

**Interfaces:**
- Consumes: approved authorities, active registry, one run manifest, nine results, selected evidence index, and preapproval artifact inventory.
- Produces: governance-verifier output, assertion aggregate, ordered preapproval tuple array, and `candidate_evidence_root`.

- [ ] **Step 1: Write failing integrity and aggregate tests**

```python
import unittest

from market_platform_foundation.verifier import aggregate_status, candidate_root


class VerifierTests(unittest.TestCase):
    def test_fail_precedes_blocked(self):
        self.assertEqual(aggregate_status(["PASS", "BLOCKED", "FAIL"]), "FAIL")

    def test_blocked_precedes_pass(self):
        self.assertEqual(aggregate_status(["PASS", "BLOCKED"]), "BLOCKED")

    def test_candidate_root_is_order_independent(self):
        rows = [
            {"logical_id": "b", "member_sha256": "B", "byte_length": 2, "media_type": "application/json"},
            {"logical_id": "a", "member_sha256": "A", "byte_length": 1, "media_type": "application/json"},
        ]
        self.assertEqual(candidate_root(rows), candidate_root(list(reversed(rows))))
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m unittest tests.phase0.test_verifier -v`  
Expected: import failure because `verifier.py` does not exist.

- [ ] **Step 3: Implement validation in fail-closed order**

Validate duplicate-free canonical JSON, exact authority hashes/effectivity, one canonical specification, supersession graph, exact mandatory set and predicate hashes, role resolution and eligibility, repository mutation authorization and preservation comparison, implementation authorization, evidence hash resolution, selected-run membership, result IDs, role arrays, same-version supersession, and aggregate rules. Report missing prerequisites as BLOCKED; contradictory or invalid bytes follow the controlling plan's FAIL rules. Do not infer approval from artifact status text.

- [ ] **Step 4: Implement aggregate and candidate-root construction**

Compute `FAIL` if any mandatory result is FAIL, else `BLOCKED` if any is BLOCKED, else `PASS`. A PASS aggregate is not Phase 0 PASS. Build the lexicographically ordered `(logical_id, member_sha256, byte_length, media_type)` tuple array for preapproval artifacts. Exclude `phase0.candidate_evidence_root`, `phase0.approval_records`, `phase0.ai_review_runs`, `phase0.ai_review_coverage`, `phase0.acceptance_index`, and `phase0.final_acceptance_result`. Hash canonical tuple-array bytes; store the value and array in the candidate-root manifest without making the manifest a member of itself.

- [ ] **Step 5: Run unit and tamper tests**

Run: `python -m unittest tests.phase0.test_verifier -v`. Copy one test artifact to a temporary directory, change one byte, and verify hash resolution fails; remove one result and verify BLOCKED; mix a run ID and verify invalid membership; add a postroot logical ID and verify exclusion or rejection as specified. Expected: all focused tests pass and no governed artifact is changed.

- [ ] **Step 6: Commit**

```text
git add src/market_platform_foundation/verifier.py tests/phase0/test_verifier.py
git commit -m "feat: verify governance and build candidate root"
```

### Task 10: Full Step 9–13 execution and immutable candidate publication

**Files:**
- Modify: generated files only under `evidence/phase0/<run_id>/`
- Create: `evidence/phase0/<run_id>/candidate-evidence-root.json`
- Test: `tests/phase0/test_pipeline.py`

**Interfaces:**
- Consumes: clean committed source, exact authorities, finalized Step 10–11 evidence, active registry, and implementation authorization.
- Produces: one complete preapproval evidence bundle ready for principal approval and the two qualifying independent AI review classes.

- [ ] **Step 1: Reverify the clean subject and preservation state**

Run the full authority-hash check, `git status --porcelain`, `git remote`, source-manifest build, and prototype preservation comparison. Expected: clean governed worktree, no remote, no unauthorized prototype drift, and only separately reported volatile log drift. Any mismatch stops before evidence generation.

- [ ] **Step 2: Run the complete focused test suite**

Run: `python -m unittest discover -s tests/phase0 -v`  
Expected: zero failures and zero errors. Record the command, interpreter, test count, and sanitized output hash.

- [ ] **Step 3: Build twice and prove deterministic distribution bytes**

Build in two fresh temporary directories under the guard. Expected: identical distribution manifest and archive SHA-256 values. Do not retain temporary directories as evidence members; retain the comparison record and selected artifact only.

- [ ] **Step 4: Perform clean denied-network installation and CLI self-check**

Create a new venv with no system site packages, run the guarded local installer, verify installed inventory, run all four fixed CLI help/validation paths, and execute denial self-tests for DNS, IPv4, IPv6, loopback, proxy-name handling, subprocess, and package-manager targets. Expected: installation succeeds with no third-party package and no network attempt; every controlled prohibited attempt is denied with the specified reason.

- [ ] **Step 5: Finalize Step 10–11 evidence and write the pre-evaluation manifest**

Finalize the preservation, distribution, registry, import, dynamic-load, route, dependency-lock, local-artifact, denied-network-install, denied-network-protocol, credential-audit, canonical-inventory, authorization, and source-manifest evidence. Verify every hash, then write the run manifest. No new predicate evidence may be introduced afterward.

- [ ] **Step 6: Evaluate all nine active assertions in one run**

Run the evaluator once. Expected: exactly one result for each mandatory key and no extra key. Preserve truthful PASS, FAIL, or BLOCKED results. If any result is FAIL or BLOCKED, still run the verifier and aggregate, but do not describe Phase 0 as passed.

- [ ] **Step 7: Run the verifier and build the candidate root**

Run: `python -I -m market_platform_foundation verify-governance --evaluation-dir <run-dir> --output-dir <run-dir>`. Expected: verifier output, deterministic aggregate, ordered preapproval tuple array, and candidate-root manifest. Recompute the root independently with a separate invocation and require equality.

- [ ] **Step 8: Commit the immutable preapproval evidence bundle**

Stage only finalized evidence selected by the preapproval tuple array plus its candidate-root manifest. Commit with:

```text
git add evidence/phase0/<run_id>
git commit -m "chore: publish phase 0 candidate evidence root"
```

Do not create approval records, AI review runs, coverage, acceptance index, or final acceptance result in this task. Those are postroot Steps 14–15.

- [ ] **Step 9: Handoff at the final approval/review gate**

Report the candidate root, aggregate status, run ID, registry hash, specification hash, plan hash, implementation-authorization hash, commit ID, evidence member count, and unresolved reason codes. Request attributable principal approvals and launch the two fresh-context read-only AI review classes only under the already approved review procedure. Do not begin Phase 0A.

## Plan self-review result

- Specification coverage: the plan covers the exact Phase 0 Step 9 skeleton; Step 10 preservation/distribution/registry/import/dynamic-load/reachability/credential artifacts; Step 11 lock/local-artifact/denied-network installation; Step 12 registry/run manifest/nine one-run results; and Step 13 verifier/aggregate/candidate root.
- Scope: no prototype code, market data, strategy, provider, broker, remote, registry, LFS, paper, live, Phase 0A, or later-phase implementation is included.
- Type consistency: canonical, registry, guard, distribution, analysis, audit, evidence, assertion, and verifier interfaces are named once and consumed by later tasks using the same names.
- Deferred boundary: the normative JSON schema/fixture/test-vector suite remains uncreated; focused unit tests do not claim to satisfy that deferred deliverable.
- Placeholders: angle-bracket values in execution commands denote runtime-derived sanitized IDs or directories, not unspecified design choices; each is produced by an earlier named step.
