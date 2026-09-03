# PLATFORM-P4-001 — Code-Grounded Audit

**Audit date:** 2026-08-22
**Status of this note:** **ALL FINDINGS F1–F8 APPLIED** to the spec on
2026-08-22 (pending principal review along with the spec itself). F9 is
deferred as a code change outside the spec's scope.
**Subject spec:** [`2026-08-22-platform-p4-broker-paper-001-design.md`](../docs/superpowers/specs/2026-08-22-platform-p4-broker-paper-001-design.md)
**Method:** Walked every claim the spec makes about **existing code** that the
Tradier paper adapter / idempotency / reconciliation will build on. New-contract
claims (broker payload models, reconciliation engine, broker entry points) are
itemized as as-built checks below. No code or governed subjects were mutated.
**Scope note:** `main` at `59b3716` (spec + audit landed at `4399268`); Phase 1 ADR
drift resolved (FULL green). No implementation exists for P4 yet.

---

## 1. Verified accurate against source (spec claims hold)

| # | Spec claim | Verified in | Notes |
|---|---|---|---|
| V1 | `PaperExecutionProvider` protocol exists per ADR-PROV-001 | `providers/contracts.py` — `place_order(intent) -> ProviderResult`; sentinels `PROVIDER_UNAVAILABLE`, `EXECUTION_DISABLED` | Protocol has **only** `place_order`; cancel/fetch are adapter-local (§5.1 wording is consistent) |
| V2 | Per-event provenance vocabulary (provider, entitlement, event-time, receive-time, symbol mapping, latency/quality, raw source) | `providers/envelope.py::build_provider_metadata` — `provider_id`, `entitlement`, `event_time_ns`, `receive_time_ns`, `symbol_mapping` (via `SymbolMapping`), `latency_quality`, `raw_source_reference`; envelope schema validated by `contracts/envelope.py::validate_envelope` | Field names corrected in the spec by F2 |
| V3 | `build_user_order_intent` already requires `idempotency_key` + `client_order_id`; `research_candidate_id` wired with fail-closed validation | `paper/contracts.py::build_user_order_intent` (required params; `RESEARCH_CANDIDATE_ID_PREFIX` + uuid validation); `normalize_execution_intent` copies `research_candidate_id` | DEC-RESEARCH audit F6 (normalize list) confirmed handled |
| V4 | Internal idempotency primitive exists | `paper/ledger.py` — `idempotency_index`, `record_idempotent_order`, `lookup_idempotent_order`; `paper/execution.py::submit_interactive_order` returns `duplicate: True` on replay | Storage primitive reusable; "submission-record-before-network" ordering guarantee is new in P4 |
| V5 | `OrderSubmitted` event carries `client_order_id` / `idempotency_key` / `intent_id` | `paper/ledger.py::append_order` payload; `project_orders`/`project_execution_trace` consume the same keys | Exact payload shape the spec's §6 submission record describes |
| V6 | Lifecycle: `WORKING` reserved for broker LIMIT orders; transitions enforced | `paper/contracts.py` `ORDER_LIFECYCLE_STATES` (incl. `WORKING`) + `VALID_ORDER_TRANSITIONS` (`SUBMITTED → REJECTED/WORKING/…`, `WORKING → PARTIALLY_FILLED/FILLED/CANCEL_PENDING/REJECTED/EXPIRED`) | P1 order-lifecycle spec: "WORKING = Resting/working (future LIMIT/broker adapters)" — P4's mapping claim is consistent |
| V7 | Mode constants exist | `operating_modes.py` — `DATA_MODES` incl. `BROKER_DELAYED`; `EXECUTION_MODES` incl. `BROKER_PAPER`; `PROVIDER_IDS` incl. `TRADIER`; `EXECUTION_AUTHORITIES` incl. `PAPER_ONLY`; `PAPER_EXECUTION_AUTHORITIES = {AUTHORIZED, PAPER_ONLY}` | Authorization matrix in spec §3 maps cleanly onto existing constants |
| V8 | `IMP_LIVE_FIXTURE_FEED` fixture-replay precedent | PLATFORM-DATA-001 §Configuration + `.env.example` | Justifies the sandbox-contract fixture approach (§5.1, §10) |
| V9 | Execution trace already reserves broker fields | `paper/ledger.py::project_execution_trace` — `broker_order_id: None`, `broker_order_submitted: False`, `broker_modifications: 0`, `broker_cancels: 0`; P3.2 UI trace panel renders "broker order submitted = NO" | Spec now requires populating these via F6 |
| V10 | Reconciliation concept already has a field | `paper/ledger.py::project_risk` returns `reconciliation_status: "INTERNAL_AUTHORITATIVE"` | Spec now reuses/extend this field via F7 |
| V11 | Fail-closed composition slot exists | `providers/composition.py` — `ProviderComposition.paper_execution` defaults to `DisabledPaperExecutionProvider` (gated on `EXECUTION_ENABLE=1`; returns `EXECUTION_DISABLED` / `EXECUTION_ADAPTER_NOT_IMPLEMENTED`) | Spec now names this slot via F5; legacy `EXECUTION_ENABLE` gate flagged by F8 |
| V12 | Broker fills can be normalized into the canonical ledger shape | `portfolio/ledger.py::apply_fill`/`build_ledger_state` consumed by `paper/ledger.py::_project_ledger` | Fill-authority split resolved in the spec by F1 |

