# Live Mixed Screener — Continuation Ledger

**Updated:** 2026-08-24 (Composer 2.5 continuation session)

## Repository state

| Field | Value |
| --- | --- |
| Branch | `main` |
| HEAD (start) | `b89027a20274fc71a1dba8eb859c11f575510f97` |
| Initial dirty files | `README.md`, `evidence/ui1/*`, `ui/README.md`, untracked launcher scripts |
| Canonical repo path | `integrated-market-platform/` |

## Architectural decisions (frozen)

- Finviz Elite = discovery authority; Moomoo = first live L1 enrichment (`BASIC_QUOTE` only).
- Authoritative-per-field routing; snapshot never masquerades as live.
- Lanes: `MOMENTUM`, `SQUEEZE`, `CATALYST`, `SWING` (multi-lane allowed).
- Attention ranking is inspectable, not a buy score; `candidate_role: INVESTIGATE`, `execution_authority: NONE`.
- Transport: `GET /discover/mixed` (read-only poll) + `POST /discover/mixed/refresh` (single-flight Finviz + subscription reconcile).
- Consumer id `discover-live-screener`, cap from `IMP_DISCOVERY_LIVE_CANDIDATES` (default 12).

## Workstreams

| Stream | Status |
| --- | --- |
| Domain (mixed.py, lanes, ranking) | Complete on main |
| Moomoo enrichment (live_enrichment.py) | Complete on main |
| API/service (mixed_discovery_projections.py) | Complete + session/summary fields added this session |
| UI (/discover Mixed Live) | Complete + status banner/caveats this session |
| Finviz Elite auto-recovery | Complete on main (`d675e94`..`7830e6e`) |
| IBKR adapter for screener | Deferred (architecture-ready via enricher protocol) |

## Files modified this session

- `src/market_platform_foundation/market_sessions.py` (new)
- `src/market_platform_foundation/discovery/mixed.py` (evidence + caveats)
- `src/market_platform_foundation/ui_api/mixed_discovery_projections.py` (session, counts)
- `ui/src/components/DiscoverPage.tsx` (status banner, spread, caveats)
- `ui/src/components/DiscoverPage.test.tsx`
- `ui/src/styles/layout.css`
- `tests/platform/test_mixed_discovery.py`
- `tests/platform/test_market_sessions.py` (new)

## Milestones

- [x] Checkpoint A — Repository recovery
- [x] Checkpoint B — Spec frozen (`docs/superpowers/specs/2026-08-24-mixed-live-screener-design.md`)
- [x] Checkpoint C — Shared contracts integrated
- [x] Checkpoint D — Discovery + ranking integrated
- [x] Checkpoint E — Moomoo enrichment integrated
- [x] Checkpoint F — Backend live service working
- [x] Checkpoint G — Frontend working
- [ ] Checkpoint H — Real-data/browser validation (blocked: no `.venv`, OpenD not probed)

## Validations run

| Command | Result |
| --- | --- |
| `py -3.13 -m unittest tests.platform.test_mixed_discovery tests.platform.test_market_sessions` | PASS (31 tests) |
| `npm test DiscoverPage` (ui/) | PASS (5 tests) |
| `tools/validate.py changed` | SKIPPED (no `.venv`) |
| Browser QA | SKIPPED (no `.venv` / platform not started) |

## Review fixes applied this session

- Subscription reconcile now uses live-enriched ranks (not discovery-only preliminary).
- Rank anchor freezes attention ordering between Finviz refreshes (polls update quotes only).
- `NOT_SUBSCRIBED` / `QUOTA_EXHAUSTED` surface as `UNAVAILABLE`, not `SNAPSHOT`.
- Symbol row no longer deep-links to workspace; **Open Workspace** is the promotion path.
- UI shows market session, subscription summary, screen degradation, and market `reason` codes.
- `POST /discover/mixed/release` drops `discover-live-screener` subscriptions on page leave.
- Cached-only Finviz bootstrap (all `LATEST_SAVED_CAPTURE`) reports `HEALTHY`, not `DEGRADED`.

## Blockers

| Blocker | Type | Impact |
| --- | --- | --- |
| No `.venv` in repo | ENVIRONMENT | `START_PLATFORM.cmd` fails; live Finviz/Moomoo probe deferred |
| Finviz Elite credentials | EXTERNAL (if unset) | Live discovery uses saved captures + degraded mode |
| Moomoo OpenD at 127.0.0.1:11111 | PROVIDER (if down) | Live quotes show SNAPSHOT/UNAVAILABLE; page still works |

## Finviz Elite status

`CODE_READY_NEEDS_USER_AUTH` — automatic key reload + login recovery implemented; live verification requires configured `FINVIZ_API_KEY` or stored login in `.private/providers.env`.

## Immediate next actions

1. Create `.venv` (Python 3.11+) and run `tools/validate.py changed`.
2. Start platform (`START_PLATFORM.cmd`) and browser QA `/discover`.
3. Probe Moomoo OpenD with `IMP_MOOMOO_LIVE=1` when available.
4. IBKR enrichment adapter (follow-on).
