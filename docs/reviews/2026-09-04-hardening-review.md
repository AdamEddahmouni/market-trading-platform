# Workspace Hardening Review — 2026-09-04

| Field | Value |
|---|---|
| Date | 2026-09-04 |
| Scope | Whole workspace: `integrated-market-platform` (canonical platform), `equity-data-v1-worktree`, `governed-ticker-metadata-enrichment`, `short-squeeze-project`, parent workspace tooling/governance, and donor/reference projects at the workspace root |
| Method | Desk review of canonical program docs, engineering registers, lane roadmaps/audits, validation receipts, CI workflows, and a source pass over strategy/runtime/lane registries |
| Companion | [Hardening task plan](2026-09-04-hardening-task-plan.md) — tracked, checkable P0/P1/P2 backlog |
| Status | Review only. No code, policy, or authority changed. |

This review asks one question: **what must be true — and what is not yet true — before any real trading can happen**, judged across three axes: (1) strategies, (2) pipelines/ideas, and (3) how the different lanes are handled. Findings cite evidence paths so each can be verified.

---

## 1. Workspace topology (what was reviewed)

| Repo / area | Role | Where truth lives |
|---|---|---|
| `integrated-market-platform/` (nested repo, archived remote) | Canonical governed trading platform: Demo replay / Paper simulation / Live observational | `projects/integrated-market-platform` snapshot is tracked by this workspace; active dev happens in the nested repo; CI now validates the snapshot (`projects/integrated-market-platform`) from parent workflows |
| `equity-data-v1-worktree/`, `governed-ticker-metadata-enrichment/` | Worktrees sharing one underlying history (equity-data foundation / governed ticker metadata feature branches) | Tracked snapshots under `projects/`; local clones at workspace root |
| `short-squeeze-project/` | Independent public short-squeeze screener (evidence/provenance-driven, read-only research) | Own git repo (public); snapshot under `projects/` |
| Parent workspace | Manifest, monorepo guard, history audit, CI | `workspace-manifest.json`, `docs/MONOREPO_WORKFLOW.md`, `docs/history/`, `.github/workflows/` |
| Donor/reference projects (root) | Research donors only; local-only, excluded from public publish | `PROJECT_NOTES_INDEX.md`; `.gitignore` |

Reviewed sources include: `docs/platform/PROGRAM_STATUS.md`, `docs/platform/MASTER_ROADMAP.md`, `docs/platform/MASTER_ARCHITECTURE.md`, `docs/engineering/TECH_DEBT.md`, `docs/engineering/WORK_LOG.md` (through 2026-09-04), `docs/engineering/*_V1.md` (promotion/adaptation/qualification/canary), `docs/research/PLATFORM_COOPERATIVE_MASTER_ROADMAP.md` + per-lane audits/gap analyses/discrepancy registers, `docs/architecture/PAPER_DECISION_LIFECYCLE.md` + ADR-0006/0007/0008, `docs/PROJECT_STATUS.md`, `docs/product/PRODUCT_BACKLOG.md`, artifact `*_KNOWN_LIMITATIONS.md`, CI workflows, and source registries (`paper/decision_source.py`, `ui/.../paperOrderDraft.ts`, `ui/.../laneRegistry.ts`, `ui/.../paperDecisionSemantics.ts`).

---

## 2. Verdict

**The safety architecture is the strongest part of this workspace and must be preserved as-is.** Mode authority (Demo/Paper/Live), fail-closed gates, immutable ledger/record semantics, human session authorization + per-order confirmation, no autonomous live execution, no automatic broker failover, and strict provenance are all genuinely hardened and repeatedly evidenced.

**The gap is not safety architecture — it is forward evidence.** The workspace is deliberately, correctly blocked from real trading (LIVE-001) and from claiming any validated edge. Everything material is fixture-scope; P6 shadow forward-validation and EVIDENCE-01C are deferred; the live canary has never executed; no production broker transport is accepted; real-wire paper adapters are unexercised. Those are *the* blockers, and they are governance decisions, not bugs.

Below that, the review finds a smaller set of **hardening defects and drifts** worth fixing regardless of the trading decision:

