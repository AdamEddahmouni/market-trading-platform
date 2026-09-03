# ADR 0055: Earliest boundary selection is outcome-blind

## Decision

The selected boundary is the minimum `(evaluation_as_of, case_id)` per symbol. Outcome and return fields are forbidden selection inputs.

## Consequences

Selection is reproducible under input reordering and outcome mutation, and favorable outcomes cannot influence cohort construction.