## 2. Findings — resolution status

### F1. Fill-authority contradiction (was blocking) — ►APPLIED
Spec §3 now declares **fill authority is per mode**: the broker is authoritative
for lifecycle **and fills** inside a `BROKER_PAPER` account (broker fill events
normalized into the canonical shape and projected by `apply_fill`), while
`INTERNAL_SIMULATION` remains `BarConservativeSimulator`-authoritative; the two
modes never share a fill source. §8's diagram reflects the split, §12 scopes
broker fills as ledger-authoritative-but-not-research, §9 adds `P4-FILL-001`,
and §10 adds a fill-authority regression fixture. This makes account-level
reconciliation meaningful and `P4-REC-002` reachable.

### F2. Provenance field names — ►APPLIED
Spec §4 now lists the canonical vocabulary (`provider_id`, `entitlement`,
`event_time_ns`, `receive_time_ns`, `symbol_mapping`, `latency_quality`,
`raw_source_reference`), requires verbatim reuse of `build_provider_metadata` +
`validate_envelope`, and pins PLATFORM-DATA-001 timestamp semantics
(`available_time` = `local_received_time` for live pushes). `latency_ms` /
`raw_source_ref` removed. `P4-PROV-001` updated to the canonical names.

### F3. Broker entry points vs the INTERNAL_SIMULATION guard — ►APPLIED
Spec §5.1 names `submit_broker_paper_order` / `cancel_broker_paper_order` and
states explicitly that `submit_interactive_order` / `cancel_interactive_order`
are **not** loosened (`PAPER_EXECUTION_MODE_INVALID` stays the
PLATFORM-DATA-001 invariant). §9 adds `P4-SAFE-003`; §8 shows the split path.

### F4. `IMP_BROKER_PAPER_EXECUTION` / `PAPER_ONLY` authority — ►APPLIED
Spec §5.1 + §5.3 map `BROKER_PAPER → PAPER_ONLY` under
`IMP_BROKER_PAPER_EXECUTION`, keeping `INTERNAL_SIMULATION → AUTHORIZED` on
`IMP_PAPER_EXECUTION`, both already accepted by `PAPER_EXECUTION_AUTHORITIES`.
`resolve_execution_authority` is the function to change in 4A.

### F5. Adapter placement / composition — ►APPLIED
Spec §5.1 + §11 place the adapter at
`src/market_platform_foundation/providers/adapters/tradier_paper.py`, injected
into `ProviderComposition.paper_execution` (replacing
`DisabledPaperExecutionProvider` + its `EXECUTION_ADAPTER_NOT_IMPLEMENTED`);
reconciliation engine under `platform/reconciliation/**`. §13 completion lists
the composition wiring as a deliverable.

### F6. Execution-trace broker fields — ►APPLIED
Spec §5.1 requires populating `broker_order_id`, `broker_order_submitted: True`,
`broker_modifications`, `broker_cancels` in `BROKER_PAPER` mode; §9 adds
`P4-TRACE-001`; §13 lists it in the completion definition.

