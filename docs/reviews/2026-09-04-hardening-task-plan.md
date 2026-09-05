# Workspace Hardening Task Plan — 2026-09-04

| Field | Value |
|---|---|
| Created | 2026-09-04 |
| Source | [Hardening review](2026-09-04-hardening-review.md) |
| Purpose | Tracked, checkable backlog produced by the workspace hardening review. Items are grouped P0 → P2. Each item names evidence, the fix, and an acceptance check. |
| Status | In progress — 1/17 closed (P0-3, 2026-09-04) |

**How to use:** tick `[ ]` → `[x]` as items close. Substantive work should also follow the owning repo's conventions (platform work log entry in `integrated-market-platform/docs/engineering/WORK_LOG.md`; short-squeeze work in its own repo; snapshot refreshes through the guarded monorepo import).

---

## P0 — Before any trading / promotion / forward campaign

These items make the machinery behind the (correctly) closed live gates trustworthy. None of them relaxes a gate.

### P0-1 — Forward-validation readiness checklist (gates G1/G3/G4/G5)

- **Problem:** P6 Shadow Run 1 and EVIDENCE-01C are deferred; canary never executed; real-wire adapters unexercised. Reactivation today would be ad hoc.
- **Evidence:** `docs/platform/PROGRAM_STATUS.md`; `docs/engineering/P6_SHADOW_RUN_1_PROTOCOL.md`; `docs/engineering/EVIDENCE_01C*`; BUILD25/29 limitation artifacts; TD-004 (`docs/engineering/TECH_DEBT.md`).
- **Fix:** one checklist document (owner: platform docs) listing the exact prerequisites to reopen each of P6 Shadow Run 1, EVIDENCE-01C, live canary, Tradier sandbox wire, and Moomoo OpenD shakedown — connectivity, env vars, credentials, fixture-state, rollback, and acceptance artifacts.
- **Acceptance:** a reviewer can determine in one page exactly which env/credential/connectivity prerequisites block each campaign today, and what each campaign must produce to count.

### P0-2 — Promotion dry-run harness (champion/challenger machinery proof)

- **Problem:** promotion governance exists but has never been exercised end-to-end; the first real use would be the first test of the machinery.
- **Evidence:** `docs/engineering/CHAMPION_CHALLENGER_PROMOTION_V1.md`; decision-research gate report (no `SUPPORTED` strategy).
- **Fix:** a fixture-driven dry-run that replays recorded paper outcomes through the promotion policy (`strategy/evaluation.py`, promotion engine) and emits an immutable decision record (`PROMOTED` / `NOT_PROMOTED`), proving the ladder without claiming an edge.
- **Acceptance:** test exists in `tests/`; output record references exact preregistration + evidence; docs state the dry run grants no execution authority.

### P0-3 — Single source of truth for lane/module identity

- **Problem:** lane identity is duplicated (backend dead `KNOWN_LANE_MODULES`; UI `LANE_MODULE_IDS`; UI `WORKSPACE_LANE_REGISTRY`; hand-written `EVIDENCE_LANE_TO_MODULE_ID`) with no cross-check test — next lane addition can silently drift.
- **Evidence:** `src/market_platform_foundation/paper/decision_source.py:19` (defined, never imported); `ui/src/components/paper-now/paperOrderDraft.ts:408`; `ui/src/components/workspace-module-shared/laneRegistry.ts`; `ui/src/components/paper-workspace/paperDecisionSemantics.ts`; `docs/architecture/DATA_CONTRACTS.md:39`.
- **Fix:** one canonical lane registry consumed by backend + UI (single JSON or Python module + generated TS), with an equality/closure test; `sops/ADD_WORKSPACE_LANE.md` updated so adding a lane edits exactly one source file.
- **Acceptance:** a test asserts backend set == UI list == evidence map; removing the dead backend frozenset or unifying registries lands with zero behavior change; lane addition is a one-file change.
- **Closed 2026-09-04** — resolved as UI-canonical registry + structural backend (no backend enumeration), rather than a shared JSON + generated TS: `WORKSPACE_LANE_REGISTRY` in `ui/src/components/workspace-module-shared/laneRegistry.ts` is now the single identity source, deriving `WORKSPACE_LANE_MODULE_IDS` / `WORKSPACE_LANE_LABELS`; `paperOrderDraft.ts` (`LANE_MODULE_IDS`, `LaneModuleId`, `isKnownLaneModuleId`, `laneModuleLabel`) and `paperDecisionSemantics.ts` (evidence map typing, `MODULES_WITHOUT_EVIDENCE_LANE` complement) read from it. Dead backend `KNOWN_LANE_MODULES` removed — `decision_source.py` now states backend lane provenance is validated structurally and never enumerated, so there is no backend list to drift. Equality/closure tests in `laneRegistry.test.ts` (7 tests) fail if any derived list or the evidence map disagrees with the registry. Verified: `npm run typecheck` clean; `npm test` 436 passed / 85 files; backend `py_compile` clean and zero references to the removed constant (full manifest validation runs in CI). Platform work-log entry added 2026-09-04.

