# Phase 0A — data feasibility and donor characterization (planning draft)

**Status:** Complete — Phase 0A `PASS` published; `DF-001`/`DF-002` `PASS` on admitted non-ES equity intraday source  
**Plan date:** 2026-08-15  
**Baseline verified:** 2026-08-15 (Phase 0 publication bindings)  
**Scope:** Phase 0A only  
**Operating mode:** Documentation, read-only inspection, and offline evidence
generation only after separate implementation authorization  
**Design spec:** [Phase 0A design spec](../specs/2026-08-15-phase-0a-data-feasibility-and-donor-characterization-design.md)  
**Canonical specification:** Revision 3
`foundation.canonical_specification.revision_3`

## 1. Purpose

Operationalize Phase 0A of the canonical specification after Phase 0 structural
PASS. This plan defines work packages, deliverables, assertion rules, owners,
status semantics, and exit criteria for data feasibility (`DF-001`, `DF-002`)
and read-only donor characterization.

Phase 0A does **not** implement canonical contracts, adapters, replay engines,
strategies, or Phase 1 ADRs.

## 2. Authority and precedence

Precedence order:

1. Revision 3 canonical specification (and incorporated Revision 1 §17.5–17.6).
2. Phase 0A design spec at its approved exact hash.
3. This operational plan at its approved exact hash.
4. Phase 0A implementation authorization at its approved exact hash.
5. Phase 0A evidence manifests and assertion results.
6. Donor notes and fixture inventory as descriptive evidence only.

Phase 0 PASS does not authorize Phase 0A work. No ADR or evidence result may
weaken Phase 0 or Revision 3 prohibitions.

## 3. Current gate state

Phase 0A aggregate state: **PASS** (Option 2 admitted non-ES equity intraday source; ES-session bundle remains blocked).

| Gate | State | Reason |
|---|---|---|
| Phase 0A design spec | `APPROVED` | Principal exact-hash approval recorded |
| Phase 0A operational plan | `APPROVED` | Principal exact-hash approval recorded |
| Phase 0A implementation authorization | `APPROVED` | Principal exact-hash approval at bound hash |
| Phase 0A implementation activation | `EFFECTIVE` | Activation record published |
| Admitted-source decision | `EFFECTIVE` | Option 2: `ADMIT_NON_ES_EQUITY_INTRADAY_SOURCE` |
| `DF-001` | `PASS` | Non-pointer bytes, pinned hash, parser, license resolved |
| `DF-002` | `PASS` | Capability manifest truth, sampled schema, source semantics |
| Donor characterization index | `COMPLETE` | Seven-donor read-only index in evidence bundle |
| Phase 0A final status | `PASS` | `phase0a.pass_publication` published |

Phase 0 publication verification (2026-08-15): **ALL PASS** — bindings intact.

## 4. Scope boundaries

### 4.1 In scope (after authorization)

- Read-only fixture inventory updates and admitted-source decision support.
- Offline hash verification of selected non-pointer objects.
- Offline parser report for admitted source only.
- License/entitlement classification record (no credential values).
- Positive and negative capability manifests.
- Sampled schema and source-semantics reviews (sanitized).
- Seven-donor read-only characterization index (including DS-340W and GridIQ).
- Prototype oracle characterization without copy.
- Assertion registry extension for `DF-001`/`DF-002`.
- One-run assertion evaluation and candidate evidence root.
- Optional qualifying independent AI reviews per approved procedure.

### 4.2 Out of scope

- Git LFS retrieval or pointer materialization.
- Copying donor code, data, outputs, or credentials into governed repo.
- Running donor installs, entry points, migrations, or remote fetches.
- Provider/broker connections, paper/live trading.
- Canonical contract implementation (Phase 2).
- Phase 1 ADR acceptance.
- Normalization to canonical events (Phase 3).
- Modifying Phase 0 candidate bundle `DA8BEB60…` or postreview bytes.
- Preregistered performance thresholds before fixture report exists.

## 5. Governing invariants

1. **Read-only donors.** Inspection is metadata, schema, and structure only.
2. **No pointer masquerading as data.** LFS pointers never satisfy `DF-001`.
3. **Capability truth.** Unsupported capabilities are explicit `false`, not omitted.
4. **License before PASS.** Unresolved entitlement keeps `BLOCKED`, not waived PASS.
5. **Separate evidence root.** Phase 0A evidence never overwrites Phase 0 roots.
6. **Evidence over assertion.** Missing evidence is `BLOCKED`.
7. **No secret disclosure.** Same sanitization rules as Phase 0.
8. **ohlcv-1m negative case.** If only bar data is admitted, depth/trade/MBO claims
   must be false and negative fixture documented.

