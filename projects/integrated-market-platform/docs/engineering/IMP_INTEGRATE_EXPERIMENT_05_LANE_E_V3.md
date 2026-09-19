# IMP-INTEGRATE-AND-EXPERIMENT-05 — Lane E v3 findings

Lane E synthesizes **bounded historical observations** from the executed OpenD fill-economics v3 pack and documents **intelligence benchmark deferral** without re-running Smoke10 or mutating v3/v2 receipts.

## Authority

- Simulator findings: `BOUNDED_HISTORICAL_OBSERVATION` / `HISTORICAL_DEVELOPMENT` as marked per row
- Intelligence findings: `BENCHMARK` observation only; not production readiness

## Machine-readable artifacts

| Artifact | Path |
|----------|------|
| Findings registry | `evidence/historical-research/imp-integrate-experiment-05-lane-e-v3-findings/findings_registry_v1.json` |
| Hypothesis queue | `evidence/historical-research/imp-integrate-experiment-05-lane-e-v3-findings/hypothesis_queue_v1.json` |
| Synthesis receipt | `evidence/historical-research/imp-integrate-experiment-05-lane-e-v3-findings/lane_e_v3_synthesis_receipt.json` |

## Source run (read-only)

| Item | Value |
|------|-------|
| Merge on `main` | [#273](https://github.com/AdamEddahmouni/market-trading-platform/pull/273) `a8dc0a65` — lane tip `436a0ed7` |
| `EXPERIMENT_HASH` | `81EFC1B1E2650010962F81F5B58B7E614E1AC1C2232E7862890CBB37BF5F3F61` |
| `pack_run_id` | `C3DE72960BAC86F9E743E14B9DBC2BF1` |
| Prior immutable v2 hash | `E8C9ADB9E295EBE913C254FCBBBDDC48A794D9FDE79492CB341138855A67C2A4` (unchanged) |

## Non-goals (observed)

- No v3 rerun, retune, or receipt rewrite
- `SMOKE10_EXECUTED=NO`
- No Item 9 collector mutation; no PR #222 / #267 merge

## Lane F status closure (docs)

Program-level invariants, v3 receipt pins, merge SHAs ([#271](https://github.com/AdamEddahmouni/market-trading-platform/pull/271)–[#274](https://github.com/AdamEddahmouni/market-trading-platform/pull/274)), and the recommended next increment are recorded in [PROGRAM_STATUS.md](../platform/PROGRAM_STATUS.md) § [IMP-OPEND-FILL-ECONOMICS-V3 — Lane F status/docs closure](../platform/PROGRAM_STATUS.md#imp-opend-fill-economics-v3--lane-f-statusdocs-closure). Lane F does not alter frozen JSON under `evidence/historical-research/imp-integrate-experiment-05-r3-opend-fill-economics-v3/`. **`SMOKE10_EXECUTED=NO`** remains in force after **#272** (`ccc41a7f`).

## Related

- Prior Lane E (validation-04): `IMP_RESEARCH_VALIDATION_04_LANE_E.md`
- Lane H synthesis: `IMP_INTEGRATE_EXPERIMENT_05_LANE_H.md`
- v3 execution doc: `IMP_INTEGRATE_EXPERIMENT_05_LANE_B_V3_FILL_ECONOMICS.md`