1. **Lane identity is defined three-plus times with no single source of truth and no cross-check test** (dead backend constant + two UI registries + a hand-written evidence-lane map). Adding or renaming a lane today risks silent UI/backend drift.
2. **Strategy/idea machinery grew very fast (2026-09-01→04)** — scanner, match, opportunity economics, comparison, allocation, order-ready, attribution, learning, profitability observability. Record-level immutability is excellent; the risk is *path multiplicity* and promotion machinery that has never been exercised end-to-end.
3. **Workspace hygiene issues that can silently break the import/guard workflow**: a git "dubious ownership" failure in `equity-data-v1-worktree` and a very large (213-file) uncommitted delta in `short-squeeze-project` that the parent snapshot does not contain.
4. **Documentation parallelism** (THREE/FOUR/FIVE-lane reconciliations + cooperative master; root README vs `PROGRAM_STATUS.md`; a workflow doc that calls a public repo "private") creates ambiguity about what is *current*.
5. **CI/validation is excellent but now bifurcated** between the archived nested repo's workflows and the parent snapshot workflows — reconcile so one canonical gate is unambiguous.

---

## 3. What is strong (keep as-is)

- **Mode authority and fail-closed semantics** — `docs/architecture/MODE_AUTHORITY.md`, env gates in `CONFIGURATION.md`; frontend gating is UX, backend gates are security.
- **Immutable records everywhere**: `EventV1`, prediction ledger entries, `StrategyMatch`, `CapitalAllocationDecisionV1`, `OrderReadyV1`, fill events, reconciliation events — append-only with identity covering content.
- **Paper decision lifecycle** — `PAPER_DECISION_LIFECYCLE.md` is a single authoritative end-to-end description (opportunity → allocation → risk → order-ready → submit → fill → settlement → attribution), with immutable provenance (`decision_source_snapshot`, `correlation_id`) and honest failure behavior.
- **Validation ladder** — manifest-driven `tools/validate.py` + `tools/imp.py`; full run green at **3487 tests / 43 skipped / 0 failures / 0 errors** (2026-09-04 receipt), UI vitest ~428 passing with typecheck/build and bundle budget passing.
- **Repository closure audit** fail-closed on unclassified paths; evidence-churn bug fixed 2026-09-04 so tests no longer dirty tracked assistant-audit evidence.
- **Per-lane research discipline** — each lane has current-state audits, capability gap analyses, glossary, discrepancy registers, and target architecture docs; cross-lane boundary matrix exists.
- **Cross-lane provenance & account scoping** — ADR-0006 lane provenance envelope, ADR-0007 account-scoped snapshots, ADR-0008 auth; TD-001…TD-007 mostly closed.
- **Honest known-limitations artifacts** for every acceptance build (no overclaiming).

---

## 4. The non-negotiable chain before ANY trading

Every limitation artifact and canonical doc repeats some subset of this chain; the review consolidates it as the standard to hold:

```text
real observational market data
!= live provider connectivity
!= production live broker transport
!= operationally accepted live execution
!= authorized live session
!= authorized individual order
!= broker acceptance or fill
(and, separately) fixture/backtest evidence
!= forward/out-of-sample evidence
!= promoted, validated strategy
!= execution authority
```

**Readiness gates derived from the evidence (all currently unmet):**

| Gate | Status (evidence) |
|---|---|
| G1 Forward validation campaign active (P6 Shadow Run 1 / EVIDENCE-01C) | ❌ Deferred — `PROGRAM_STATUS.md`, `MASTER_ROADMAP.md`, `PRODUCT_BACKLOG.md` |
| G2 At least one strategy promoted through the champion/challenger ladder on forward evidence | ❌ No `SUPPORTED` strategy; decision-research cards pinned `INCONCLUSIVE` / `INSUFFICIENT_DATA` / `NEEDS_PROSPECTIVE_VALIDATION` (`evidence/research/decision-research-gate-report.json`) |
| G3 Live canary executed with real micro-notional submits | ❌ `CANARY_NOT_EXECUTED` — BUILD25/29 limitation artifacts |
| G4 Accepted production live broker transport exercised on real wire | ❌ `ABSENT`; Tradier sandbox wire unexercised; Moomoo paper fixture-only (TD-004 open) |
| G5 Real-provider observational shakedown (EVIDENCE-01C) | ❌ Deferred; Moomoo OpenD not installed on this machine (see `fix(tests): accept OPEN_D_NOT_INSTALLED`) |
| G6 ES-session acceptance | ❌ Blocked on lawful ES bytes (ADR-DATA-001) — keep futures TREASURY/METALS fail-closed |
| G7 Strategy attribution parity with authoritative ledger enforced as an invariant | ⚠️ Expected by design; make it a hard gate on materialization (finding S4) |

