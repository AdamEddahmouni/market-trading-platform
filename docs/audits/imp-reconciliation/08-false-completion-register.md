# 08 — False-Completion Register

Status: **COMPLETE (WS04, 2026-09-06/07)**. Evidence-backed reconciliation of
historical completion claims. Classification vocabulary: VALID ·
VALID_BUT_REGRESSED · PARTIALLY_VALID · FALSE_COMPLETION · NO_LONGER_RELEVANT ·
UNVERIFIABLE (plus `VALID_FOR_HISTORICAL_SCOPE` in explanatory notes where a
claim was true for its recorded cutoff but is incomplete against today's
expanded target — that alone is never FALSE_COMPLETION).

Evidence: WORK_LOG entries, validation receipts
(`artifacts/developer-workflow/full-validation-receipt-20260904.json`,
`artifacts/developer-workflow/closure-report.json`), program docs
(PROGRAM_STATUS/MASTER_ARCHITECTURE), BUILD35 acceptance artifacts, this
session's fresh runs (15-validation-evidence).

## Register

| # | Historical claim | Source / cutoff | Classification | Evidence / interpretation |
|---|---|---|---|---|
| FC-01 | "~2209 tests / 1 failure / 92 errors; focused closed / global validation blocked" | WORK_LOG 2026-09-02 (Equity Paper loop handoff) | **VALID at cutoff; NO_LONGER_RELEVANT for current state** | Honest blocked-state record: the failures were pre-existing dirty-tree + git-ownership issues, explicitly labeled "GLOBAL VALIDATION BLOCKED", never presented as product green. Resolved 09-04 (unblock → 3462 → 3487 → 3569 → 3575 all-green receipts). Fresh WS04 FULL = 3580 tests / 1 environmental failure / 0 errors. The 08 skeleton's bootstrap caution is discharged: reproduced, explained, superseded. |
| FC-02 | "Full validation green: 3487 tests, 43 skipped, 0 failures, 0 errors" | receipt 2026-09-04 | **VALID** | Reproduced structurally: fresh FULL = 3580 tests, 48 skipped, 0 errors; the only 1 failure is the excluded dirty-tree `cross_lane` golden (absent from committed baseline). Receipt format confirmed. |
| FC-03 | "Full validation green: 3569 / 3575 passed" | WORK_LOG 2026-09-05/06 (Q-H1-O10, Q-H3) | **VALID** | Consistent with FC-02 and WS04 fresh run; suite grew with Q-series golden tests. |
| FC-04 | BUILD35 "FULL_SYSTEM_ACCEPTED_WITH_LIMITATIONS" | `artifacts/full-system-acceptance/BUILD35_FULL_ACCEPTANCE_REPORT.json` | **PARTIALLY_VALID** | Valid as historical acceptance of the BUILD35 candidate at its recorded cutoff, WITH documented limitations; PROGRAM_STATUS itself disclaims current production readiness from BUILD35. Not a false completion; the acceptance is scoped. |
| FC-05 | Repository closure "COMPLETE" | `POST_BUILD35_REPOSITORY_CLOSURE_AUDIT.md` | **VALID for its recorded source** | Closure was for the recorded source classification; audit now passes (09-04 cleanup). |
| FC-06 | IMP-OF-01/02/03, IMP-RT-01, IMP-XA-01..05 "COMPLETE_WITH_LIMITATIONS" (XA-05 COMPLETE) | PROGRAM_STATUS / acceptance reports | **VALID_FOR_HISTORICAL_SCOPE** | Each is scoped to its milestone and documents limitations; WS04 source/tests confirm the implementations exist and pass (of01 84, of02 33, of03 41, rt01 26, xa01..05 109). Not completion of the broader product. |
| FC-07 | EVIDENCE-01 "COMPLETE" (policy/machinery); EVIDENCE-01A "COMPLETE" (campaign framework); EVIDENCE-01B "IMPLEMENTED, not operationally accepted" | PROGRAM_STATUS | **VALID** | Honestly scoped: machinery/framework complete; 01B explicitly NOT operationally accepted; EVIDENCE-01C DEFERRED. WS04 confirms gates G1–G6 remain closed and no live wires verified. |
| FC-08 | TD-001/002/003/005/006 closures (2026-09-01): paper history paging, lane provenance timestamps, multi-account broker snapshots, auth/multi-user, UI CI | `docs/engineering/TECH_DEBT.md` | **VALID** | Implementation reproduced in WS04: `/paper/order-history`, `lane_provenance`, `OperationalIdentity`+`/accounts`+`AccountSnapshotCache` (TD-003), `IMP_AUTH_ENFORCEMENT_MODE`+session API (TD-005), `validate-ui` CI job. V3 tests pass. |
| FC-09 | "Order Flow ~12–15% of redesign target" / "Options ~8–12%" / "Futures ~5–8%" / "Market Context ~5–8%" (lane audits 2026-08-18/19) | `docs/research/*_CURRENT_STATE_AUDIT.md` | **VALID_FOR_HISTORICAL_SCOPE; SUPERSEDED by later phases** | The audits were honest baselines at their date; hardening sprint (through 09-06) added Q-series formulas, O3/O5/O10/BL, futures engines, MC11 macro, XA-02/03. WS04 supersedes the percentages with the fresh matrix (05). |
| FC-10 | "Phase 10 PASS" (CVD), "Phase 11 complete" (Options fixture lane), "Phase 13/14 PASS" (L2/ES depth) | phase governance + lane audits | **VALID_FOR_HISTORICAL_SCOPE** | Phase-gate claims were for fixture-first lane scopes, which remain true; they never claimed provider-backed completion. WS04 retains PARTIAL lane statuses. |
| FC-11 | "Short Squeeze screener" research-evidence status; no calibrated predictor | SHORT_SQUEEZE audit + Phase 4 skeleton | **VALID (honest)** | The platform does not claim prediction; `squeeze_probability: None`, ADAM pins assert-only, Phase 4 `NOT_CALIBRATED` fit-report skeleton. Consistent with WS04 (PARTIAL). |
| FC-12 | P6 Shadow Run 1 / EVIDENCE-01C "DEFERRED" | PROGRAM_STATUS / MASTER_ARCHITECTURE | **VALID** | Deferred, not claimed complete; preserved protocols/records. WS04 confirms no active forward-observation campaign. |
| FC-13 | "Accepted production live broker transport" — ABSENT (explicit) | PROGRAM_STATUS §Live-readiness | **VALID (honest negative)** | The program explicitly records ABSENT, not PARTIAL. WS04 reproduces: broker paper = fixture-first; LIVE-001 blocked; no accepted broker transport. |
| FC-14 | WORK_LOG per-change claims ("domain options 583 passed", "full 3575 passed", etc.) | WORK_LOG entries | **VALID** | Reproduced in WS04 domain/full runs (options 583, futures 526, order-flow 539 with the same 1 dirty-tree failure; full 3580). |
| FC-15 | WS03 "no IBKR client in IMP" | 03-donor-integration-map (2026-09-06) | **FALSE_COMPLETION (negative-claim error), corrected WS04** | `tools/ibkr/*` (Client Portal REST + TWS L1 observational, commit `4853df0`, 2026-08-24; tests/ibkr 47 pass) predates WS03. The substance (no L2 depth; not wired to CVD; no broker execution) stands, but the "zero IBKR client" record was wrong. Correction recorded in 05 §6. |
| FC-16 | MASTER_ROADMAP implying current program lanes cover the product | MASTER_ROADMAP v1.x | **PARTIALLY_VALID → STALE** | Roadmap predates the mandate: zero mention of Bonds/Crypto/Gold/Silver/Commodities/Whale/Industry/Government. Not a completion claim per se, but it understates authorized scope → documentation gap (MS-13), update at WS07. |
| FC-17 | UI "market-context" lane implied as available | `laneRegistry.ts` (11 lanes, no market-context) vs `server.py` `/workspace/:symbol/market-context` route | **PARTIALLY_VALID → UNREACHABLE** | The backend lane projection exists (sentiment/event/expectation engines) but has **no frontend lane, no route in App.tsx, no hook, no registry entry** (WS06 API-004/DEL-02). The *backend capability* is real; the *user surface* is not. Recorded as dead-route candidate, not deleted. |
| FC-18 | `validate changed` as a reliable cheap gate | WS04 changed run (21 tests / 1.8s) + WS06 controlled `--explain` runs | **FALSE_COMPLETION (tooling claim), CONFIRMED** | WS06 proved three under-selection modes: (a) monorepo `projects/`-prefixed paths match no suite globs and do not escalate; (b) `fixtures/**`, `config/**`, `tests/fixtures/**` select nothing; (c) shared modules escalate to 5 core suites but not true dependents. CI strips the prefix so CI remains correct; **local monorepo validation is silently under-selected** (DEV-001/002, TD-TS1). |
| FC-19 | `full_suite_required=true` implies the full suite ran | `validate.py::_offline_core_diagnostics` behavior + telemetry (changed ≈74s avg) | **MISLEADING LABEL** | The flag runs `validation/phase0/contracts/runtime/providers` + mandatory (5 core suites), NOT the 60-suite full run (451s). Output can mislead developers/agents into believing full coverage occurred. WS07: rename to `core_checkpoint_required` and print what actually ran. |

