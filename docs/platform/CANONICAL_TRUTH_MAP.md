# IMP canonical truth map

| Field | Value |
|---|---|
| Document ID | `IMP-TRUTH-MAP` |
| Classification | `CANONICAL` |
| Primary Truth Class | `CURRENT_CANONICAL_TRUTH` |
| Canonical Subject | Topic-to-authority routing and conflict disposition |
| Establishing Milestone | `IMP-REBASE-01` |
| Version | `1.1` |
| Last Verified | `2026-08-27` |
| Supersedes | No single current whole-program authority index |
| Superseded By | None |

There is no global “newest file wins” hierarchy. Identify the subject and time
scope first, then use the source that controls that scope.

## Scoped precedence

| Question | Controlling authority |
|---|---|
| Current behavior, policy, gate, registry, or validation selection | The current executable schema, code, policy, gate, registry, or manifest for the behavior it directly controls; then an accepted hashed binding where applicable |
| Current program explanation, maturity, navigation, or future ownership | The `docs/platform/` document for its declared subject, constrained by executable truth and accepted evidence |
| What happened or was accepted at a past cutoff | The immutable accepted BUILD, Phase, closure, or EVIDENCE artifact and its hashes |
| Approved future direction | This roadmap plus the accepted design/spec for that future subject; it grants no runtime authority |
| Procedure in a named environment | The current scoped runbook, constrained by executable gates and policy |

## Authority routing

Mutable values must be read from the linked source. This map intentionally does
not copy thresholds, limits, policy IDs, provider states, model identities,
validation counts, or gate logic.

