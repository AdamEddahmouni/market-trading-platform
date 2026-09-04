# Gaps, Dependencies, and Proposed Sequence

## Architecture gap matrix

| Future capability | Reality | Reusable foundation | Missing primitive |
|---|---|---|---|
| Canonical program architecture | `ABSENT` | Foundation authority, BUILD35 map, this audit | Accepted precedence/status/architecture layer |
| Documentation governance | `PARTIAL` | Strong local docs/artifacts | Lifecycle metadata, owner, supersession index, generated refs |
| Universal Run Ledger | `PARTIAL` | `RunManifestV1`, hashes/manifests, ledgers | Append-only global envelope/index and retry/disposition model |
| Operating Fabric | `PARTIAL` | schedulers/orchestrators/pipelines/runbooks/incidents | Common operation/workflow lifecycle and registry |
| Observability/tracing | `PARTIAL` | BUILD32 telemetry, feed metrics, correlation IDs | Program schema and causal end-to-end trace |
| Global capability registry | `PARTIAL` | `MarketCapability`, probes, provider docs | Current joined registry with freshness/evidence/admission |
| Cross-asset kernel | `PARTIAL` | events/provenance/quality + FRED/CFTC/EIA/participant | Instrument/release/relationship extensions and admitted verticals |
| Real-time Opportunity Fabric | `PARTIAL` | callback path, state, features, routing, opportunity engine | durable state/trace/SLO and measured incremental computation plan |
| Narrative/motive | `PARTIAL` | market-context, participant, hypotheses | canonical uncertain motive/thesis/credibility model |
| AI/Agent operating model | `PARTIAL` | read-only assistant and versioned fixture LLM | run attribution, prompt/tool registry, approvals, evaluation |
| Production live broker runtime | `ABSENT` | paper adapters and live safety gates | authorized real transport and operational qualification |
| Global debt/problem registry | `ABSENT` | distributed limitation registers | owner/severity/dependency/disposition/closure evidence |

## Dependency graph

```text
REBASE-01 canonical truth + terminology + doc lifecycle
  -> REBASE-02 reproducibility/operation/observability standards
      -> OF-01 append-only Run Ledger + artifact index
          -> OF-02 validation/provider/evidence adapters
              -> OF-03 workflow registry + SOP/incident/debt indexes
          -> RT-01 end-to-end trace schema + benchmark harness
              -> RT-02 measured state/feature optimization
                  -> RT-03 event-bus or native hot-path decision (only if justified)
          -> XA-01 cross-asset kernel extensions + source template
              -> XA-02 first admitted rates/source vertical
                  -> specialized rates/commodities/FX/institutional branches
          -> AI-01 attributable read-only AI runs
              -> AI-02 workflow/tool registry and evaluation
```

The Run Ledger precedes universal workflows because existing workflows are heterogeneous but all need attribution. Latency tracing precedes event-bus changes because current bottlenecks are unknown. The workflow registry precedes a skill registry because there is only one bounded assistant family and no demonstrated universal skill lifecycle. Cross-asset design can proceed in parallel after standards, but admitted implementation should emit ledgered runs from its first source.

## Proposed milestones

### IMP-REBASE-01 — canonical program truth

Create and accept only the canonical documentation layer:

- current `PROGRAM_STATUS`, concise `ARCHITECTURE`, `AUTHORITY_MODEL`, data/epistemic model, glossary, and documentation standard;
- precedence/supersession/history indexes pointing to executable and immutable sources;
- generated-reference rules for policies, capabilities, models, tests, and hashes;
- repair root README/roadmap status only after the new authorities are accepted;
- no runtime, provider, policy, schema, EVIDENCE, risk, or execution changes.

### IMP-REBASE-02 — standards and contracts design

Specify reproducibility, operation taxonomy, run status/attempt semantics, artifact linkage, retention/redaction, observability, testing/evaluation, and development workflow. Reconcile with `RunManifestV1` and existing ledgers; do not yet centralize all workflows.

### IMP-OF-01 — append-only run/artifact ledger

Implement the minimal durable ledger and generated index. First adapter: validation, because it is ubiquitous, deterministic, and currently loses source/attempt context.

### IMP-OF-02 — operation adapters

Add provider smoke, replay/research, model train/inference, and EVIDENCE reference adapters. Reference frozen campaign records; do not rewrite them.

### IMP-RT-01 — end-to-end instrumentation

Define trace stages and benchmark harness; instrument the Moomoo observational/UI research path without changing admission or execution semantics. Establish SLO baselines before architecture optimization.

### IMP-XA-01 — cross-asset kernel

Define instrument/release/revision/calendar/relationship extensions and a source-admission template. Select a bounded U.S.-rates/FRED vertical as the reference, explicitly separating macro context from tradable bond data.

### IMP-OF-03 — workflow/control registry

Register existing schedulers, pipelines, campaigns, runbooks, incidents, capabilities, and debt with owners and lifecycle. Add retry/compensation only where operation semantics justify it.

### IMP-AI-01 — attributable AI research

Version/hash prompts and evidence packs, bind assistant/fixture-label generation to runs, add claim-citation validation and evaluation. Retain read-only/no-execution authority.

### Later branches

- `IMP-XA-RATES-*`, `IMP-XA-COMMODITIES-*`, `IMP-XA-FX-*`, `IMP-XA-INSTITUTIONAL-*` after XA-01 and OF-01.
- `IMP-RT-02` incremental/state optimization after RT-01; `IMP-RT-03` event bus/native path only after measured need.
- `IMP-NARRATIVE-01` motive/thesis/credibility ontology after XA-01 identity/event relationships and AI-01 attribution.
- `IMP-AI-02` governed workflows/tools/skills after OF-03.
- Any real live broker milestone remains a separate safety/qualification program and must not be inferred from re-baselining.

## Explicit do-not-touch list

- EVIDENCE-01 sufficiency policy, EVIDENCE-01A campaign semantics, EVIDENCE-01B configuration/settlement semantics, and existing observation/session/checkpoint records.
- Prediction ledger and outcome settlement contracts/policies.
- Risk, opportunity, paper execution, live gate, authorization, confirmation, reconciliation, kill-switch, deployment, and release authorities.
- Provider entitlements, adapters, admission policies, model behavior, datasets, feature schemas, test manifest, and validation semantics.
- Historical BUILD/Phase/EVIDENCE artifacts, hashes, reports, known-limitations registers, and prior validation reports.
- Production live transport work, autonomous execution, automatic broker failover, and any shortcut from forecast/LLM/release to order submission.
