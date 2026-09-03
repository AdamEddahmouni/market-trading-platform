# Transparent Candidate Evaluation Contract

Phase 3A evaluates one explicit candidate snapshot at one explicit UTC `as_of`. A frozen
request names the symbol, asset class, policy, enabled rules, provider scope, observations,
metrics, readiness results, and any detected default substitutions.

Every rule returns exactly one of `PASS`, `FAIL`, `UNKNOWN`, `CONFLICTED`,
`INSUFFICIENT_DATA`, or `NOT_APPLICABLE`. Missing evidence never defaults to `FAIL`; numeric
zero remains known where valid. Results retain threshold, observed value/unit, supporting
observation/metric/readiness IDs, quality, diagnostics, and deterministic ID.

Candidate aggregation sorts independent rule results and emits count-only summaries for all
four categories. It has no aggregate state. Identity includes evaluation/policy versions,
candidate boundary, enabled rules, rule-result IDs, and supporting IDs. Canonical JSON uses
stable key/list ordering and exact Decimal strings. Wall clock, insertion order, paths,
credentials, and prose are excluded.

The CLI is local-only:

```powershell
.\.venv\Scripts\python.exe -m squeeze_core build-candidate-evaluation `
  --policy tests\fixtures\evaluation\phase_3a_default_policy.json `
  --evidence tests\fixtures\evaluation\phase_3a_synthetic_evidence.jsonl `
  --symbol TESTA --as-of 2026-07-17T14:23:58Z `
  --provider provider-a --output build\evaluation\candidate-evaluation.json
```

Evidence JSONL uses typed local records: `observation`, `metric`, `readiness`, or
`default_substitution`. The command performs no network, database, credential, GUI, alert,
order, or trading operation.

## Phase 3B reuse

Phase 3B may deserialize a frozen result or construct this exact request from an explicit local request artifact and invoke the unchanged evaluator. Research outcome data is never included in the request, and the Phase 3B detection result preserves the supporting Phase 3A rule-result IDs without modifying them.