## 6. Work packages

### WP-1 — Governance activation (pre-implementation)

| Step | Deliverable | Owner |
|---|---|---|
| 1.1 | Principal exact-hash approval of design spec | `PROJECT_OWNER` |
| 1.2 | Principal exact-hash approval of this plan | `PROJECT_OWNER` |
| 1.3 | Principal exact-hash approval of implementation authorization | `PROJECT_OWNER`, `RELEASE_OWNER` |
| 1.4 | Admitted-source decision record if inventory options remain open | `PROJECT_OWNER` |
| 1.5 | Verify Phase 0 `phase0_status: PASS` still holds | `RELEASE_OWNER` |

**Exit:** implementation authorization `current_state` may move to activatable
pending execution prerequisites.

### WP-2 — Fixture feasibility (`DF-001` unblock attempt)

| Step | Action | Evidence |
|---|---|---|
| 2.1 | Refresh read-only inventory (no LFS) | Updated inventory doc or `phase0a.fixture_inventory` |
| 2.2 | Verify non-pointer bytes and SHA-256 | `phase0a.object_hash_report` |
| 2.3 | Record license/entitlement | `phase0a.license_record` |
| 2.4 | Run authorized offline parser | `phase0a.parser_report` |
| 2.5 | Publish source manifest | `phase0a.source_manifest` |

If no object satisfies predicates, publish `DF-001: BLOCKED` with reason codes
and stop WP-3 parser-dependent steps — donor characterization (WP-4) may still
proceed.

### WP-3 — Capability truth (`DF-002`)

| Step | Action | Evidence |
|---|---|---|
| 3.1 | Sample schema fields and timestamps | `phase0a.sampled_schema_report` |
| 3.2 | Document source semantics | `phase0a.source_semantics_review` |
| 3.3 | Build positive capability manifest | `phase0a.capability_manifest` |
| 3.4 | Document explicit unsupported capabilities | same manifest `explicitly_unsupported` |
| 3.5 | If `ohlcv-1m` only: negative capability fixture | `phase0a.negative_capability_fixture` |

### WP-4 — Donor characterization (read-only)

| Step | Action | Evidence |
|---|---|---|
| 4.1 | Consolidate existing donor notes (5 prototypes + DS-340W + GridIQ) | `phase0a.donor_characterization_index` |
| 4.2 | Cross-check `DONOR_REUSE_MATRIX.md` gaps | index gap section |
| 4.3 | Draft `ADR-DONOR-001` scope statement (planning, not acceptance) | `phase0a.adr_donor_001_scope_draft` |
| 4.4 | Map oracle candidates (CVD, OFI, freshness gates) | `phase0a.oracle_characterization` |

No donor execution. Extend DS-340W and GridIQ per Revision 3 §20 using existing
`DS340W_NOTES.md` and `GRID_IQ_NOTES.md` as inputs.

### WP-5 — Assertion registry and evaluation

| Step | Action | Evidence |
|---|---|---|
| 5.1 | Extend `assertion-predicates.json` to `1.1.0` with `DF-001`, `DF-002` | `phase0a.assertion_registry` |
| 5.2 | Implement or run Phase 0A evaluator tooling (authorized scope only) | `tools/phase0a/*` if authorized |
| 5.3 | One-run evaluation | `phase0a.assertion_results` |
| 5.4 | Aggregate | `phase0a.assertion_aggregate` |
| 5.5 | Candidate evidence root | `phase0a.candidate_evidence_root` |

### WP-6 — Acceptance (post-candidate)

| Step | Action | Evidence |
|---|---|---|
| 6.1 | Principal candidate-root approval | `phase0a.approval_records` |
| 6.2 | Qualifying independent AI reviews (if required) | `phase0a.ai_review_runs`, coverage |
| 6.3 | Acceptance index and final result | `phase0a.acceptance_index`, final result |
| 6.4 | Phase 0A PASS publication | `phase0a.pass_publication` |
| 6.5 | Update `canonical-authority.json` `phase0a_status` | authority manifest revision |

## 7. Assertion matrix

| ID | Version | Mandatory | Depends on |
|---|---|---|---|
| `DF-001` | 1.0.0 | yes | Admitted source bytes, parser, license |
| `DF-002` | 1.0.0 | yes | `DF-001` source identity (may be `BLOCKED` in parallel if no source) |

Phase 0 assertions remain evaluated under Phase 0 registry; Phase 0A does not
re-run `GOV-*`/`SAFE-*` except via unchanged authority verifier reads.

