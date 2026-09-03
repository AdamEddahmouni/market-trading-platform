# Research Hypothesis & Experiment System (BUILD 17)

BUILD 17 converts measured forward evidence into falsifiable research hypotheses and
pre-registered experiment specifications. It does not train candidates, validate them on
holdouts, or modify production.

## Epistemic ladder

```text
OBSERVATION (ResearchFindingV1)
    ↓
HYPOTHESIS (ResearchHypothesisV1)
    ↓
EXPERIMENT PLAN (ExperimentManifestV1)
    ↓
BUILD 18 candidate generation
    ↓
BUILD 19 independent validation
    ↓
BUILD 20 promotion
```

Observation ≠ explanation ≠ hypothesis ≠ evidence ≠ validated strategy.

## Market vs research hypothesis

- `HypothesisV1` (BUILD 13): market-state mechanism hypothesis (e.g. squeeze-like dynamics).
- `ResearchHypothesisV1` (BUILD 17): falsifiable claim about a potential system improvement.

## ResearchFindingV1

Evidence-linked observation from BUILD 16 `EvaluationReportV1`. References exact report ID,
evaluation spec ID, cohort fingerprint, slice/comparison keys, metric observations, and sample
counts. Findings are observations, not causal explanations.

Automated extraction uses explicit `FindingExtractionPolicy` thresholds over predefined BUILD 16
slice results — no combinatorial slice mining.

## ResearchHypothesisV1

Requires:

- source finding references
- explicit treatment and control (`ComponentMutationSpec`)
- primary metric and expected direction
- falsification criterion
- `ResearchKnowledgeFootprint` (development knowledge for BUILD 19)

Treatment must differ from control. No `PROVEN` / `TRUE` status.

## ExperimentManifestV1

Pre-registered experiment plan binding:

- treatment/control specs
- `DataSpecification` (target, horizon, mode, decision range)
- frozen `MetricPlan` (one primary metric)
- success and falsification criteria
- `ValidationRequirements` (walk-forward, purge, embargo, locked holdout placeholders)
- optional bounded `SearchSpaceSpec`, `SeedPolicy`, complexity and resource budgets
- allowed/forbidden mutation surfaces

Experiment identity excludes results and lifecycle status.

## Contamination principle

Evidence inspected to create a hypothesis is development knowledge. `ResearchKnowledgeFootprint`
preserves report IDs, cohort fingerprints, and time ranges for BUILD 19 holdout contamination
ledger enforcement.

## Persistence

Immutable collections (no TTL):

- `research_findings`
- `research_hypotheses`
- `experiment_manifests`
- `research_lifecycle_events`

## Handoffs

- **BUILD 18**: consumes `ExperimentManifestV1` mutation/search/resource boundaries for candidate
  generation only.
- **BUILD 19**: consumes manifests, footprints, and validation requirements for temporal validation.
- **BUILD 20**: receives independently validated results, not raw hypotheses.

## No training

`ExperimentManifestV1` ≠ trained candidate. BUILD 17 registers plans only.

See also: `EVALUATION_DIAGNOSTICS_V1.md`, `PREDICTION_LEDGER_OUTCOME_SETTLEMENT_V1.md`.
