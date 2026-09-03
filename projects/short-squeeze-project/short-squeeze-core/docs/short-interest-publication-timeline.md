# Short-Interest Publication Timeline

The deterministic `TESTA` fixture separates the described settlement period from operational availability.

| Event | UTC time |
|---|---|
| Settlement period | 2026-01-15 |
| Original published | 2026-01-22 19:00 |
| Original received | 2026-01-22 20:00 |
| Correction published | 2026-01-29 19:00 |
| Correction received | 2026-01-30 15:00 |

Bundles are generated at five explicit times:

| Bundle | Result |
|---|---|
| Before publication | Finviz and IBKR evidence are eligible; published short interest is missing/not yet published |
| After publication, before receipt | Published short interest remains excluded because the local system has not received it |
| After original receipt | Original published short interest is eligible |
| After correction publication, before correction receipt | Original remains eligible; correction remains excluded |
| After correction receipt | Original and correction are both preserved; one deterministic supersession relationship is present |

The earlier bundle hash and bytes are identical when rebuilt after the correction exists because selection uses historical publication and receipt metadata.

- Fixture: `tests/fixtures/evidence/short_interest_publication_timeline.json`
- Mixed JSONL: `tests/fixtures/evidence/normalized_phase_1d_point_in_time.jsonl`
- Expected hashes: `tests/fixtures/evidence/expected_phase_1d_bundle_metadata.json`
