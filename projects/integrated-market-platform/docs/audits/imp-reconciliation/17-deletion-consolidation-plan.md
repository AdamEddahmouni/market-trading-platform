# 17 — Deletion & Consolidation Plan (WS07)

Status: **COMPLETE (WS07, 2026-09-07)**. Reconciles every WS06 deletion
candidate (DEL-01..07) and consolidation candidate (CON-01..10) with WS03/WS05
evidence into final dispositions. Policy (controller §67/§68): never delete
because something is old/donor-lineaged/phase-named/ugly; delete only with no
legitimate requirement, no active dependency, replacement exists, and
validation proves safe removal. Consolidate only when two systems claim the
same responsibility; never consolidate intentionally separate boundaries
(e.g., provider raw payload vs canonical domain observation).

All dispositions are **planned work for recovery waves** — nothing in this
file has been executed.

---

## 1. Deletion register (final dispositions)

| ID | Artifact | Current usage (evidence) | Reason candidate | Dependency impact | Replacement | Action | Wave | Validation |
|---|---|---|---|---|---|---|---|---|
| DEL-01 | `/paper/account`, `/paper/positions`, `/paper/fills`, `/paper/risk`, `/paper/orders` GET | 0 non-test frontend refs (WS06 §15); ui1/ui2 API suites may assert them | Superseded by `/paper/portfolio` + `/paper/order-history` (route families) | ui1/ui2 route tests may break | `/paper/portfolio` projections (existing) | **ARCHIVE_FIRST** — add deprecation header + route log entry; remove only after ui1/ui2 test-caller confirmation in Wave 8 | Wave 8 | grep callers incl. tests; run ui1/ui2; confirm 0 assertions before removal |
| DEL-02 | `/workspace/:symbol/market-context` route (backend-only lane) | No lane registry entry, no hook, no App.tsx route; backend sentiment/event/expectation engines ARE live research value (FC-17, WS06 §15) | No user surface | None if backend modules kept | **Wire a real UI lane** (product decision D22 resolved: wire, don't archive) | **KEEP + WIRE** (do not delete backend) | Wave 6 | new lane renders `build_workspace_market_context_payload`; lane-registry parity test |
| DEL-03 | `pytest-equity-premerge-20260824/`, `pytest-equity-postmerge-20260824c/` (parent root) | Empty artifact dirs — 0 files (WS06 REPO-002) | No content | none | none | **DELETE** | Wave 8 | `find` census 0 files; git rm only tracked entries (likely untracked) |
| DEL-04 | Child-repo `.github/workflows/imp-*.yml` (STALE copies) | Explicit STALE headers; canonical CI lives at parent root (WS06 REPO-003) | Duplicate; could be mistaken canonical | none (parent CI unaffected) | Parent-root CI (canonical) | **DELETE + pointer** (replace with a one-line README pointer to parent CI) | Wave 8 | verify parent CI canonical; docs pointer present |
| DEL-05 | `/capabilities` GET | No caller; `/context` `capability_states` supplies the same (WS06 §15) | Duplicate of `/context` | none | `/context` capability_states | **DELETE** after confirming endpoints.ts + tests | Wave 8 | grep endpoints.ts; ui1/ui2 run |
| DEL-06 | `tools/run_all_tests.py` / duplicate full_invalidator entries | Second test runner vs `validate.py`; manifest `full_invalidators` lists it (WS06 §15) | Duplicate command path | tests/agents may invoke it | `tools/validate.py` (canonical) | **KEEP if referenced; else DEPRECATE** — verify agent/CI references first; do not delete in Wave 8 without a caller census | Wave 8 | caller census (grep tools/ CI/ docs/); if 0 callers, add deprecation note, remove in a later cleanup increment |
| DEL-07 | Mongo/pymongo repositories (`xa04/mongo`, `intelligence/persistence/mongo`, `analysis.py` pymongo path) | SQLite is canonical persistence; Mongo = alternate/optional (DEP-001) | Optional-path install cost | tests may cover optional paths | SQLite canonical store | **KEEP_AS_OPTIONAL + DOCUMENT** — mark optional in README/docs, keep isolated; do not delete (dependency question D29 resolved: optional/isolated) | Wave 8 | tests confirm SQLite canonical; docs state optional |

## 2. Repository cleanup plan (34 §repository cleanup)

| Item | Classification | Action | Wave | Evidence |
|---|---|---|---|---|
| Stale short-squeeze snapshot (`projects/short-squeeze-project/` @ `78b7467`) | KEEP_CANONICAL_TREE + refresh | **Refresh snapshot via guarded import** to child `fix/frozen-followups` @ `9de7b2f` (plan ref `41f52bb` reconciled) + update `workspace-manifest.json` | Wave 0 | WS06 REPO-001 (three truths); TD-RP1 |
| `pytest-equity-*` temp dirs | SAFE_DELETE | Delete (0 files) | Wave 8 | REPO-002 / DEL-03 |
| STALE child-repo CI copies | SAFE_DELETE + pointer | Delete; add pointer | Wave 8 | REPO-003 / DEL-04 |
| Donor remnant trees (GridIQ, CVD, internship, futuresX) | KEEP_LOCAL_ONLY (read-only by policy) | **No action** — never clean donor trees blindly (controller §64/§67) | n/a | REPO-004 |
| `Claude Code News/` (node_modules untracked) | KEEP_LOCAL_ONLY | No action (D7 closed — `.gitignore` covers) | n/a | DEP-003 |
| `.worktrees/` internal lineage worktrees | KEEP_LOCAL_ONLY | No action (program isolation) | n/a | WS01 §non-source |
| `integrated-market-platform/.planning/` scratch | KEEP_LOCAL_ONLY | No action (scratch history, not canonical) | n/a | 00-program-state |
| `project-scope-images/` | KEEP_CANONICAL (Tier A evidence) | No action | n/a | 02a |
| `docs/audits/imp-reconciliation/` | KEEP_CANONICAL (program record) | This workspace | n/a | README |

## 3. Consolidation register (final dispositions)

| ID | Area | Multiple implementations | Canonical owner (target) | Migration order | Boundary to preserve | Action | Wave |
|---|---|---|---|---|---|---|---|
| CON-01 | Asset-class vocabularies | `paper/contracts.ASSET_CLASSES` (incl. CRYPTO/PREDICTION_MARKET) vs `xa01.enums.XaAssetClass` (no CRYPTO) vs futures family registry | **XA-01 `XaAssetClass`/`InstrumentKind`** (extended with CRYPTO, bond, commodity identity) | (1) extend XA-01; (2) add runtime instrument ref carrying asset-class + contract fields; (3) deprecate `paper ASSET_CLASSES` (keep compat shim) | Runtime boundary types distinct (paper instrument ref ≠ identity kernel; both resolve through one vocabulary) | CONSOLIDATE (RC-004) | Wave 1 |
| CON-02 | Frontend/backend schemas | `ui/src/api/schemas.ts` (2,000 lines) vs backend projection builders | **Generated/shared contracts** (OpenAPI from projection builders or typed contract package) | (1) canonical error taxonomy (RC-010); (2) generate initial contracts; (3) migrate frontend to generated types; (4) keep `schemas.test.ts` interim | none (replacement only) | CONSOLIDATE (RC-010) | Wave 7 |
| CON-03 | Error taxonomy | ad-hoc reason codes across `server.py` projections | **Canonical 12-category taxonomy** (VALIDATION_ERROR, PROVIDER_UNAVAILABLE, PROVIDER_REJECTED, STALE_DATA, UNSUPPORTED_CAPABILITY, ACCOUNT_UNAVAILABLE, RISK_BLOCKED, MODE_BLOCKED, AUTH_ERROR, RATE_LIMITED, TIMEOUT, INTERNAL_ERROR) | additive first: introduce enum; map existing codes; frontend typed union | none (additive) | CONSOLIDATE (RC-010) | Wave 7 |
| CON-04 | Query-key factories | inline keys in `hooks.ts` + prefix invalidation | **One factory with mode/account/provider/as-of dimensions** | (1) add mode dimension; (2) isolation test; (3) retire inline literals | none | CONSOLIDATE (RC-011) | Wave 7 |
| CON-05 | Portfolio ledgers | `portfolio/ledger.py` (equity minor-int) vs `portfolio/options_ledger.py` (float) vs futures sim floats | **Canonical multi-asset ledger** (RC-001) | (1) canonical position/valuation model; (2) options merge (float→Decimal); (3) futures Decimal; (4) remove compat | numeric base single (int minor/Decimal) | CONSOLIDATE (RC-001) | Wave 1 |
| CON-06 | Evidence models | `cross_lane/evidence.py` + `participant/evidence.py` + `intelligence/contracts/evidence.py` (coherent chain) | **Keep layered chain; one documented ownership model** (cross_lane NormalizedLaneEvidence = canonical normalization; participant families = specialist input; EvidenceV1 = specialist contract) | (1) ownership documentation (RC-020); (2) metadata unify only | intentional layering preserved (raw provider payload ≠ canonical observation) | DOCUMENT_OWNERSHIP (RC-020), not code merge | Wave 0 |
| CON-07 | ADR homes | `docs/architecture/*.md` + `docs/superpowers/decisions/*.json` + `docs/research/donors/*` | **`docs/architecture/` markdown canonical; superpowers JSON = machine-readable mirrors** | (1) declare owner in docs authority; (2) new ADRs to canonical home; (3) migrate key existing ADRs (ADR-GRIDIQ-001, ADR-DONOR-001, ADR-DCACHE-001, ADR-RDATA-001, ADR-LLM-001, ADR-WHALE-001, ADR-LIVE-002, ADR-C-001..010) | JSON kept as mirrors | CONSOLIDATE (RC-020) | Wave 0 |
| CON-08 | Provider capability metadata | `providers/contracts.py` Protocols + live_runtime capability registry + operator readiness providers | **Provider Capability Registry** (provider → roles → capabilities → gates → freshness policy → discovery) | (1) registry model; (2) adapters report `capabilities()`; (3) UI/planner consult registry | provider raw payload ≠ canonical observation | CONSOLIDATE (RC-009) | Wave 4 |
| CON-09 | Current-state docs | WORK_LOG + PROGRAM_STATUS + task_plan/progress/findings + docs authority | **WORK_LOG + docs authority map** (canonical); audit workspace separate | (1) state canonical ownership in AGENTS.md; (2) demote planning scratch | audit workspace preserved separately | CONSOLIDATE (RC-014/RC-020) | Wave 0 |
| CON-10 | Chart libs | recharts + lightweight-charts | **Keep both** (different use cases: analytics vs financial charts) | revisit only if bundle budget tightens (PERF-002 budget gate is the arbiter) | none | KEEP_AS_IS | n/a |

## 4. Documentation supersession plan (33 §documentation supersession)

All items: **preserve history; add `SUPERSEDED` / `HISTORICAL` context; never
delete.** Wave 0 (with RC-013, DOC-003, TD-P1).

| Document | Current framing | Correction |
|---|---|---|
| `docs/superpowers/governance/2026-08-14-donor-code-permissions.json` | PROTO-DS340W-001/PROTO-GRIDIQ-001 with "Lucas email permission" (wrong Lucas) | Header: SUPERSEDED (2026-09-06 Heller correction — mistaken donor); permission evidence invalid for reuse; preserved as history |
| `docs/superpowers/decisions/2026-08-16-adr-gridiq-001-port-adapt-patterns.json` | GridIQ as authorized donor source | Header: authorization basis SUPERSEDED (mistaken donor); implementation stands independently (PORT_ADAPT, zero identifiers); capability required → KEEP |
| `docs/superpowers/governance/2026-08-16-gridiq-port-phase-gate.json` | Phase gate records | Annotate: gate enforced an independent PORT_ADAPT (not donor code admission) |
| `docs/superpowers/decisions/2026-08-15-adr-donor-001-component-disposition.json` | Donor component disposition | Annotate per-component with corrected provenance (no code removal; disposition unchanged) |
| `docs/research/donors/DONOR_REUSE_MATRIX.md` | Cites files absent locally; treats Heller as donor | Header + row annotations: matrix reflects pre-correction snapshot; Heller rows NOT_AUTHORIZED; GridIQ rows = PORT_ADAPT concepts only |
| `docs/research/donors/GRID_IQ_NOTES.md`, `DS340W_NOTES.md` | Notes as donor references | Header: HISTORICAL — mistaken donor; pattern concepts only; no code copied |
| `docs/research/donors/README.md` | Donor boundary rules | Add correction context; point to 03/16 audit files |
| `docs/superpowers/plans/2026-08-14-revision-3-donor-integration-and-evidence-transition.md`, `2026-08-15-phase-0a-...` | Pre-correction donor plans | Header: HISTORICAL (pre-Heller-correction); superseded by reconciliation program |
| `docs/engineering/PROVIDER_DUPLICATION_AUDIT.md`, `docs/engineering/WORK_LOG.md` (donor-era entries) | Donor-era record | Annotation only on donor-era entries |
| `docs/research/fixtures/2026-08-15-phase-0a-collection-fixture-inventory.md` | Fixture inventory | Annotate donor fixture provenance per 03 fixture registry (research-only) |
| `tests/gridiq/test_required_future_tests.py` (docstring/name) | References donor notes | Annotate: conformance harness for independent implementation (no test change) — TD-P3 |
| `donor_patterns/` package (namespace docstring) | Name implies donor code | Namespace annotation: independent lane formulas (CVD/options/futures/order-book/edgar); rename deferred (D18) — TD-P2 |

## 5. Wave-8 cleanup summary

Deletes (evidence-backed, Wave 8): DEL-03 empty pytest dirs; DEL-04 stale CI
copies (+pointer); DEL-05 `/capabilities`; DEL-01 routes after test-caller
confirmation (deprecate first). DEL-06 depends on caller census. DEL-07 =
document-optional, no delete.

Everything else: KEEP / ARCHIVE / DOCUMENT — nothing removed in Waves 0–7
except governance supersession headers (in-place, non-destructive).