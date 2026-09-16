---
name: imp-evidence-integrity
description: Audit IMP changes for prospective vs historical contamination, timestamp/freshness/provenance honesty, and evidence-class upgrades. Use when work touches FTEP, RTH, forward tests, Paper/Live labels, schedulers, or experimental artifacts.
---

# IMP evidence-integrity audit

Always-on invariants live in `.cursor/rules/imp-evidence-integrity.mdc`. This skill is the checklist when the diff might contaminate evidence.

## Classify every touched artifact

| Class | Meaning | Forbidden upgrade |
|---|---|---|
| historical | past market/state | do not treat as prospective |
| replay / backtest / simulation / shadow | non-prospective | do not label as forward-test or live |
| prospective forward test | locked before outcome | do not rewrite after seeing results |
| paper | internal simulation, fake money | do not treat as live or calibrated market truth |
| live | observational unless separately authorized | do not enable broker execution |

## Inspect

- timestamps: source/event vs receive/observation; no backdating
- freshness tokens: `STALE`, `UNAVAILABLE`, `NOT_OBSERVED`, `UNKNOWN`, `PENDING`
- provenance: provider, instrument, entitlement, PIT reconstructability
- run labels: failed observations remain failed; no substitute reruns under the same label
- schedulers/heartbeats: do not restart or retune to manufacture a passing window

## Output

```markdown
# Evidence audit
- classes touched: ...
- contamination risk: NONE / LOW / HIGH
- missing evidence (explicit tokens): ...
- allowed mutations: ...
- blocked mutations: ...
```

If risk is HIGH and the task did not explicitly authorize evidence mutation: **stop and report**. Do not “clean up” the record.
