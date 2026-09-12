## Summary

- Completes **max safe engineering** for FTEP v1 provider/data activation increment on `work/ftep-v1-activation`: Wave A/B artifacts, capability matrix + gap engine + campaign-readiness, calibration/comparator contracts, CG/news bridges, ES/news stack selection, goal audit (**24/26 MET**), and blocker report.
- Adds **PIT-A-001** unified research export manifest (`research/pit_export.py` + tests) and **OPERATOR_PROBE_RUNBOOK.md** for secret-free local probe refresh.
- **Does not** freeze FTEP-V1-001 manifest, enable Live trading, or claim qualifying prospective evidence.

## Test evidence

| Command | Result |
| --- | --- |
| `python tools/imp.py validate fast` | (see commit CI / local run) |
| `python -m unittest tests.research.test_pit_export -q` | PIT export determinism |
| Prior branch closure | `python tools/imp.py closure --skip-ui` — 4606 passed (wave-b) |

## Goal audit (section 28)

- **MET:** 24 (A–B, C–W, X, Y–Z)
- **PARTIAL:** 1 (**O** — observational live news ingress deferred)
- **qualifying_ftep_v1_001_activation:** `false`
- **engineering_complete:** `true`
- **update_goal_complete:** `false` (not 26/26 MET; owner/external blockers remain)

Authoritative JSON: `artifacts/ftep-v1-activation-goal-audit.json`

## Blockers (human / external only)

| ID | Owner | Action |
| --- | --- | --- |
| OWNER-OD-1-11 | Owner | [FTEP-V1_OWNER_DECISION_PACKET.md](../docs/engineering/FTEP-V1_OWNER_DECISION_PACKET.md) |
| OWNER-CALIBRATION-THRESHOLDS | Owner | Preregister numeric calibration gates |
| PROBE-MOOMOO / PROBE-FINVIZ / PROBE-G-A5 | Operator | [OPERATOR_PROBE_RUNBOOK.md](../docs/engineering/OPERATOR_PROBE_RUNBOOK.md) |
| EXT-MOOMOO-FUTURES-ENTITLEMENT | External | Account/plan verification |
| EXT-PREMIUM-WIRES / EXT-NEWSAPI-FINNHUB-PIT | External | Provider terms / PIT archive |

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
