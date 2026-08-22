# PLATFORM-P4-001 — Code-Grounded Audit

**Audit date:** 2026-08-22
**Subject spec:** [`2026-08-22-platform-p4-broker-paper-001-design.md`](../docs/superpowers/specs/2026-08-22-platform-p4-broker-paper-001-design.md)
**Method:** Walked every claim the spec makes about **existing code** that the
Tradier paper adapter / idempotency / reconciliation will build on. New-contract
claims (broker payload models, reconciliation engine, broker entry points) are
itemized as as-built checks below. No code or governed subjects were mutated.
**Scope note:** `main` at `59b3716`; Phase 1 ADR drift resolved (FULL green).
No implementation exists for P4 yet — the spec is a draft awaiting review.

---

## 1. Verified accurate against source (spec claims hold)

| # | Spec claim | Verified in | Notes |
|---|---|---|---|
| V1 | `PaperExecutionProvider` protocol exists per ADR-PROV-001 | `providers/contracts.py` — `place_order(intent) -> ProviderResult`; sentinels `PROVIDER_UNAVAILABLE`, `EXECUTION_DISABLED` | Protocol has **only** `place_order`; cancel/fetch are adapter-local (§5.1 wording is consistent) |
| V2 | Per-event provenance vocabulary (provider, entitlement, event-time, receive-time, symbol mapping, latency/quality, raw source) | `providers/envelope.py::build_provider_metadata` — `provider_id`, `entitlement`, `event_time_ns`, `receive_time_ns`, `symbol_mapping` (via `SymbolMapping`), `latency_quality`, `raw_source_reference`; envelope schema validated by `contracts/envelope.py::validate_envelope` | **Field names differ from spec wording — see F2** |
| V3 | `build_user_order_intent` already requires `idempotency_key` + `client_order_id`; `research_candidate_id` wired with fail-closed validation | `paper/contracts.py::build_user_order_intent` (required params; `RESEARCH_CANDIDATE_ID_PREFIX` + uuid validation); `normalize_execution_intent` copies `research_candidate_id` | DEC-RESEARCH audit F6 (normalize list) confirmed handled |
| V4 | Internal idempotency primitive exists | `paper/ledger.py` — `idempotency_index`, `record_idempotent_order`, `lookup_idempotent_order`; `paper/execution.py::submit_interactive_order` returns `duplicate: True` on replay | Storage primitive reusable; "submission-record-before-network" ordering guarantee is new in P4 |
| V5 | `OrderSubmitted` event carries `client_order_id` / `idempotency_key` / `intent_id` | `paper/ledger.py::append_order` payload; `project_orders`/`project_execution_trace` consume the same keys | Exact payload shape the spec's §6 submission record describes |
| V6 | Lifecycle: `WORKING` reserved for broker LIMIT orders; transitions enforced | `paper/contracts.py` `ORDER_LIFECYCLE_STATES` (incl. `WORKING`) + `VALID_ORDER_TRANSITIONS` (`SUBMITTED → REJECTED/WORKING/…`, `WORKING → PARTIALLY_FILLED/FILLED/CANCEL_PENDING/REJECTED/EXPIRED`) | P1 order-lifecycle spec: "WORKING = Resting/working (future LIMIT/broker adapters)" — P4's mapping claim is consistent |
| V7 | Mode constants exist | `operating_modes.py` — `DATA_MODES` incl. `BROKER_DELAYED`; `EXECUTION_MODES` incl. `BROKER_PAPER`; `PROVIDER_IDS` incl. `TRADIER`; `EXECUTION_AUTHORITIES` incl. `PAPER_ONLY`; `PAPER_EXECUTION_AUTHORITIES = {AUTHORIZED, PAPER_ONLY}` | Authorization matrix in spec §3 maps cleanly onto existing constants |
| V8 | `IMP_LIVE_FIXTURE_FEED` fixture-replay precedent | PLATFORM-DATA-001 §Configuration + `.env.example` | Justifies the sandbox-contract fixture approach (§5.1, §10) |
| V9 | Execution trace already reserves broker fields | `paper/ledger.py::project_execution_trace` — `broker_order_id: None`, `broker_order_submitted: False`, `broker_modifications: 0`, `broker_cancels: 0`; P3.2 UI trace panel renders "broker order submitted = NO" | **Pre-planned P4 integration point — spec does not mention it (see F6)** |
| V10 | Reconciliation concept already has a field | `paper/ledger.py::project_risk` returns `reconciliation_status: "INTERNAL_AUTHORITATIVE"` | **Hook the spec does not reference (see F7)** |
| V11 | Fail-closed composition slot exists | `providers/composition.py` — `ProviderComposition.paper_execution` defaults to `DisabledPaperExecutionProvider` (gated on `EXECUTION_ENABLE=1`; returns `EXECUTION_DISABLED` / `EXECUTION_ADAPTER_NOT_IMPLEMENTED`) | **The slot the Tradier adapter fills (see F5)** |
| V12 | Broker fills can be normalized into the canonical ledger shape | `portfolio/ledger.py::apply_fill`/`build_ledger_state` consumed by `paper/ledger.py::_project_ledger` | Mapping `BrokerFillEvent → fill dict` is feasible — but see F1 (authority) |