### Aggregator rules (planning)

- If any mandatory Phase 0A assertion is `FAIL` → aggregate `FAIL`.
- If any mandatory assertion is `BLOCKED` → aggregate `BLOCKED`.
- All mandatory `PASS` → aggregate `PASS`.
- `BLOCKED` cannot be waived by prose or partial characterization.

## 8. Owners and approvals

| Capacity | Responsibility |
|---|---|
| `PROJECT_OWNER` | Admitted-source decision, design/plan/authorization approvals |
| `RELEASE_OWNER` | Evidence publication, authority manifest updates |
| `SECURITY_OWNER` | Sanitization review, license record safety |
| `ARCHITECTURE_LEAD` | Authorized executor under implementation authorization |
| `INDEPENDENT_REVIEWER` | Qualifying AI review classes per `AI-REVIEW-PROCESS-001` |

Sole-principal disclosure continues under `phase0.role_assignment`.

## 9. Exit criteria

Phase 0A may publish `PASS` only when:

1. Design spec, plan, and implementation authorization are effective at bound hashes.
2. `phase0a.admitted_source_decision` is effective.
3. `DF-001` and `DF-002` are `PASS` with resolvable evidence hashes.
4. `phase0a.donor_characterization_index` covers all seven donors.
5. Negative `ohlcv-1m`-only case documented when applicable.
6. `phase0a.candidate_evidence_root` accepted with principal approvals.
7. Required independent reviews (if not waived by principal) are `QUALIFIED`.
8. Acceptance index and final result verify.
9. `phase0a.pass_publication` binds to Phase 0 PASS without mutating Phase 0 roots.

Until then Phase 0A remains `BLOCKED` or `FAIL`.

## 10. Relationship to later work

- Phase 0A `PASS` does not authorize Phase 1 implementation — only fixture-dependent
  ADR **choices** may be accepted using Phase 0A evidence.
- Phase 2 remains blocked without Phase 1 accepted ADRs.
- Copying donor material remains blocked without `ADR-DONOR-001` and rights evidence.
- ES-session acceptance bundle (Revision 1 §17.6) remains `BLOCKED` until `DF-001`
  passes for an appropriate admitted source or specification is revised.

## 11. Deliverables register

See design spec §12.3 for logical IDs. Each published member maps to one
repository-relative path, byte length, and SHA-256 in `phase0a.acceptance_index`.

## 12. Implementation source scope (when authorized)

Planned governed paths (implementation authorization may narrow):

```text
docs/superpowers/**          (Phase 0A governance additions)
docs/research/fixtures/**    (inventory updates)
docs/research/donors/**      (characterization index pointers only)
manifests/phase0/**          (registry extension only)
manifests/phase0a/**         (new Phase 0A manifests if split)
evidence/phase0a/**
src/market_platform_foundation/**  (Phase 0A evaluator extensions only)
tests/phase0a/**
tools/phase0a/**
```

Excluded: `evidence/phase0/DA8BEB60…/**`, prototypes, donor trees, LFS objects.

## 13. Stop conditions

- Any authority hash mismatch.
- Unauthorized prototype drift.
- Request to fetch LFS, run donor code, or copy donor bytes without ADR.
- Parser or evaluator requiring network or third-party packages outside authorization.
- Pressure to mark `DF-001` `PASS` on metadata-only or pointer objects.
- Conflict between capability manifest and sampled schema.

## 14. Session completed items

- [x] Phase 0 publication and principal validation verification — ALL PASS
- [x] Collection fixture inventory (read-only)
- [x] Phase 0A design spec — principal approved
- [x] Phase 0A operational plan — principal approved
- [x] Phase 0A implementation authorization and activation
- [x] Admitted-source decision (blocked pending procurement)
- [x] Donor characterization index and oracle map in evidence bundle
- [x] `DF-001`/`DF-002` evaluation — aggregate `BLOCKED`
- [x] Phase 0A candidate evidence root generated
- [x] Principal characterization candidate-root approval and qualifying AI reviews
- [x] Phase 0A acceptance index and final result (`outcome: BLOCKED`)
- [x] `phase0a.blocked_characterization_publication` (does not claim Phase 0A PASS)

## 15. Next session (after lawful source procurement)

1. Update admitted-source decision with pinned object and license record.
2. Re-run pipeline; target `DF-001` `PASS` and `DF-002` evaluation.
3. Principal candidate-root approval and qualifying AI reviews.
4. `phase0a.pass_publication` and `phase0a_status` update.
