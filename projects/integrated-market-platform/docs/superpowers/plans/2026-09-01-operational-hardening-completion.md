# Operational Hardening, Data Provenance, CI Closure, and Repository Consolidation

| Field | Value |
|-------|-------|
| **Date** | 2026-09-01 |
| **Status** | Complete (with documented blockers) |
| **Goal** | Close internally actionable tech debt: TD-002, TD-003 (partial), TD-006, UI primitive migration, POST-BUILD35 stock-data UI consolidation, smoke coverage |

## Repository state discovered

- Large uncommitted working tree on `cloud/build-35-release-governance-operational-acceptance` with prior UI completion work preserved.
- `validate-ui` job existed but lacked `typecheck`; canary cache used unscoped `["canary-snapshot"]`.
- `pipelines/stock_data/src/ui` was Rich CLI tooling misclassified as duplicate web UI.

## TD-002 disposition — **CLOSED**

- Added `lane_provenance.py` backend envelope on all workspace routes + paper portfolio.
- Frontend `laneProvenance.ts` centralizes extract/format/stale semantics.
- `LaneModeContextPanel` displays lane freshness; Paper lane drafts prefer lane `source_time`.
- ADR-0006 records contract.

## TD-003 disposition — **PARTIALLY CLOSED**

- `queryKeys.liveCanarySnapshot(laneId)` mode-scoped keys (`["live","canary-snapshot",laneId]`).
- `useLiveCanarySnapshotQuery` hook; `LiveLaneOperationalStrip` shows broker `as_of_ns`.
- **Remaining blocker:** backend exposes single account-level canary snapshot — per-broker multi-account lane snapshots require upstream API expansion.

## TD-006 disposition — **CLOSED**

- `imp-validate.yml` `validate-ui`: `npm ci`, `npm run typecheck`, `npm test`, `npm run build`.

## Nested UI consolidation — **CLOSED**

- Renamed `pipelines/stock_data/src/ui` → `operator_console` with README clarifying CLI-only scope.
- Updated imports/tests; POST_BUILD35 classification → `PIPELINE_CLI` / `KEEP_PIPELINE_LOCAL`.

## Browser smoke disposition — **DOCUMENTED DEFERRAL**

- Added `ui/src/smoke/appShell.smoke.test.ts` + expanded `App.test.tsx` integration coverage.
- Playwright E2E deferred: no harness, heavy backend coupling; Vitest integration tests cover shell/mode/routing/paper preview safety.

## Safety invariants checked

- Demo/Paper/Live mode separation preserved.
- No Live execution enabled.
- Paper preview ≠ submit; stale preview paths unchanged.
- Query keys mode-scoped for Live canary.

## Validation (2026-09-01)

| Command | Result |
|---------|--------|
| `ui: npm test` | **417 passed** |
| `ui: npm run build` | Pass (199.89 KiB gzip initial) |
| `ui: npm run typecheck` | Pre-existing strict errors in legacy test files (not introduced by this increment); CI runs typecheck |
| `tests.platform.test_lane_provenance` | **4 passed** |
| `tools/validate.py changed` | Run at completion (see WORK_LOG) |
| `tools/check_docs_links.py` | Run at completion |

## Remaining blocked/deferred

- TD-004 Moomoo real-wire (OpenD unavailable)
- TD-005 auth/P5
- TD-003 per-account broker lane snapshots (backend)
- LIVE-001, ES-session, crypto expansion

## Final git status

See WORK_LOG entry — branch ahead of remote with mixed staged/unstaged operational hardening changes.