## 2. Findings / discrepancies to act on

### F1. Fill-authority contradiction — the one blocking design question (highest priority)
Spec §3 says "fills remain the internal simulator's product"; §8's diagram shows
broker status/fill events flowing into the ledger; §7 reconciles "fill count"
**and** account cash/positions with `P4-REC-002` = "0 unexplained mismatches".
Under dual-book (simulator authoritative + broker fills recorded separately),
account-level cash/position reconciliation **can never match** — sandbox fills
price at delayed quotes, simulator fills at the internal model — so `P4-REC-002`
becomes unreachable by design.
- **Recommendation:** make the broker authoritative for lifecycle **and fills in
  `BROKER_PAPER` mode only** (normalize `BrokerFillEvent` into the canonical fill
  dict and let `apply_fill` project it — V12 makes this mechanical), and scope
  the §3 simulator-fill sentence to `INTERNAL_SIMULATION` mode. Research signals
  keep using the simulator + admitted fixtures (§12 unchanged). This matches
  P1's "WORKING: future broker adapters" and makes reconciliation structural and
  meaningful (state, cumulative qty, fills, cash all derive from one source).
- Alternative (dual-book): drop account-level cash/position matching from §7 and
  reconcile order structure only. **Pick one and state it explicitly in §3/§7.**

### F2. Provenance field names drift from the canonical vocabulary
Spec §4/§9 say `latency_ms`, `quality_flags`, `raw_source_ref`; the existing
vocabulary in `build_provider_metadata` is `latency_quality: {quality_state}`,
`raw_source_reference`, and `quality_flags` (a list attached at enrichment, e.g.
`enrich_chain_contract_event`). `latency_ms` does not exist anywhere in
`providers/`.
- **Recommendation:** §4/§9 should require reuse of `build_provider_metadata`
  exactly (provider_id, entitlement, event_time_ns, receive_time_ns,
  symbol_mapping, latency_quality, raw_source_reference) and `validate_envelope`
  (per PLATFORM-DATA-001 timestamp semantics: `available_time` defaults to
  `local_received_time` for live broker pushes). Drop `latency_ms` from the spec.

### F3. Broker entry points vs the hardened INTERNAL_SIMULATION guard
`submit_interactive_order` hard-rejects `execution_mode != INTERNAL_SIMULATION`
(`PAPER_EXECUTION_MODE_INVALID`) and `cancel_interactive_order` is
simulator-bound. That guard is the safety invariant keeping
`LIVE_OBSERVATIONAL + BROKER_PAPER` unreachable (PLATFORM-DATA-001 matrix).
- **Recommendation:** §8/§9 should name **new** broker-paper entry points (e.g.
  `submit_broker_paper_order`, `cancel_broker_paper_order`) and state explicitly
  that `paper/execution.py::submit_interactive_order` is **not** loosened.

### F4. `IMP_BROKER_PAPER_EXECUTION` is a required change, not existing behavior
`resolve_execution_authority` (`operating_modes.py`) today maps `BROKER_PAPER` →
`AUTHORIZED` iff `IMP_PAPER_EXECUTION=1`. There is no `IMP_BROKER_PAPER_EXECUTION`
anywhere in the tree. The spec correctly frames this as a requirement, but the
audit pins the exact function and a cleaner fit:
- `EXECUTION_AUTHORITIES` already includes **`PAPER_ONLY`** (currently unused by
  `resolve_execution_authority`). Map `BROKER_PAPER` → `PAPER_ONLY` gated on
  `IMP_BROKER_PAPER_EXECUTION`, keeping `INTERNAL_SIMULATION` → `AUTHORIZED` on
  `IMP_PAPER_EXECUTION`. `PAPER_EXECUTION_AUTHORITIES` already accepts both.

### F5. Adapter placement should follow the composition/adapter convention
Existing provider adapters live in `providers/adapters/<name>.py` and are wired
through `ProviderComposition` (which already owns a `paper_execution` slot
defaulting to the disabled stub). Spec §11 proposes a new
`platform/broker/**` namespace.
- **Recommendation:** implement the Tradier adapter as
  `providers/adapters/tradier_paper.py` and inject it into
  `ProviderComposition.paper_execution` (replacing `DisabledPaperExecutionProvider`
  and its `EXECUTION_ADAPTER_NOT_IMPLEMENTED` sentinel); keep `platform/broker/**`
  only for orchestration if a seam is truly needed. The spec should name the
  composition slot it fills.

