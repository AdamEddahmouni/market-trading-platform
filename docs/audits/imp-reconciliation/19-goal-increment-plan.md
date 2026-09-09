# 19 — Executable /goal Increment Plan (WS07)

Status: **COMPLETE (WS07, 2026-09-07)**. Converts the master backlog (12) +
recovery roadmap (13) into large coherent implementation increments (5–20
materially related changes each, controller §46/§47). Each increment closes a
meaningful architectural/product slice and unlocks the next.

## 1. Increment list (ordered)

| Goal | Title | Root causes addressed | Waves | Prerequisites | Unlocks |
|---|---|---|---|---|---|
| G0 (NEXT) | **Post-reconciliation baseline: governance supersession + validate-changed correctness + repo truth + dev-system corrections** | RC-012/013/014/020 | Wave 0 (core slice) | none | trustworthy validation + clean commit base for G1 |
| G1 | **Canonical Multi-Asset Domain Foundation** | RC-004 (+RC-001 identity part) | Wave 1 (identity slice) | G0 | G2 portfolio; all domain surfaces |
| G2 | **Canonical Multi-Asset Portfolio + ledger merge** | RC-001 | Wave 1 (portfolio core) | G1 | G3 risk; Wave 5 domains |
| G3 | **Trading/Risk correctness** | RC-005/006/007/008 | Wave 2 | G2 (BP multi-asset; instrument-kind) | E2E meaningful; provider execution |
| G4 | **IBKR adapter + incremental depth engine** | RC-002/003 | Wave 3 | G3 (not strict; depth buildable earlier) | live CVD; Wave 4 |
| G5 | **Provider Capability Registry + live-wire verification** | RC-009 | Wave 4 | G4 (IBKR); registry first | verified provider paths |
| G6 | **Multi-asset product domains (Bonds/Crypto/Gold/Silver/Commodities/Industry/Government)** | RC-015 | Wave 5 | G2 + G5 | authorized scope visible |
| G7 | **Intelligence completion (whale cockpit, market-context lane, news/research)** | RC-015/018 | Wave 6 | G5 | full intelligence surface |
| G8 | **Frontend/API/product convergence (query keys, taxonomy, contracts, selector, IA)** | RC-010/011 | Wave 7 | G6 (surfaces) + G1 (selector) | one coherent product |
| G9 | **Developer system/performance/cleanup + E2E** | RC-016/017/018/019 | Wave 8 | G3 (E2E) + G0 (perf) | fast honest engineering system |
| G10 | **Production hardening + final acceptance** | RC-009/016 | Wave 9 | all | defensible production readiness |

## 2. G0 — EXACT NEXT GOAL (copy/paste)