Nothing below should be read as suggesting these gates be relaxed. The task plan instead hardens everything *around* them so that when a gate opens, the machinery behind it is trustworthy.

---

## 5. Findings

### A. Strategies

**S1 — No validated edge exists, by design; promotion path never exercised end-to-end.**
Evidence: `CHAMPION_CHALLENGER_PROMOTION_V1.md` (BUILD 20) defines promotion on preregistered forward evidence; decision-research milestone A gate is 101/101 but every card result is `INCONCLUSIVE`/`INSUFFICIENT`/`NEEDS_PROSPECTIVE_VALIDATION`. No champion has ever been promoted; the ladder has never run against a real forward dataset.
Fix direction: keep the gate; add an *exercisable* promotion dry-run harness that replays recorded paper outcomes through promotion policy and emits the decision record — so the machinery is proven before it is ever needed. (Task P0-2.)

**S2 — Strategy layer grew rapidly; path multiplicity is the main technical risk.**
Evidence: 2026-09-01→04 added typed `StrategyDefinition`, universal scanner, `StrategyMatch`, opportunity economics sidecar + P4 adapter + bridge, clustering/comparison/allocation, `OrderReadyV1`, attribution sidecar/materializer, learning boundary, and profitability observability (`WORK_LOG.md`). Each layer is immutable and tests pass, but several parallel constructions exist (OpportunityEngine vs. new scanner+sidecar+bridge; attribution sidecar vs. ledger).
Fix direction: one canonical narrative (bridge/universal path) with the older construction explicitly deprecated in docs; add negative tests for cross-path identity collisions; make "one way to build an opportunity/decision" an enforced invariant. (Task P1-3.)

**S3 — Strategy eligibility for execution intent is implicit.**
Evidence: research handoffs are non-promotional and cannot promote/execute (learning boundary tests), but there is no single checkable predicate "this strategy may drive OrderReadyV1 with execution intent" used at runtime.
Fix direction: a small, explicit eligibility gate on the order-ready path (preregistered + promoted state + forward evidence class), enforced by test, so intent is auditable per order. (Task P1-2.)

**S4 — Attribution is a sidecar with a parity expectation, not yet an enforced invariant.**
Evidence: `portfolio/attribution.py` + materializer; reconciliation expects the strategy slice to agree with authoritative ledger P&L.
Fix direction: make parity a hard gate on every materialization (fail closed on mismatch), with mismatch surfaced as an immutable event, mirroring P4-REC semantics. (Task P1-1.)

### B. Pipelines / ideas

**P1 — The full strategy paper chain is implemented but forward-validated nowhere.**
Evidence: backend-only deterministic loop documented in `PAPER_DECISION_LIFECYCLE.md`; P6 shadow infra exists (`shadow/**`) with leakage guard and a preregistered protocol, but P6 Shadow Run 1 is deferred and its stopping rule (12/65 scheduled opportunities) was unmet while active.
Fix direction: keep deferred status honest (done); treat reactivation as the P0 for forward evidence (G1). (Task P0-1.)

**P2 — Idea capture is informal at the product level; experiment registration is formal but narrow.**
Evidence: `PRODUCT_BACKLOG.md` is a short list; decision-research experiment cards are hash-bound and preregistered (excellent) but cover only 6 SS cards; MRA assistant is read-only; controlled adaptation (`CONTROLLED_ADAPTATION_V1.md`) emits `ResearchTriggerV1` but nothing connects backlog → hypothesis → card → outcome → learning as one traversable record.
Fix direction: a lightweight machine-readable idea/experiment registry (reuse OF-03 capability/SOP/workflow patterns) linking idea → preregistered experiment → evidence → learning; keep it non-authoritative. (Task P2-1.)

**P3 — Unified tracing is almost complete; broker/reconciliation spans remain.**
Evidence: RT-01 ingest-path baseline accepted; paper pipeline tracing landed 2026-09-04 (`rt01/instrumentation/paper.py`); broker/reconciliation tracing and full opportunity→risk→order_ready technical spans are still follow-ons.
Fix direction: extend RT-01 to broker-paper submission/poll/reconcile seams as P1; do not build before measured need (IMP-RT-02 rule). (Task P1-4.)