### P0-4 — Attribution parity as an enforced invariant

- **Problem:** strategy attribution is a P&L sidecar whose parity with the authoritative ledger is expected but not a hard, fail-closed gate on materialization.
- **Evidence:** `src/market_platform_foundation/portfolio/attribution.py`, `attribution_materializer.py`; `PAPER_DECISION_LIFECYCLE.md`.
- **Fix:** materializer fails closed on any mismatch with authoritative fill-driven accounting; mismatch is recorded as an immutable event (mirroring P4-REC semantics), never silently absorbed.
- **Acceptance:** unit test forces a mismatch and asserts fail-closed + event recorded; no legitimate state can produce a silent divergence.

---

## P1 — Hardening while the live gates stay closed

### P1-1 — Explicit strategy eligibility gate before OrderReadyV1 execution intent

- **Problem:** no single checkable predicate "this strategy may drive OrderReadyV1 with execution intent" is enforced at runtime.
- **Evidence:** `src/market_platform_foundation/strategy/runtime.py` (order-ready construction path); learning boundary tests (`tests/intelligence/test_strategy_learning.py`).
- **Fix:** small explicit eligibility predicate (preregistered + promotion state + forward-evidence class) enforced on the order-ready path and by test.
- **Acceptance:** per-order intent is auditable to the strategy's eligibility record; unknown/unpromoted strategies cannot reach execution intent.

### P1-2 — Canonical opportunity path enforcement (retire path multiplicity)

- **Problem:** OpportunityEngine vs. new scanner + economic sidecar + bridge constructions coexist; only docs currently say which is canonical.
- **Evidence:** `src/market_platform_foundation/intelligence/opportunity/` (`engine.py`, `bridge.py`, `p4_adapter.py`, `economic_assessment.py`); 2026-09-01→04 `WORK_LOG.md` entries.
- **Fix:** designate one canonical construction path in `PAPER_DECISION_LIFECYCLE.md` + code docstrings; deprecate the older construction; add negative tests for cross-path identity collisions (same decision via two paths must conflict, not duplicate).
- **Acceptance:** docs and code name one canonical builder; a test proves two paths cannot produce duplicate authoritative records.

### P1-3 — RT-01 spans for broker-paper submission/poll/reconcile seams

- **Problem:** paper pipeline tracing landed 2026-09-04, but broker/reconciliation technical spans and full opportunity→risk→order_ready tracing remain follow-ons.
- **Evidence:** `WORK_LOG.md` 2026-09-04 RT-01 paper tracing entry; `docs/platform/PROGRAM_STATUS.md` RT-01 limitation line.
- **Fix:** extend `rt01/instrumentation/` to broker-paper submission, polling, cancellation, and reconciliation seams (fixture-driven), consistent with existing trace semantics; no new tracing before measured need beyond these seams.
- **Acceptance:** trace IDs flow across the broker-paper seams in tests; `PROGRAM_STATUS.md` limitation updated when closed.

### P1-4 — Discovery-lane → workspace-module → research-family mapping

- **Problem:** three "lane" vocabularies coexist (screener `MOMENTUM/SQUEEZE/CATALYST/SWING`, workspace modules, research families) with partial hand maps.
- **Evidence:** `docs/research/PLATFORM_COOPERATIVE_MASTER_ROADMAP.md`; `artifacts/live-screener/continuation-state.md`; `src/market_platform_foundation/discovery/mixed.py`; `ui/.../paperDecisionSemantics.ts`.
- **Fix:** glossary entry + one tested mapping table; keep the concepts distinct (a discovery lane is not a workspace module is not a research family).
- **Acceptance:** a single documented + tested mapping covers all three vocabularies; no hand-written per-component map remains unverified.

### P1-5 — Provider admission guard tests

- **Problem:** live opt-in provider captures are "not admitted research datasets"; doctrine forbids model retraining on them, but no guard test pins the boundary.
- **Evidence:** root README ADR table; `PROVIDER_READINESS.md`; ADR-LIVE-001 / ADR-SHORT-001 fixtures.
- **Fix:** guard/negative tests asserting unadmitted live captures cannot feed model training or promotion paths.
- **Acceptance:** a test proves an unadmitted capture is rejected by training/promotion entry points.

### P1-6 — CI canonicalization (parent snapshot workflows authoritative)

- **Problem:** identical workflow names exist in the archived nested repo and the parent (which validates `projects/integrated-market-platform`); ambiguity about the canonical gate.
- **Evidence:** `integrated-market-platform/.github/workflows/imp-validate.yml` vs `.github/workflows/imp-validate.yml` (parent); parent `imp-python.yml` working-directory `projects/integrated-market-platform`.
- **Fix:** declare parent workflows canonical in docs; mark nested workflow copies stale or remove them in the nested repo (child repo is archived read-only — document-only decision may suffice).
- **Acceptance:** a reader can tell which CI gate is authoritative; no duplicated workflow is presented as current without a stale marker.

### P1-7 — Fix git dubious-ownership failure in `equity-data-v1-worktree`

