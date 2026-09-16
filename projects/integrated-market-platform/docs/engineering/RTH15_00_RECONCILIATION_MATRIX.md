# RTH15-00 reconciliation matrix

**Base:** `origin/main` `d06f1f4c1154913c561fc3c7c42aa46f452a2a15`  
**Branch / worktree:** `reconcile/rth15-00` / `.worktrees/reconcile-rth15-00`  
**Primary checkout:** `item7/natural-settlement` @ `c44231fa` — **not mutated**.

Inspected actual commits/diffs; branch names were not treated as sufficient.

| Lane / Branch | Purpose | Base / tip | Divergence vs `origin/main` | Important changes | Current relevance | Evidence sensitive? | Conflicts / overlap | Validation available | Disposition |
|---|---|---|---|---|---|---|---|---|---|
| `work/phase55b-lane-b-evidence-capture-context` (#196) | Optional capture-context sidecar | `ec93809e` | Unique sidecar; merge-base stale vs current OE | Sidecar + CLI + schema; must not mutate receipts | Unique software still missing on main | No (software metadata) | Overlaps FTEP docs only | Sidecar unit tests | `REIMPLEMENT_ON_CURRENT_MAIN` |
| `repair/ranked-summary-leak-audit-20260915` | Omit leak-shaped public DTO names | `ec105d16` | Mixed leak fix with stale WATCH 403 policy | Public `instrument_key` / `authority` omit | Leak 500 still real on main after #205/#208 | No | Conflicts with Live operator WATCH | Leak-audit + opportunity API tests | `CHERRY_PICK_SUBSET` / reimplement leak only |
| `cursor/ux-research-nav-dedupe-d1ba` (#123) | Drop duplicate Lab→Research nav | draft | Behind; Lab still duplicate on main | NavShell link | Still true | No | None | NavShell vitest | `REIMPLEMENT_ON_CURRENT_MAIN` |
| `cursor/ux-drop-top-opportunity-cards-d1ba` (#124) | Remove orphaned top cards | draft | Behind | Delete unused TSX; keep CSS used by radar | Orphan still on main | No | CSS shared with radar dense tags | UI tests | `REIMPLEMENT_ON_CURRENT_MAIN` |
| `cursor/ux-navshell-horizontal-cleanup-d1ba` (#126) | Dead horizontal NavShell CSS | draft | Behind | Drop unused layout prop/CSS | Dead CSS still present | No | None | UI tests | `REIMPLEMENT_ON_CURRENT_MAIN` |
| `cursor/ux-discover-investigate-only-d1ba` (#128) | Discover investigation-only boundary | draft | Behind; copy already partly on main | Badges/ARIA vs opportunity contract | Badges still missing | No | Discover routes already `/discover` | DiscoverPageSections vitest | `REIMPLEMENT_ON_CURRENT_MAIN` |
| `phase55b/lane-g-ui-test-hygiene` (#201) | TS unused-import hygiene | `159861f6` DRAFT | Mixed with deleting PREVIEW_STALE revalidation test | Unused imports vs stale-mapping deletion | Unused imports still true; stale test **must stay** | No | PREVIEW_STALE mapping lives on main | UI typecheck | `CHERRY_PICK_SUBSET` |
| `ui/operator-redesign-v2` | Graphite/lava operator shell | `5726238d` | **66 behind**; incomplete shell | Full redesign vs current Opportunity schema | Plan docs useful; shell too stale | No | Opportunity/API/provenance drift | Incomplete | `KEEP_ISOLATED` + recover plan docs only |
| `item7/natural-settlement` (#222) | Natural settlement after capture persist | `c44231fa` (ahead 3/behind 1) | Unique settlement software | Settlement after #218 persist | Awaiting governed acceptance | **Yes** | Dirty review artifacts in primary checkout | Isolated PR | `KEEP_ISOLATED_PENDING_EVIDENCE` |
| `repair/live-oe-cockpit-state-20260915` | Sep 15 live OE cockpit | `f194f2e8` ahead 5 / behind 12 | EventV1 admit, fixture as_of, ranked/ACK split | Precursor to #205/#208 | Main is the superior architecture | No (software) | Same files as #205/#208 | Superseded by #205/#208 | `SUPERSEDED_BY_MAIN` |
| `docs/post-215-program-status-sync` unique tip | P1 EventV1 admit fail-closed test | `fe6e84f7` | Duplicate of `eea65581` on main | Acceptance test | Already on main via #208 train | No | Same test module | On main | `SUPERSEDED_BY_MAIN` |
| `diagnosis/launcher-routing-20260915` + `repair/launcher-routing-from-main-20260915` | Launcher/Vite `/discover` | `9b0781c9` / `80792ea7` | Stale snapshot | Launcher Python/runtime | Reconstructed in #206/#211 | No | Same launcher files | On main | `SUPERSEDED_BY_MAIN` |
| `diagnosis/item7-upstream-20260915` | Item 7 upstream diagnosis | `823aad46` | Docs/drafts | Diagnosis notes | Historical truth | No (docs) | Item 7 software on other lanes | Docs only | `KEEP_AS_DIAGNOSTIC_EVIDENCE` then archive here |
| `diagnosis/item9-prospective-bar-20260915` + `review/item9-kline-diagnosis-20260915` | Item 9 kline/window | `0ce7a400` / `49ae216e` | Docs + later Item 9 software on main (#203) | Honest categories | Historical | Yes if code mutated receipts — **docs only recovered** | #203 kline window | Docs | `KEEP_AS_DIAGNOSTIC_EVIDENCE` then archive |
| `diagnosis/observability-latency-20260915` | Next-RTH hop clocks | `49529d64` | Unique catalog module | Read-only hop catalog | Unique; no production telemetry | No | hot_path_telemetry | Catalog unit test | `REIMPLEMENT_ON_CURRENT_MAIN` |
| `diagnosis/test-gap-audit-20260915` | Live-integration test-gap matrix | `145fee4f` | Docs | Gap matrix | Historical | No | Later tests on main | Docs | `KEEP_AS_DIAGNOSTIC_EVIDENCE` then archive |
| `diagnosis/rth-runbook-item7-provider-20260915` | P7/P8/P10 drafts | `134924c3` | Drafts | Runbook drafts | Historical | No | Current NEXT_RTH runbook | Docs | `KEEP_AS_DIAGNOSTIC_EVIDENCE` then archive |
| `review/live-oe-*` | P12/P13 falsification notes | several | Docs | Reviews | Historical | No | #205/#208 closed holes | Docs | `KEEP_AS_DIAGNOSTIC_EVIDENCE` then archive |
| Phase 2–5 / split / overnight / perf worktrees | Merged campaign leftovers | various | Remote often `gone` | Already merged or stale | Leftover worktrees | Varies | Do not re-merge | Historical | `SUPERSEDED_BY_MAIN` / retain worktrees |
| Intelligence Benchmark Protocol v1 | Blind Modes A–E | **not found** | No branch | — | Not integrable | N/A | — | Not executed | `DEFER` |
| `STAGE_2_APPLIED_AWAITING_NATURAL_CYCLE` | Heartbeat Day Discovery sentinel | **NONE OBSERVED** | No branch, artifact, or Windows task | — | Not present | Would be yes | Item 7 #222 is a different experiment | N/A | `NONE OBSERVED` — do not invent |
| Local `main` `3aaa3e8a` | Stale local main | ahead 1 / behind 4 | Unique docs superseded by #221 | Do not use as base | Stale | No | — | — | `SUPERSEDED_BY_MAIN` |

Heartbeat answers (this increment):

1. Required natural cycles observed in repo/scheduler: **0** (`NONE OBSERVED`).
2. Valid Stage 2 evidence: **none** (experiment not present).
3. Stage 2 acceptance contract: **not applied**.
4. Additional natural cycle for Stage 2: **not required** because Stage 2 is not in tree; do not start one.
5. This reconciliation **does not** alter Item 7 #222 or any empirical receipts.

`NO HISTORICAL OR PROSPECTIVE EVIDENCE MUTATED`.
