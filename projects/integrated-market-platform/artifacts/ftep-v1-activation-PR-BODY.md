## Summary

- Completes **maximum safely achievable implementation** for the FTEP v1 provider/data activation increment on `work/ftep-v1-activation` (HEAD `08b3960`): Wave A/B artifacts, capability matrix + gap engine + campaign-readiness, calibration/comparator contracts, CG/news bridges, ES/news stack selection, PIT-A-001 export, operator probe runbook, and section-28 goal audit (**26/26 MET** for implementation scope).
- **Observational news ingress scaffold** (`437cd1c`): gate-gated `observational_ingress.py` + tests (criterion **O**); campaign forward-test auto-wire remains **DEFER-FTEP-ACT-04** (owner/governance).
- **Does not** freeze FTEP-V1-001 manifest, enable Live trading, run qualifying probes, or claim prospective FTEP-V1-001 empirical activation.

## Test evidence

| Command | Result |
| --- | --- |
| `python tools/imp.py validate fast` | 21 passed, 0 failures (goal audit receipt) |
| `python -m unittest tests.news.test_observational_ingress -q` | Observational ingress (with 3.11 + `PYTHONPATH=src`) |
| `python -m unittest tests.research.test_pit_export -q` | PIT export determinism |
| Prior branch closure | `python tools/imp.py closure --skip-ui` — 4606 passed (wave-b) |

## Goal audit (section 28)

- **MET:** 26 (A–Z) — all criteria **IMPLEMENTATION_COMPLETE**
- **qualifying_ftep_v1_001_activation:** `false` (out of scope for this goal)
- **implementation_objective_complete:** `true`
- **qualifying_activation_out_of_scope:** `true`
- **engineering_complete:** `true`
- **Residual (human/external only):** OWNER-OD-1-11, calibration numerics, local probes, manifest freeze, ACT-04 campaign wire

Authoritative JSON: `artifacts/ftep-v1-activation-goal-audit.json`

## Blockers (human / external only — not implementation gaps)

| ID | Owner | Action |
| --- | --- | --- |
| OWNER-OD-1-11 | Owner | [FTEP-V1_OWNER_DECISION_PACKET.md](../docs/engineering/FTEP-V1_OWNER_DECISION_PACKET.md) |
| OWNER-CALIBRATION-THRESHOLDS | Owner | Preregister numeric calibration gates |
| PROBE-MOOMOO / PROBE-FINVIZ / PROBE-G-A5 | Operator | [OPERATOR_PROBE_RUNBOOK.md](../docs/engineering/OPERATOR_PROBE_RUNBOOK.md) |
| EXT-MOOMOO-FUTURES-ENTITLEMENT | External | Account/plan verification |
| EXT-PREMIUM-WIRES / EXT-NEWSAPI-FINNHUB-PIT | External | Provider terms / PIT archive |
| DEFER-FTEP-ACT-04-OBS-INGRESS | Owner | Campaign-scale forward-test wiring when governance opens |

Details: [FTEP_V1_ACTIVATION_BLOCKER_REPORT.md](../docs/engineering/FTEP_V1_ACTIVATION_BLOCKER_REPORT.md)

## Safe operator sequence (post-merge)

1. Owner decisions + calibration thresholds
2. Operator probes → refresh `artifacts/wave-a-findings/capability-matrix-snapshot.json`
3. `python tools/imp.py providers campaign-readiness FTEP-V1-001 --json` (expect NOT_READY until gaps clear)
4. `python tools/forward_test/freeze_activation_manifest.py` only when manifest complete

## Out of scope / prohibited claims

- LIVE-001 remains blocked; no Live activation
- No manifest freeze in this PR
- No implication that FTEP-V1-001 is collecting qualifying forward evidence