**P4 — Data acquisition pipelines must stay clearly outside admitted research data.**
Evidence: `pipelines/stock_data` is a "stealth scraper" acquisition subsystem whose SQLite output is explicitly non-admitted; provider live captures are observational and non-admitted.
Fix direction: keep the boundary; consider a guard so non-admitted stores cannot be referenced by admitted research paths by import/namespace convention (documented + CI check). (Task P2-2.)

### C. Lanes

**L1 — Lane/module identity is duplicated with no single source of truth.**
Evidence (direct source pass):
- Backend: `src/market_platform_foundation/paper/decision_source.py` defines `KNOWN_LANE_MODULES` frozenset — **never imported anywhere** (dead).
- UI: `ui/src/components/paper-now/paperOrderDraft.ts` `LANE_MODULE_IDS` + separate labels map.
- UI: `ui/src/components/workspace-module-shared/laneRegistry.ts` `WORKSPACE_LANE_REGISTRY` (same set, own labels/order).
- UI: `ui/src/components/paper-workspace/paperDecisionSemantics.ts` hand-written `EVIDENCE_LANE_TO_MODULE_ID` + `MODULES_WITHOUT_EVIDENCE_LANE`.
- `docs/architecture/DATA_CONTRACTS.md` calls `LANE_MODULE_IDS` canonical — but that is UI-only.
No test asserts backend set == UI list == evidence map. Today they happen to agree; nothing prevents silent drift on the next lane addition.
Fix direction: one canonical lane registry (single source, e.g. a Python module plus generated TS or a shared JSON), consumed by backend, UI registries, and evidence map; add an equality/closure test; route new lanes through `sops/ADD_WORKSPACE_LANE.md` which must edit exactly one file. (Task P0-3.)

**L2 — Two "lane" vocabularies coexist and are easy to confuse.**
Evidence: workspace lane modules (10, UI + paper provenance) vs. live-screener lanes `MOMENTUM`/`SQUEEZE`/`CATALYST`/`SWING` (`discovery/mixed.py`) vs. research-domain lanes (SS/Options/Futures/OF/MC/PI). `continuation-state.md` and `paperDecisionSemantics.ts` each hold partial maps.
Fix direction: glossary entry + a single mapping table (discovery lane → workspace module → research family) with tests; keep them distinct concepts. (Task P1-5.)

**L3 — Lane roadmaps are layered and partly superseded; "current" is ambiguous.**
Evidence: `THREE_LANE_ROADMAP_RECONCILIATION.md`, `FOUR_LANE_ROADMAP_RECONCILIATION.md`, `FIVE_LANE_ROADMAP_RECONCILIATION.md`, plus `PLATFORM_COOPERATIVE_MASTER_ROADMAP.md` (which itself says it supersedes independent lane sequencing) — none carries a clear superseded header.
Fix direction: mark superseded docs with forward links to the cooperative master + per-lane current-state audits; keep history immutable. (Task P2-3.)

**L4 — Cross-lane semantics are well-governed at the contract level.**
Evidence: SHARED P2/P3/P4 contracts, ADR-0006 provenance envelope, cross-lane evidence UI block, contradiction semantics with fail-closed `MIXED`/`NO_HYPOTHESIS`, no universal news/composite score.
No defect found. Preserve the "no composite score / no fabricated synthesis" doctrine as new lanes arrive. (Task P2-4 — verify on each new lane, no code change.)

### D. Data & providers

**D1 — Real-wire gaps are the single largest external dependency.**
Evidence: TD-004 open (Moomoo paper real-wire, fixture-proven only, OpenD TCP-only); Tradier sandbox adapter (P4-4A/4B) not exercised against the real sandbox; Moomoo OpenD not installed on this machine; EVIDENCE-01C deferred.
Fix direction: when connectivity is available, run the bounded shakedown and record wire contracts; keep fixtures authoritative until then. (Task P0-4 / P1-6.)

**D2 — Many public providers are fixture-first; live opt-in exists but is unadmitted.**
Evidence: ADR table in root README (SEC EDGAR/FTD, FINRA/Nasdaq Reg SHO, FRED, CFTC COT, EIA, weather, CBOE stats) — live captures explicitly "not admitted research datasets".
Fix direction: keep admission gates; no model retraining on unadmitted captures (already doctrine — verify with a guard test). (Task P1-7.)