## WS07 final reconciliation (2026-09-07)

Final classification pass (controller §55) — no new rows were added; each
row was re-confirmed or annotated once:

| # | Final classification | Note |
|---|---|---|
| FC-01 | VALID at cutoff; NO_LONGER_RELEVANT | superseded by WS04 fresh baseline |
| FC-02 | VALID | reproduced structurally |
| FC-03 | VALID | consistent with fresh runs |
| FC-04 | PARTIALLY_VALID | scoped acceptance; PROGRAM_STATUS disclaims |
| FC-05 | VALID (recorded source) | closure was source-scoped |
| FC-06 | VALID_FOR_HISTORICAL_SCOPE | milestone-scoped; 05 retains PARTIAL |
| FC-07 | VALID | EVIDENCE-01B not operationally accepted (honest) |
| FC-08 | VALID | TD closures reproduced in WS04 |
| FC-09 | VALID_FOR_HISTORICAL_SCOPE; SUPERSEDED | superseded by WS04 matrix |
| FC-10 | VALID_FOR_HISTORICAL_SCOPE | fixture-first lane scope honest |
| FC-11 | VALID (honest) | NOT_CALIBRATED preserved |
| FC-12 | VALID | deferred, not claimed |
| FC-13 | VALID (honest negative) | broker transport ABSENT explicit |
| FC-14 | VALID | reproduced |
| FC-15 | FALSE_COMPLETION (corrected) | WS04 correction stands; WS07 owns no change |
| FC-16 | PARTIALLY_VALID → STALE | roadmap refresh = BL-0006 (WS07) |
| FC-17 | PARTIALLY_VALID → UNREACHABLE | market-context lane wiring = BL-0602 (WS07) |
| FC-18 | FALSE_COMPLETION (tooling) | correction = BL-0002..0004 (WS07) |
| FC-19 | MISLEADING LABEL | rename = BL-0004 (WS07) |

Result: 0 new duplicates; 17/19 rows unchanged in substance; FC-16/17/18/19
now own explicit backlog items (BL-0006, BL-0602, BL-0002..0004). No row is
unverifiable.

## Rules applied

- A claim valid for its historical cutoff is never FALSE_COMPLETION merely
  because scope later expanded (`VALID_FOR_HISTORICAL_SCOPE` used in notes).
- Existence ≠ completion; a passing unit test ≠ an end-to-end workflow; a
  fixture test ≠ provider-backed runtime capability (each recorded per lane in
  05).
- No claim of production readiness, live execution, broker transport, or
  calibrated prediction was found to be falsely asserted: IMP's own records
  are consistently honest on those negatives.