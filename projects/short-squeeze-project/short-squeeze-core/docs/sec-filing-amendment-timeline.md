# SEC Filing Amendment Timeline

The synthetic `TESTA` fixture separates reporting period, SEC acceptance, and local receipt.

| Event | UTC time |
|---|---|
| Period of report | 2026-01-15 |
| Original accepted | 2026-01-20 14:30 |
| Original received | 2026-01-20 15:00 |
| Amendment accepted | 2026-01-27 14:30 |
| Amendment received | 2026-01-28 15:00 |

Before acceptance no SEC observation is eligible. After acceptance but before receipt it remains unavailable locally. After original receipt the original is eligible. Before amendment receipt only the original remains eligible. After amendment receipt both immutable observations and their relationship are present. Rebuilding an earlier bundle remains byte-identical.

- Timeline: `tests/fixtures/evidence/sec_filing_availability_timeline.json`
- Mixed JSONL: `tests/fixtures/evidence/normalized_phase_1e_point_in_time.jsonl`
- Hash metadata: `tests/fixtures/evidence/expected_phase_1e_bundle_metadata.json`