**D3 — ES-session acceptance remains blocked (ADR-DATA-001).**
Evidence: BUILD35 limitations + README. Futures lane ships EQUITY_INDEX + ENERGY/CL; TREASURY/METALS fail closed.
No action unless lawful ES bytes are procured. Keep status visible in `PROGRAM_STATUS.md` (done). (Task P2-5 — none, verify only.)

### E. Validation, CI, governance

**V1 — Validation is green and cheap enough to run frequently.**
Evidence: 3487 tests / 43 skipped / 0 failures (2026-09-04); UI vitest ~428, typecheck + build + bundle budget pass; manifest-driven pyramid in `DEVELOPER_OPERATING_SYSTEM.md`.
Keep. No change.

**V2 — CI is duplicated between the archived nested repo and the parent snapshot.**
Evidence: nested `integrated-market-platform/.github/workflows/{imp-validate,imp-python}.yml` and parent `.github/workflows/` with the same names; parent `imp-python.yml` runs against `projects/integrated-market-platform`; nested remote is archived/read-only.
Fix direction: declare the parent snapshot workflows canonical; remove or clearly mark nested duplicates stale to avoid drift confusion. (Task P1-8.)

**V3 — Guard tooling is solid; history audit is regenerable.**
Evidence: `tools/monorepo_guard.py validate --ci`, `tools/generate_history_ledger.py validate --ci` in CI; tests `test_monorepo_guard`, `test_history_ledger`.
Keep. No change.

### F. Workspace hygiene

**H1 — `equity-data-v1-worktree` fails git access on this machine ("dubious ownership").**
Evidence: `git -C equity-data-v1-worktree status` → ownership error (repo owned by `CodexSandboxOffline`, running as `adame`); same class of issue was already fixed for `integrated-market-platform` on 2026-09-04 via `git config --global --add safe.directory`.
Fix: add the safe.directory entry; verify `monorepo_guard.py validate` passes with both worktrees readable. (Task P1-9.)

**H2 — `short-squeeze-project` has a large uncommitted delta the parent snapshot lacks.**
Evidence: 213 modified files, ~6,469 insertions / ~3,129 deletions, branch `phase/3e-historical-acquisition`, including `.env.example` and research datasets; parent snapshot points at `0b40834` (committed HEAD), so uncommitted work is not captured anywhere except the working tree.
Fix: commit/push the short-squeeze work in its own public repo (its own workflow), then refresh the parent snapshot via the guarded import; until then flag snapshot lag. (Task P1-10.)

**H3 — Documentation parallelism / stale wording.**
Evidence: `docs/MONOREPO_WORKFLOW.md` calls `AdamEddahmouni/market-trading-platform` "private", while root README calls it the public workspace (repo summary: public); root README still carries whole-program status that `PROGRAM_STATUS.md` supersedes.
Fix: reconcile wording; route readers to canonical docs with superseded headers. (Task P2-3.)

**H4 — Donor projects remain local-only and must never enter the execution path.**
Evidence: `.gitignore` + publish commit excluded donors from the public repo; `PROJECT_NOTES_INDEX.md` warns several donors can submit paper/live-style broker orders and none has a validated edge.
Fix: keep isolation; do not wire donor entry points into platform adapters. Optionally encode a "donor provenance" tag if any donor-derived logic is ever ported, so it is auditable. (Task P2-6.)

---

## 6. Suggested sequence

- **P0 (before any trading / promotion / forward campaign):** single lane source of truth (L1), promotion dry-run harness (S1), explicit eligibility gate (S3), attribution parity gate (S4), forward-campaign readiness checklist (G1/G3/G4/G5).
- **P1 (hardening while gates stay closed):** RT-01 broker/reconcile spans (P3), CI canonicalization (V2), safe.directory fix (H1), short-squeeze commit + snapshot refresh (H2), canonical opportunity path enforcement (S2), discovery-lane mapping (L2), provider admission guard tests (D2).
- **P2 (hygiene/docs):** idea registry (P2), data-boundary guard (P4), supersede old roadmap/README wording (H3/L3), donor isolation check (H4), per-lane doctrine verification (L4/D3).

Full checkable items with acceptance criteria: **[Hardening task plan](2026-09-04-hardening-task-plan.md)**.