### F7. Reconciliation vocabulary — ►APPLIED
Spec §7 reuses/extends `project_risk.reconciliation_status`
(`BROKER_RECONCILED` / `MISMATCH` / `RECONCILIATION_HOLD`) and records reports
as a new `ReconciliationRecorded` event in `EVENT_TYPES`; §8 reflects it; §13
lists the integration as a deliverable. No parallel vocabulary.

### F8. Env-gate and docs gaps — ►APPLIED
Spec §5.3 flags the competing legacy `EXECUTION_ENABLE` gate for
reconciliation/deprecation in 4A; §11 and §13 make `.env.example` (new gates)
and `docs/providers/TRADIER_PAPER.md` explicit deliverables.

### F9. CI hardening for `IMP_LIVE_EXECUTION` — ►DEFERRED (out of scope)
Adding `IMP_LIVE_EXECUTION` to `tools/validate.py::ALL_LIVE_GATES` is a code
change to CI tooling, not a spec concern. The spec already states the invariant
(`P4-SAFE-002`). Carry this as a follow-up when CI gates are next touched.

## 3. As-built checks (re-verify as each P4 component lands)

| Component | Check |
|---|---|
| `providers/adapters/tradier_paper.py` | gate triple verified before any request; sandbox endpoint enforced; `place_order` returns `ProviderResult` on the contract; cancel/fetch adapter-local; unmapped symbol fails closed |
| Broker payload models | canonical field names match `build_provider_metadata` exactly (F2); broker fills normalize into `apply_fill` shape (F1) |
| Idempotency | submission event precedes network call (V4/V5 primitives reused); N retries → 1 submission record (adversarial fixture); ambiguous outcome → fetch/reconciliation, no blind retry |
| Broker entry points | `submit_interactive_order` guard untouched (F3); new `submit_broker_paper_order` / `cancel_broker_paper_order` distinct |
| `operating_modes.resolve_execution_authority` | `BROKER_PAPER → PAPER_ONLY` under `IMP_BROKER_PAPER_EXECUTION` (F4) |
| `project_execution_trace` | broker fields populated in BROKER_PAPER mode (F6) |
| `project_risk` | `reconciliation_status` extended + `ReconciliationRecorded` event type (F7) |
| `ProviderComposition` | Tradier adapter injected into `paper_execution` slot; `EXECUTION_ENABLE` reconciled/deprecated (F5, F8) |

## 4. Residual / open questions

- F9 (CI hardening) is deferred — code change outside spec scope.
- Tradier wire specifics (endpoints, payloads, sandbox account model) are unknown
  until the sandbox is exercised; the spec defers them to
  `docs/providers/TRADIER_PAPER.md`.
- Whether the `paper` suite (`tests/platform`) or a new suite owns the P4 tests
  is a manifest question; adding a manifest suite is a governed edit requiring
  principal approval (spec §11 already flags this).

**Overall:** all code-facing claims remain accurate (12/12). The one blocking
design question (F1) and the seven follow-ups (F2–F8) are **resolved in the
spec and awaiting principal review**; no implementation started. No code or
governed subjects were mutated.

## 5. Spec revision cross-check (post-F1–F8 edits)

Both hashes are over **LF bytes** (the spec file is LF-only on disk — see the
Phase 1 drift precedent; `git cat-file` and working-tree bytes agree when CR is
stripped), so they are directly comparable.

| Version | Identity | SHA-256 (LF bytes) |
|---|---|---|
| **Pre-edit** | committed `4399268` (2026-08-22), git blob `6ec8d277…` | `89999F4774A4871BDB03C1870DE073ECD26F436349C7EC310409764D3F6C9BFA` |
| **Post-edit** | working tree after F1–F8 + "sub-milestones" wording fix | `F0129919EF5A34FC1D7028CF83AEC3F047AF2D309F8D26785EDCC6DB423B2C8B` |

- **Authoritative diff:** `git diff 4399268 -- docs/superpowers/specs/2026-08-22-platform-p4-broker-paper-001-design.md`.
- **Governed state:** unchanged; the design spec is not a governed hash-bound
  artifact, so no governed hash moved. Once the principal approves and the
  post-edit spec is committed, the new blob hash supersedes the POST value above;
  the pre/post diff and this table remain the review trail.