### F6. Pre-reserved execution-trace broker fields are unwired
`project_execution_trace` already returns `broker_order_id: None`,
`broker_order_submitted: False`, `broker_modifications: 0`, `broker_cancels: 0`,
and the P3.2 trace panel renders "broker order submitted = NO". Spec §5.1 lists
`/paper/broker/*` observability but never mentions these fields.
- **Recommendation:** P4 must populate the reserved trace fields (broker order id
  on submit, `broker_order_submitted: True`, cancels/modifications counters) —
  this is the pre-planned integration point, and leaving it `None` in
  `BROKER_PAPER` mode would regress the trace panel's honesty.

### F7. Reuse `reconciliation_status` instead of a parallel vocabulary
`project_risk` already exposes `reconciliation_status: "INTERNAL_AUTHORITATIVE"`.
Spec §7 defines a new report vocabulary without referencing it.
- **Recommendation:** extend the existing field (`BROKER_RECONCILED` /
  `RECONCILIATION_HOLD` / `MISMATCH` in `BROKER_PAPER` mode) and add a new event
  type to the closed `EVENT_TYPES` tuple (e.g. `ReconciliationRecorded`) —
  adding to `EVENT_TYPES` is the established P0 pattern (9 types today).

### F8. Env-gate and docs gaps
- Spec §5.3 introduces five new env vars; §13's completion definition omits
  `.env.example` and `docs/providers/TRADIER_PAPER.md` env documentation as
  deliverables (docs/providers/ is the established provider-doc home — no
  TRADIER file exists yet).
- `DisabledPaperExecutionProvider` is gated on a **legacy `EXECUTION_ENABLE=1`**
  gate that is distinct from both `IMP_PAPER_EXECUTION` and the proposed
  `IMP_BROKER_PAPER_EXECUTION`. P4 should reconcile/deprecate `EXECUTION_ENABLE`
  or the composition slot will have two competing gates.

### F9. Minor hardening note on `IMP_LIVE_EXECUTION`
`P4-SAFE-002` restates "`IMP_LIVE_EXECUTION` never set in CI" — correct, but
`tools/validate.py::LIVE_GATES`/`ALL_LIVE_GATES` strips provider gates only;
`IMP_LIVE_EXECUTION` is not among them (fine today because LIVE-001 is blocked
and CI never sets it). Optional hardening: add `IMP_LIVE_EXECUTION` to
`ALL_LIVE_GATES` so CI child environments fail-closed even if it is ever set.

## 3. As-built checks (re-verify as each P4 component lands)

| Component | Check |
|---|---|
| `providers/adapters/tradier_paper.py` | gate triple verified before any request; sandbox endpoint enforced; `place_order` returns `ProviderResult` on the contract; cancel/fetch adapter-local; unmapped symbol fails closed |
| Broker payload models | canonical field names match `build_provider_metadata` exactly (F2); broker fills normalize into `apply_fill` shape (F1) |
| Idempotency | submission event precedes network call (V4/V5 primitives reused); N retries → 1 submission record (adversarial fixture); ambiguous outcome → fetch/reconciliation, no blind retry |
| Broker entry points | `submit_interactive_order` guard untouched (F3); new broker entry points distinct |
| `operating_modes.resolve_execution_authority` | `BROKER_PAPER → PAPER_ONLY` under `IMP_BROKER_PAPER_EXECUTION` (F4) |
| `project_execution_trace` | broker fields populated in BROKER_PAPER mode (F6) |
| `project_risk` | `reconciliation_status` extended + `ReconciliationRecorded` event type (F7) |
| `ProviderComposition` | Tradier adapter injected into `paper_execution` slot; `EXECUTION_ENABLE` reconciled (F5, F8) |

## 4. Residual / open questions

- **F1 fill authority** must be settled before 4A implementation — it changes the
  §8 architecture and every reconciliation assertion.
- Tradier wire specifics (endpoints, payloads, sandbox account model) are unknown
  until the sandbox is exercised; the spec correctly defers them to
  `docs/providers/TRADIER_PAPER.md` (V-consistent with how other providers
  documented their contracts).
- Whether the `paper` suite (`tests/platform`) or a new suite owns the P4 tests
  is a manifest question; adding a manifest suite is a governed edit requiring
  principal approval (spec §11 already flags this).

**Overall:** the spec's code-facing claims are accurate (12/12 verified). One
blocking design decision (F1 fill authority) and eight spec/implementation
follow-ups (F2–F9), all actionable before/while implementing 4A. No code or
governed subjects were mutated by this audit.
