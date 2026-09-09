# 14 — Open Decisions & Missing Evidence

Status: **CURRENT (WS05 closure 2026-09-07)**. Every unresolved matter is
recorded here; nothing blocks the overall program, only the workstream that
needs it. WS04 closed M6/M7 with fresh runtime evidence and added WS04 rows;
WS05 resolved D19 with an architectural recommendation and gave D3/D16 an
architectural shape recommendation (provider choice remains product/professor
input).

## Missing evidence (needed by which workstream)

| # | Evidence | Needed by | Where it should come from | Status (2026-09-06) |
|---|---|---|---|---|
| M1 | Original project-goal screenshots/materials (Tier A baseline) | WS02 | **SUPPLIED** — `project-scope-images/` (7 PNG) inventoried + OCR'd (Windows.Media.Ocr); image index in 02a; verbatim professor quotes in 02. Limitation: set documents email evolution + integration mandate; full original proposal body only partially visible (ORG-001/002 at MODERATE confidence) — later-supplied proposal screenshots supersede | CLOSED_WITH_LIMITATION (WS02) |
| M2 | Professor brief + meeting transcript (`PROFESSOR_BRIEF_AND_ROADMAP.md`, `PROFESSOR_MEETING_TRANSCRIPT_20260813.md`) | WS02/WS03 | Personal files kept OUT of repo; only derived plan (`docs/reviews/2026-09-04-hardening-task-plan.md`) is committed | ABSENT_FROM_REPO |
| M3 | `DS-340W-Fantasy-Football-Prediction-main/` local tree | WS01/WS03 | Absent locally; external repo VERIFIED (https://github.com/lucasheller22/DS-340W-Fantasy-Football-Prediction) | ABSENT_LOCALLY; EXTERNAL_VERIFIED |
| M4 | `L1VolumeBubble-main (1)/` local tree | WS01 | Absent locally; referenced in PROJECT_NOTES_INDEX + docs/DONOR_FIXTURE_MAP.md (Pine file path) | ABSENT_LOCALLY |
| M5 | Donor local git remotes / commit histories (SRC-003..006) | WS01/WS03 | No `.git` in any donor tree. External repos VERIFIED for SRC-001..004 (HTTP 200, identity + README confirmed). SRC-005 (futuresX) and SRC-006 (Claude Code News) external origins remain UNKNOWN | PARTIAL — SRC-001..004 verified; SRC-005/006 UNAVAILABLE |
| M6 | Current reproduction of the historical ~2209-test closure claim (1 failure / 92 errors) | WS04/08 | Fresh `tools/imp.py validate full` on baseline `d691050` | **CLOSED (WS04)** — fresh FULL = 3580 tests, 48 skipped, 1 failure (excluded dirty-tree `cross_lane` golden), 0 errors; the ~2209/1/92 figure was the 09-02 dirty-tree baseline, superseded by 09-04+ green receipts (08 FC-01) |
| M7 | Completion of prior-run full baseline (was running at cutoff) | WS04 | Re-run; see 15-validation-evidence | **CLOSED (WS04)** — full baseline completed (451s) and receipt saved under `.local/ws04-full.json`; appended to 15 |
| M8 | Live-wire evidence for providers (Tradier sandbox, Moomoo OpenD, IB) | WS05/WS06 | Real-wire exercise; gated per FORWARD_VALIDATION_READINESS_CHECKLIST | DEFERRED (gates closed by design) |

## Open decisions

| # | Decision | Options | Status after WS01 | Depends on |
|---|---|---|---|---|
| D1 | Where WS01+ artifacts are produced/committed | parent `docs/audits/imp-reconciliation/` vs isolated worktree | Settled for the program record: this workspace. Remediation increments: isolated worktree | None |
| D2 | SRC-005 (Eric_futuresX) vs SRC-006 (Claude Code News) relationship | COMPLEMENTARY / SUPERSEDES (either) / SEPARATE / SHARED_LINEAGE / UNRELATED / UNKNOWN | INFORMED-OPEN: source level shows SEPARATE_FUTURE_STRATEGIES with complementary roles (Tradovate+Node news-trader vs IBKR+Python L2/research); no code overlap; lineage UNKNOWN (no .git either side). Final relationship (incl. canonical Future architecture) at WS05/WS07 | WS03/WS05 |
| D3 | Canonical Future execution layer: IB, Tradovate, or provider-agnostic adapters | IB (SRC-005 path) / Tradovate (SRC-006 path) / both | **SHAPE RECOMMENDED (WS05): both as capability adapters** behind the existing Protocol/composition architecture; browser-driven Tradovate (CCN `broker_ui.js`) is NOT canonical IMP execution (reimplement bracket semantics in the target order model instead). Provider choice itself remains OPEN (professor/product input — 06 §11, 11 §12) | WS05 (shape); provider choice at WS07 |
| D4 | Whether paid options providers (Unusual Whales / iVolatility) are required capabilities or optional donor choices | Required / optional / replaceable | OPEN — donor-specific per author notes; not present in local remnant; professor said IB "might also be usable" | WS02/WS03 |
| D5 | Whether any GridIQ/Heller material reached IMP implementation, and its disposition | REMOVE / REPLACE_NATIVE / REIMPLEMENT / ISOLATE / KEEP_INDEPENDENT | **RESOLVED (WS03)** — GridIQ patterns ported under ADR-GRIDIQ-001 PORT_ADAPT (8/16); implementation independent (zero GridIQ identifiers; storage/dataset subsystem + assistant audit store + UI patterns); capability required → **KEEP_AS_IS code + governance re-annotation (WS07 Wave 1)**. No code removal or native replacement needed (already native). DS-340W: zero code/test influence | WS03 closed; WS07 executes re-annotation |
| D9 | Local donor source trees are INCOMPLETE REMNANTS (source code absent for SRC-002/003/004/005) | rely on external repos / request re-supply / accept remnant-only | INFORMED (WS03) — no trace was blocked: IMP's own governance (ADRs, phase gates, GRID_IQ_NOTES/DS340W_NOTES, admission manifests) plus verified external repos preserve the pattern-level evidence needed | WS03 closed; re-supply optional |
| D6 | Where the audit workspace lives long-term | chosen: parent `docs/audits/imp-reconciliation/` | Settled | None |
| D7 | `Claude Code News/node_modules/` in the workspace (untracked) | gitignore/exclude / keep local | **CLOSED (WS06)** — parent `.gitignore` `**/node_modules/` pattern verified to cover the donor tree; untracked and ignored; no action beyond keeping it ignored (07 DEP-003) | WS06 closed |
| D8 | Pre-existing dirty files `cross_lane/fusion.py` + `opportunity.py` | leave untouched | Leave untouched per AGENTS change-isolation rule | Owner |
| D9 | Local donor source trees are INCOMPLETE REMNANTS (source code absent for SRC-002/003/004/005) | (a) rely on external GitHub repos for WS03/WS05 evidence; (b) request re-supply of full trees; (c) accept remnant-only analysis | OPEN — external repos are verified and structurally consistent with remnants; WS03 may need repo-side evidence for trace comparisons | WS03/WS05 |
| D10 | Short-squeeze snapshot lag: manifest `78b7467` (`main`) vs child `fix/frozen-followups` @ `9de7b2f` (316-file diff) vs hardening-plan re-sync claim `41f52bb` | refresh snapshot via guarded import / document lag / reconcile at WS03 | **CONFIRMED STALE, NOT INTENTIONAL (WS06 REPO-001)** — three different truths in manifest/child/plan; do not resync during audit; WS07 refreshes via guarded import with evidence | WS07 executes |
| D11 | Claude Code News true author | Lucas Bichara = SUPPLIER (confirmed); AUTHOR unknown | OPEN — package has no author field; no .git; do not assert authorship | WS01 continues to hold |
| D12 | Existing donor-governance records (permissions record, DONOR_REUSE_MATRIX) staleness after Heller correction + remnant finding | mark superseded (preserved) / re-verify against external repos | **PARTIAL → ENUMERATED (WS06 DOC-003)** — exact supersession scope now listed in 07 §20 (9+ docs: permissions record, ADR-GRIDIQ-001, phase gate, ADR-DONOR-001, DONOR_REUSE_MATRIX, GRID_IQ_NOTES, DS340W_NOTES, revision-3 donor plans, PROVIDER_DUPLICATION_AUDIT, fixture inventory); WS07 Wave 1 adds superseded headers in place | WS07 Wave 1 executes |
| D14 | Details-to-be-defined for mandated domains (Bonds instruments/data, Crypto providers, Whale families, Industry classification, Government feeds, Gold/Silver vehicle, Commodities coverage) | define via evidence + prioritization | OPEN by design (AUTHORIZED_DOMAIN, DETAILS_TO_BE_DEFINED per WS02 §43); WS04 confirmed all six are implementation-absent (04 §7) | WS07 |
| D15 | Whether the 7-image set's ORG-001/002 reconstruction (MODERATE confidence) needs the original proposal screenshots for confirmation | accept as-is / request original proposal | OPEN — superseded if original proposal screenshots arrive | WS02 done; supersession anytime |
| D16 | Future execution provider decision (IB vs Tradovate vs adapters) for the authorized Futures capability | as D3 | **SHAPE RECOMMENDED (WS05)** — adapter contract per D3; choice OPEN | WS05 (shape); choice at WS07 |
| D17 | GridIQ/DS-340W governance re-annotation scope (supersede ADR-GRIDIQ-001 authorization framing, permissions record, reuse matrix, notes; add correction context) | annotate in place (preserve history) / consolidate | OPEN — recommended: in-place superseded headers at WS07 Wave 1 (TD-P1) | WS07 |
| D18 | `donor_patterns/` package naming/namespace (content is independent lane formulas) | annotate docstring / rename package / restructure | OPEN — low-risk annotation first; renaming deferred unless WS05/06 requires | WS07 |
| D19 | IBKR observational tooling (`tools/ibkr`) vs professor-required CVD L1/L2 runtime — is the existing read-only client the seed for the required adapter, or separate work? | seed / separate | **RECOMMENDED (WS05): SEED** — `tools/ibkr/client.py` (read-only REST allowlist + pacing/penalty box + capture) is the correct transport/capture core; the adapter adds L1/L2 market-data + account/portfolio capabilities and wires into the CVD lane (06 ARCH-001/ADR-C-002). Final confirmation only if a different IB strategy is preferred | WS05 (rec.); WS07 executes |
| D13 | Did Adam purchase IB L1+L2 data (professor offered to pay one month)? | purchased / not purchased / unknown | STILL UNKNOWN (WS05) — no repo evidence; does not block the adapter/depth design (06 §10); provider readiness later | WS07 |
| D20 | Which whale/participant evidence families are elevated to provider-backed live lanes (per SWIM_WITH_THE_WHALES) | fixture-first / elevate | OPEN — WS04 shows most families fixture-only; elevate per doctrine at WS07 | WS07 |
| D21 | Whether `/paper/{account,positions,fills,risk,orders-GET}` are truly dead (superseded by `/paper/portfolio`) | dead / retained / deprecated | **WS06 CANDIDATE-DEAD** — zero non-test frontend callers; frontend uses `/paper/portfolio` + order-history + trace + strategy-profitability. Final verdict after ui1/ui2 route-test coverage check | WS07 (verify tests, then archive/deprecate) |
| D22 | Whether `/workspace/:symbol/market-context` becomes a real UI lane or the route is archived | wire lane / archive route / keep backend-only | **WS06 CANDIDATE-DEAD as a route** — no lane registry entry, no hook, no route in App.tsx; backend engines (sentiment/event/expectation) are real value (FC-17) | WS07 (product decision) |
| D23 | Query-key structure (mode/account scoping) | add mode+account dimension / leave / partial | **WS06 RECOMMENDED: mode+account-scoped factory + isolation test** (UX-009; 07 §11) — engineering recommendation, not user decision | WS07 |
| D24 | Error taxonomy | canonical taxonomy (12 categories) / keep ad-hoc codes | **WS06 RECOMMENDED: canonical taxonomy + typed frontend union** (API-004; 07 §16) | WS07 |
| D25 | API contract generation | shared/generated contracts / keep manual Zod / typed passthrough improvements | **WS06 RECOMMENDED: generated/shared contracts** (UX-011; 07 §12) with schemas.test.ts interim | WS07 |
| D26 | `validate changed` correction approach | prefix mapping + fixture/config ownership / dependency map / escalate-to-full | **WS06 CONFIRMED under-selection in three modes** (07 §17, FC-18): recommend prefix mapping + fixture/config ownership + rename `full_suite_required` | WS07 |
| D27 | Docs authority ownership / ADR canonical home | markdown ADRs canonical / JSON mirrors / hybrid | **WS06 RECOMMENDED: `docs/architecture/` markdown canonical, superpowers JSON as machine-readable mirrors** (DOC-004; 07 §20) | WS07 |
| D28 | `imp.py env` exit policy | non-zero on hard prereq failure / stay informational | **WS06 RECOMMENDED: non-zero exit for wrong Python + missing npm when UI work planned** (DEV-004; 07 §19) | WS07 |
| D29 | Mongo/pymongo persistence role | optional/isolated / canonical for some paths / remove | OPEN — SQLite is canonical; Mongo repositories are alternate paths (DEP-001/DEL-07) | WS07 |

## WS07 final pass (2026-09-07) — engineering-correctness decisions resolved; product decisions left explicit

| Decision | Final status | Resolution | Blocks |
|---|---|---|---|
| D2 (SRC-005 vs SRC-006 relationship) | **RESOLVED (WS07)** | SEPARATE_FUTURE_STRATEGIES with complementary roles; both contribute concepts only (never code); canonical Future architecture per 11 §13.1 | nothing |
| D3/D16 (Futures execution provider) | DECISION_REQUIRED (product) | adapter shape resolved (both as capability adapters; browser-driven Tradovate NOT canonical); provider choice = professor/product; recommended default = IBKR-first (LATER-008 "Eric's using IB data") with Tradovate adapter later | BL-0404, BL-0301 (IBKR unaffected) |
| D4 (paid options providers) | **RESOLVED (WS07)** | not required (donor-specific; professor LATER-007 "maybe use IB"); optional future | nothing |
| D11 (CCN true author) | OPEN | do not assert authorship; supplier = Lucas Bichara | nothing |
| D13 (IB data purchase) | OPEN (product) | unknown; does not block adapter/depth design (11 §12) | BL-0301/0302 (none) |
| D14 (details-to-be-defined per domain) | OPEN with WS07 direction | structural integration first (identity → provider → surface → portfolio → tests → truthful status) per BL-0501..0506; specific providers TBD at implementation | BL-0501..0506 |
| D15 (original proposal screenshots) | OPEN (supersession) | accept ORG-001/002 reconstruction; superseded if originals arrive | nothing |
| D17 (GridIQ/DS-340W governance re-annotation) | **RESOLVED (WS07)** | in-place SUPERSEDED headers at Wave 0 (BL-0001) | BL-0001 |
| D18 (`donor_patterns/` naming) | **RESOLVED (WS07)** | annotate namespace now (BL-0011); rename deferred | BL-0011 |
| D19 (IBKR tooling as seed) | **RESOLVED (WS07)** | SEED — BL-0301 (D19 was WS05 RECOMMENDED; WS07 adopts) | BL-0301 |
| D20 (whale families elevation) | RECOMMENDED (product) | 13F/crowding/skill first per doctrine (BL-0601) | BL-0601 |
| D21 (dead paper routes) | **RESOLVED (WS07)** | ARCHIVE-first after test-caller census (DEL-01, BL-0803) | BL-0803 |
| D22 (market-context lane) | **RESOLVED (WS07)** | WIRE as real lane — backend engines are real value (DEL-02 → BL-0602) | BL-0602 |
| D23 (query keys) | **RESOLVED (WS07)** | mode/account-scoped factory + isolation test (BL-0701) | BL-0701 |
| D24 (error taxonomy) | **RESOLVED (WS07)** | canonical 12-category taxonomy + typed frontend union (BL-0702) | BL-0702 |
| D25 (API contract generation) | **RESOLVED (WS07)** | generated/shared contracts (OpenAPI/codegen) with schemas.test.ts interim (BL-0703) | BL-0703 |
| D26 (validate changed) | **RESOLVED (WS07)** | prefix normalization + fixture/config ownership + flag rename (BL-0002..0004) | BL-0002..0004 |
| D27 (ADR canonical home) | **RESOLVED (WS07)** | `docs/architecture/` markdown canonical; JSON mirrors (BL-0010) | BL-0010 |
| D28 (env exit policy) | **RESOLVED (WS07)** | non-zero on hard prereq failure (BL-0008) | BL-0008 |
| D29 (Mongo role) | **RESOLVED (WS07)** | optional/isolated; SQLite canonical; documented (DEL-07 → BL-0806) | BL-0806 |
| D7 (CCN node_modules) | CLOSED (WS06) | gitignore covers | — |
| D10 (SS snapshot) | CONFIRMED STALE → **RESOLVED (WS07)** | guarded refresh to `9de7b2f` (BL-0005) | BL-0005 |

Remaining OPEN (7): D11 (author unknown), D13 (IB purchase), D14 (domain detail, direction given), D15 (proposal screenshots), D3/D16 (provider choice), D20 (family elevation). All are product/professor-dependent or evidence-pending — none block Wave 0/1 engineering work.

## Rules for closing

- Close a decision only with evidence + confidence label in the relevant
  workstream file.
- Missing evidence does not block unrelated workstreams.