- **Problem:** git commands fail in this worktree on this machine (repo owned by `CodexSandboxOffline`, running as `adame`), which can break the guarded import/validate workflow.
- **Evidence:** `git -C equity-data-v1-worktree status` ownership error; same issue was fixed for `integrated-market-platform` on 2026-09-04 via `git config --global --add safe.directory`.
- **Fix:** add the safe.directory entry for `equity-data-v1-worktree`; run `python tools/monorepo_guard.py validate` to confirm both worktrees readable.
- **Acceptance:** `git -C equity-data-v1-worktree status` and `monorepo_guard.py validate` succeed locally.

### P1-8 — Commit + snapshot-refresh the short-squeeze working tree

- **Problem:** 213 modified files (~6.5k insertions / ~3.1k deletions) on `phase/3e-historical-acquisition` exist only in the working tree; the parent snapshot points at the older committed `0b40834`.
- **Evidence:** `git -C short-squeeze-project status --short` (213 files); `workspace-manifest.json` source_commit `0b408349…`.
- **Fix:** complete the short-squeeze work in its own repo (commit + PR per its own workflow), then refresh the parent snapshot through the guarded import (`docs/MONOREPO_WORKFLOW.md`).
- **Acceptance:** short-squeeze repo is clean or has a tracked branch/PR; parent snapshot commit updated via import; `monorepo_guard.py validate` passes.

---

## P2 — Hygiene and documentation

### P2-1 — Idea → experiment → evidence → learning registry (non-authoritative)

- **Problem:** product ideas are an informal short list; decision-research cards are formal but narrow; nothing traverses idea → hypothesis → card → outcome → learning as one record.
- **Evidence:** `docs/product/PRODUCT_BACKLOG.md`; decision-research card registry (`evidence/research/experiment-cards/`); `docs/engineering/CONTROLLED_ADAPTATION_V1.md`.
- **Fix:** lightweight machine-readable idea/experiment registry reusing OF-03 capability/SOP/workflow patterns; explicitly non-authoritative.
- **Acceptance:** an idea can be traced to its preregistered experiment card and outcome; registry is documented as non-authoritative.

### P2-2 — Data-acquisition boundary guard

- **Problem:** `pipelines/stock_data` scraper output is explicitly non-admitted SQLite; nothing mechanically prevents accidental reference by admitted research paths.
- **Evidence:** `pipelines/stock_data/README.md`; `docs/data/EQUITY_DATA_ACQUISITION.md`.
- **Fix:** namespace/import convention + CI check so non-admitted stores cannot be imported by admitted research code.
- **Acceptance:** a CI test proves admitted research modules cannot import the acquisition subsystem.

### P2-3 — Supersede layered docs (roadmaps, README vs PROGRAM_STATUS, public/private wording)

- **Problem:** THREE/FOUR/FIVE-lane reconciliations + cooperative master lack superseded headers; root README still carries whole-program status; `docs/MONOREPO_WORKFLOW.md` calls the public repo "private".
- **Evidence:** `docs/research/{THREE,FOUR,FIVE}_LANE_ROADMAP_RECONCILIATION.md`; root `README.md`; `docs/MONOREPO_WORKFLOW.md`; `docs/platform/PROGRAM_STATUS.md`.
- **Fix:** add superseded headers with forward links; route status readers to canonical docs; correct public/private wording.
- **Acceptance:** `tools/check_docs_links.py` passes; each superseded doc links to its current replacement.

### P2-4 — Donor isolation verification

- **Problem:** donors are local-only by policy and can submit paper/live-style orders; they must never enter the platform execution path.
- **Evidence:** `.gitignore`; publish commit `cfdebaa`; `PROJECT_NOTES_INDEX.md` cautions.
- **Fix:** verify no platform adapter imports donor execution entry points; optionally tag any donor-derived logic with provenance.
- **Acceptance:** a search/CI check confirms donor execution modules are unreachable from platform code.

### P2-5 — Per-lane doctrine verification (no code change)

- **Problem:** none (preventative) — confirm each new lane preserves "no composite score / no fabricated synthesis / no universal news score" and cross-lane evidence provenance.
- **Evidence:** SHARED P2/P3/P4 specs; ADR-0006; decision-research synthesis rules.
- **Fix:** add a checklist item in the conflict-detection section of `PLATFORM_COOPERATIVE_MASTER_ROADMAP.md`.
- **Acceptance:** the conflict checklist includes the doctrine bullets.

---

## Item cross-reference

| Priority item | Review finding |
|---|---|
| P0-1 | Gates G1/G3/G4/G5, finding P1/D1 |
| P0-2 | S1 |
| P0-3 | L1 |
| P0-4 | S4 |
| P1-1 | S3 |
| P1-2 | S2 |
| P1-3 | P3 |
| P1-4 | L2 |
| P1-5 | D2 |
| P1-6 | V2 |
| P1-7 | H1 |
| P1-8 | H2 |
| P2-1 | P2 |
| P2-2 | P4 |
| P2-3 | H3/L3 |
| P2-4 | H4 |
| P2-5 | L4/D3 |