```text
/goal Establish the clean post-reconciliation implementation baseline by:
(1) superseding all stale donor-governance documentation (12 enumerated docs:
donor-code-permissions.json, ADR-GRIDIQ-001, gridiq-port-phase-gate.json,
ADR-DONOR-001, DONOR_REUSE_MATRIX, GRID_IQ_NOTES, DS340W_NOTES, revision-3
donor plans, PROVIDER_DUPLICATION_AUDIT, fixture inventory, WORK_LOG donor-era
entries) with in-place SUPERSEDED/HISTORICAL headers + Heller-correction
context — never deleting history, never touching code, zero test changes;
(2) fixing `validate changed` correctness in the local monorepo embedding:
normalize the `projects/integrated-market-platform/` path prefix before suite
matching, add fixture/config/test-fixture ownership so fixture edits select
their consuming suites (or a defined core checkpoint), rename the misleading
`full_suite_required` flag to `core_checkpoint_required` with output that
prints exactly which suites ran, and add shared-module dependency mapping for
the seven identified shared modules (numeric, clock, errors, assertions,
authority, evidence, market_sessions) — with `--explain` regression tests
proving selection before/after;
(3) refreshing repository truth: short-squeeze snapshot refresh via guarded
import (manifest `78b7467` → child `fix/frozen-followups` @ `9de7b2f`,
reconciled against hardening-plan `41f52bb`) with `workspace-manifest.json`
updated and a manifest-vs-child parity check;
(4) updating MASTER_ROADMAP/PROGRAM_STATUS to list the authorized mandate
(Bonds, Crypto, Gold, Silver, Commodities, Whale, Industry, Government) and
reference the master backlog + recovery roadmap;
(5) applying developer-system corrections: AGENTS.md canonical edit-tree
statement (tracked snapshot `projects/integrated-market-platform/` is the
edit target; child repo mirrors it), `imp.py env` non-zero exit on hard
prereq failure, `donor_patterns/` namespace annotation + `tests/gridiq`
conformance-harness annotation (no renames, zero behavior change);
(6) removing empty `pytest-equity-*` artifact dirs and replacing stale
child-repo CI workflow copies with a pointer to parent-root canonical CI.

Safety constraints: no code behavior changes in product modules; no deletion
of any governance history; donor trees remain read-only; mode/account/paper
safety invariants untouched; live gates untouched.
Files: `tools/validate.py`, `tools/validation_manifest.json`, `tools/imp.py`,
`AGENTS.md`, `docs/platform/MASTER_ROADMAP.md`, `docs/platform/PROGRAM_STATUS.md`,
`workspace-manifest.json`, `projects/short-squeeze-project/` (import),
`docs/superpowers/{governance,decisions,plans}/*`, `docs/research/donors/*`,
`docs/engineering/{PROVIDER_DUPLICATION_AUDIT,WORK_LOG}.md`,
`src/market_platform_foundation/donor_patterns/__init__.py`,
`tests/gridiq/test_required_future_tests.py` (head only), parent root
`pytest-equity-*` dirs, child `.github/workflows/*.yml`.
Tests: `validate changed --explain` regression tests (prefixed src → owning
suite; fixture edit → owning suites; shared-module edit → mapped dependents or
explicit core checkpoint listing actual suites), manifest self-validation,
docs-link validator, monorepo-guard CI.
Validation commands: `tools/imp.py validate fast`; controlled
`python tools/validate.py changed --paths-file <case> --explain`; full
`tools/imp.py validate full` at closure (expect 3580/48/1-excluded/0 baseline
to remain clean apart from the pre-existing dirty cross_lane golden);
`python tools/check_docs_links.py`; parent `monorepo_guard validate`.
Acceptance criteria: (a) zero governance doc treats GridIQ/DS-340W as
current-authorized; (b) `validate changed` selects correctly for
prefixed/fixture/shared-module changes with honest output; (c) SS snapshot ==
child HEAD with manifest updated; (d) roadmap lists every mandated domain; (e)
AGENTS.md states the canonical edit target; `imp.py env` exits non-zero on
wrong Python; (f) no empty pytest dirs; stale CI copies pointed at parent; (g)
FULL validation clean (baseline intact); (h) docs links 162/162.
```

## 3. Why G0 first (evidence, not preference)

- Controller §81 direction: a truth + developer-control-plane correction is
  the smallest high-leverage coherent slice that unlocks the roadmap.
- Dependency evidence: every later architecture wave (G1+) is verified with
  `validate changed`; while RC-012 holds, local monorepo changes are silently
  under-validated (FC-18, proven) — architecture migration must not begin on
  an untrustworthy control plane.
- Provenance evidence: donor-governance supersession (RC-013) is required for
  professor-facing traceability (controller §61/§75) and removes stale
  ambiguity before any new work is committed.
- Repo-truth evidence: SS snapshot + roadmap + edit-tree ambiguity (RC-014)
  must be resolved before fresh developers/agents start editing the correct
  tree.
- Risk: LOW (docs + tooling; no product behavior change; dual verified by
  baseline FULL). High confidence of success; creates a clean commit base.

## 4. Parallel workstreams after G0 (controller §49)

| Stream | Work | Conflicts? | Start condition |
|---|---|---|---|
| STREAM A — Domain model (G1) | XA-01 vocabulary consolidation + CRYPTO/Bond/Commodity identity | no file overlap with G0 (identity vs tools/docs) | G0 complete |
| STREAM B — Docs/governance remainder (Wave 0 rest) | ADR home (BL-0010), handoff consolidation (BL-0009), evidence-homes doc (BL-0012), roadmap polish | docs-only | G0 complete (avoid editing same docs concurrently) |
| STREAM C — Validation/dev tooling remainder | validation performance prep (BL-0801 planning), E2E harness skeleton (BL-0802) | touches manifest/tests only | G0 complete (needs BL-0002..0004 first) |
| STREAM D — Product UX planning | multi-asset selector + IA design docs (BL-0704/0705 design-only) | docs/design only | G0 complete; implementation after G1 |

Rule: no stream edits the same architectural core concurrently (controller
§42/§45); STREAM A owns identity files exclusively until G1 closes.

## 5. G1 — canonical multi-asset identity foundation (EXECUTED 2026-09-07)

**Status: EXECUTED (working tree, uncommitted) — closure evidence in 15 (G1
section).** Canonical Multi-Asset Domain Foundation: one asset-class
vocabulary (paper ASSET_CLASSES → XA-01; compat shim), XA-01 CRYPTO class +
pair/venue identity, Bond descriptor typing, Gold/Silver/commodity contract
identity, explicit tradability + continuous-futures non-execution guard,
runtime instrument ref carrying asset-class + contract fields. Files:
`xa01/*`, `paper/contracts.py`, `xa04/codec.py`, `tests/xa01/*`. Acceptance:
equity behavior preserved; every authorized class resolvable canonically;
BL-0101..0104 CLOSED_BY_G1; BL-0105 (G2 portfolio) NOT started. (BL-0101..0104,
BL-0108 USD doc deferred to G2 portfolio work per WS07 target architecture.)

## 6. Increment schema compliance

Every increment above maps to the full schema (goal ID, title, why now, root
causes, scope, out of scope, prerequisites, likely files, implementation
sequence, migration concerns, safety invariants, tests, validation commands,
acceptance criteria, documentation updates, completion evidence, next
dependency unlocked) in 12/13/19; G0 carries the complete schema inline
(§2), and each subsequent goal inherits its items from 12.