| Subject | Current source | Source type | Truth class | Controlling scope | Conflict |
|---|---|---|---|---|---|
| Program documentation index | [Platform documentation](README.md) | Canonical explanation | `CURRENT_CANONICAL_TRUTH` | Reading order and navigation | None |
| Whole-program composition | [Master Architecture](MASTER_ARCHITECTURE.md) | Canonical explanation | `CURRENT_CANONICAL_TRUTH` | Program shape and architectural relationships | None |
| Current program state | [Program Status](PROGRAM_STATUS.md) | Canonical explanation | `CURRENT_CANONICAL_TRUTH` | Material milestone, family, authority, and limitation state | None |
| Post-core planning | [Master Roadmap](MASTER_ROADMAP.md) | Canonical roadmap | `APPROVED_FUTURE_DESIGN` | Milestone boundaries and dependencies only | None |
| Documentation governance | [Documentation Standard](DOCUMENTATION_STANDARD.md) | Canonical explanation | `CURRENT_CANONICAL_TRUTH` | Prospective documentation rules | None |
| Run, attempt, and reproducibility semantics | [Reproducibility and Run Standard](REPRODUCIBILITY_AND_RUN_STANDARD.md) | Canonical explanation | `CURRENT_CANONICAL_TRUTH` | Run identity, attempts, outcomes, dispositions, artifacts, attribution, and reproducibility classes | None |
| Observability semantics | [Observability Standard](OBSERVABILITY_STANDARD.md) | Canonical explanation | `CURRENT_CANONICAL_TRUTH` | Logs, audit records, events, metrics, traces, correlation, clocks, and latency stages | None |
| Test and evaluation semantics | [Test and Evaluation Standard](TEST_AND_EVALUATION_STANDARD.md) | Canonical explanation | `CURRENT_CANONICAL_TRUTH` | Validation, benchmarks, backtest, replay, simulation, provider smoke, model evaluation, experiment, and research | None |
| REBASE-02 acceptance | [REBASE-02 package](../../artifacts/imp-rebase/REBASE02/README.md) | Accepted audit evidence | `HISTORICAL_TRUTH` | Standards implementation at acceptance cutoff | None |
| Foundation design binding | [`canonical-authority.json`](../../manifests/phase0/canonical-authority.json) and [authority enforcement](../../src/market_platform_foundation/authority.py) | Manifest and code | `CURRENT_CANONICAL_TRUTH` | Exact-hash Foundation specification scope only | None |
| Repository validation selection | [validation manifest](../../tools/validation_manifest.json), [manifest loader](../../tools/validation_manifest.py), [validator](../../tools/validate.py), and [CI workflow](../../.github/workflows/imp-validate.yml) | Manifest, code, workflow | `CURRENT_CANONICAL_TRUTH` | Suites, domains, invalidators, selection, and result semantics | None |
| BUILD35 acceptance | [BUILD35 report](../../artifacts/full-system-acceptance/BUILD35_FULL_ACCEPTANCE_REPORT.json), [authority map](../../artifacts/full-system-acceptance/BUILD35_AUTHORITY_MAP.json), and hashes in that package | Immutable acceptance evidence | `HISTORICAL_TRUTH` | Recorded BUILD35 candidate and cutoff | None |
| Repository closure | [Closure audit](../engineering/POST_BUILD35_REPOSITORY_CLOSURE_AUDIT.md) and [classification](../../artifacts/repository-closure/POST_BUILD35_SUBSYSTEM_CLASSIFICATION.json) | Accepted audit and inventory | `HISTORICAL_TRUTH` | Recorded closure source and classifications | None |
| REBASE-00 findings | [REBASE-00 package](../../artifacts/imp-rebase/REBASE00/README.md) | Accepted audit evidence | `HISTORICAL_TRUTH` | Repository truth at the audit cutoff | Superseded only as current whole-program explanation by this layer |
| EVIDENCE sufficiency | [EVIDENCE-01 documentation](../engineering/EVIDENCE_01_LONGER_FORWARD_QUALIFICATION.md), implementation under [`evidence01/`](../../src/market_platform_foundation/intelligence/forward_qualification/evidence01), and frozen artifact package | Code, frozen policy, historical/current evidence | `HISTORICAL_TRUTH` / `CURRENT_CANONICAL_TRUTH` | Sufficiency assessment only; no execution authority | None |
| EVIDENCE campaign | [EVIDENCE-01A documentation](../engineering/EVIDENCE_01A_REAL_FORWARD_OBSERVATION_CAMPAIGN.md) and campaign implementation | Code and campaign records | `HISTORICAL_TRUTH` / `CURRENT_CANONICAL_TRUTH` | Origin, persistence, session, checkpoint, and campaign lifecycle | None |
| EVIDENCE runtime | [EVIDENCE-01B documentation](../engineering/EVIDENCE_01B_REAL_PROVIDER_RUNTIME_OPERATIONALIZATION.md) and [`evidence01b/`](../../src/market_platform_foundation/intelligence/forward_qualification/evidence01b) | Code and frozen runtime records | `CURRENT_CANONICAL_TRUTH` | Provider bridge, configuration identity, continuity, settlement, and operational controls | None |
| Temporal event semantics | [`EventV1`](../../src/market_platform_foundation/intelligence/contracts/event.py), temporal contracts, and normalization code | Code and contracts | `CURRENT_CANONICAL_TRUTH` | Event, availability, decision-time, and point-in-time behavior | None |
| Provenance | [`ProviderProvenance`](../../src/market_platform_foundation/intelligence/normalization/models.py) and provider envelopes | Code and contracts | `CURRENT_CANONICAL_TRUTH` | Source lineage and normalized provider context | None |
| Quality | [shared quality models](../../src/market_platform_foundation/intelligence/quality/models.py) plus domain taxonomies | Code and contracts | `CURRENT_CANONICAL_TRUTH` | Quality assessment within each defined domain | None |
| Provider capability and admission | [provider contracts](../../src/market_platform_foundation/providers/contracts.py), [capability registry](../../src/market_platform_foundation/market_data/capability_registry.py), adapters, probes, and provider-specific evidence | Fragmented executable authorities | `CURRENT_CANONICAL_TRUTH` | Support, entitlement, runtime evidence, and admission within each provider scope | Provider-domain registries remain authoritative in their scopes; OF-03 indexes operating capabilities, not provider admission |
| Governed operating capabilities, SOPs, and workflows | [`config/of03/`](../../config/of03) and [`of03/`](../../src/market_platform_foundation/of03) | Versioned JSON plus typed loader | `CURRENT_CANONICAL_TRUTH` | Registry identity, versions, bindings, policy metadata, and snapshot hash | Registration is not authorization; OF-01 remains execution history |
| Prediction record | [`PredictionLedgerEntryV1`](../../src/market_platform_foundation/intelligence/contracts/prediction_ledger.py) and persistence consumers | Code and contracts | `CURRENT_CANONICAL_TRUTH` | Immutable prediction lineage | None |
| Outcome settlement | [`OutcomeSettlementService`](../../src/market_platform_foundation/intelligence/outcomes/service.py) and frozen settlement policy | Code and policy | `CURRENT_CANONICAL_TRUTH` | Outcome maturity, policy matching, and settlement | None |
| Risk | [risk decision](../../src/market_platform_foundation/risk/decision.py), [risk policy](../../src/market_platform_foundation/risk/policy.py), and current scoped risk implementations | Code and policy | `CURRENT_CANONICAL_TRUTH` | May permit or block within risk scope; does not submit orders | None |
| Execution state | [intelligence execution engine](../../src/market_platform_foundation/intelligence/execution/engine.py), execution contracts, and paper paths | Code and contracts | `CURRENT_CANONICAL_TRUTH` | Candidate sizing and execution state within the selected guarded mode | None |
| Live safety gate | [live-safety gate](../../src/market_platform_foundation/intelligence/live_execution_safety/gate.py) | Code and policy | `CURRENT_CANONICAL_TRUTH` | Prerequisite safety gate; never an order | None |
| Human live-session authorization | [live-canary authorization](../../src/market_platform_foundation/intelligence/live_canary/authorization.py) | Code and records | `CURRENT_CANONICAL_TRUTH` | Bounded session permission within policy | None |
| Per-order confirmation | [live-canary confirmation](../../src/market_platform_foundation/intelligence/live_canary/confirmation.py) | Code and records | `CURRENT_CANONICAL_TRUTH` | One reviewed candidate action | None |
| Broker external reality | Broker transport response when an authorized transport exists; current live canary uses [`MockBrokerTransport`](../../src/market_platform_foundation/intelligence/live_canary/submission.py) | External system plus transport code | `CURRENT_CANONICAL_TRUTH` | Acceptance, rejection, and fill | Production live transport is absent |
| Reconciliation | [portfolio reconciliation](../../src/market_platform_foundation/portfolio/reconciliation.py), [platform reconciliation](../../src/market_platform_foundation/platform/reconciliation/engine.py), and [live-canary reconciliation](../../src/market_platform_foundation/intelligence/live_canary/reconciliation.py) | Code and records | `CURRENT_CANONICAL_TRUTH` | Incorporates external state into canonical state within each path | None |
| Release governance | [release-governance implementation](../../src/market_platform_foundation/intelligence/live_canary/release_governance) and BUILD35 historical policy/evidence | Current code plus historical evidence | `HISTORICAL_TRUTH` / `CURRENT_CANONICAL_TRUTH` | Release eligibility and approval; not session or order authorization | None |
| Future OF/RT/XA/AI/Narrative work | [Master Roadmap](MASTER_ROADMAP.md) and accepted REBASE-02 standards | Canonical roadmap and standards | `CURRENT_CANONICAL_TRUTH` / `APPROVED_FUTURE_DESIGN` | Requirements, ownership, and semantic contracts | None |

## Conflict handling

A current canonical explanation that conflicts with executable behavior is
wrong; it does not override the implementation. A same-scope safety or authority
conflict blocks acceptance. A non-safety conflict may remain only when this map
marks it `UNRESOLVED`, states the consequence, and names a future owning
milestone. No such unresolved conflict is accepted at REBASE-01.

Historical and current authority are time-scoped. Current
[Master Architecture](MASTER_ARCHITECTURE.md) cannot rewrite BUILD35 history,
and BUILD35 cannot control current program architecture solely because its
artifact is immutable. Recency alone cannot override a frozen policy.
