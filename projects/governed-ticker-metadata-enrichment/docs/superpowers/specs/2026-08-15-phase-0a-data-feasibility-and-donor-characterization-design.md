# Phase 0A — Data Feasibility and Donor Characterization Design

**Document date:** 2026-08-15

**Status:** APPROVED; implementation authorized; `DF-001` remains `BLOCKED`

**Design scope:** Governance documentation and evidence schema only

**Intended plan logical ID:** `phase0a.governance_plan`

**Controlling canonical authority:** `foundation.canonical_specification.revision_3`,
SHA-256 `7C6AE5FC9037CA37D44CD1A2FAACD0CB821192920C46CF001541DCD2121FEB35`

## 1. Purpose

Phase 0 published structural no-live safety (`phase0_status: PASS`). Phase 0A is
the **separate** track that must establish:

1. a lawful, non-pointer, locally verifiable admitted-source fixture (or an
   explicitly authorized alternative admitted source);
2. pinned bytes, license classification, schema, timestamps, coverage, and
   capability truth before contracts or strategies assume data semantics;
3. read-only donor characterization for all seven collection donors, including
   Revision 3 extensions for DS-340W and GridIQ;
4. machine-checkable `DF-001` and `DF-002` assertion evidence suitable for Phase
   1 fixture-dependent ADRs.

This design defines semantics, schemas, work boundaries, and evidence
requirements. It does **not** authorize implementation, evidence generation,
donor copying, LFS retrieval, or Phase 1.

## 2. Controlling boundaries

Subordinate authorities:

- Revision 3 canonical specification (§20 Phase 0A, donor rules);
- Revision 1 §17.5–17.6 `DF-001`/`DF-002` predicate definitions (incorporated by
  Revision 3);
- Phase 0 governance plan, SHA-256
  `EE22C688167F5016D7ED1953BB1DAE516BC6AB343655A7D96535C6605D37E904`;
- Phase 0 PASS publication `phase0.pass_publication`, SHA-256
  `8992B4ACA21F2BD1F7CFF743DA2D084755100800E08F5234B0AB0B081324F0A7`;
- Donor permissions record
  `docs/superpowers/governance/2026-08-14-donor-code-permissions.json`;
- Collection fixture inventory
  `docs/research/fixtures/2026-08-15-phase-0a-collection-fixture-inventory.md`.

Phase 0 candidate bundle `DA8BEB60…` and postreview artifacts remain immutable.

Unauthorized by this design:

- Phase 0A implementation or evidence runs;
- assertion registry code changes;
- copying donor bytes into the governed repo;
- Git LFS object retrieval;
- donor installs, entry points, remote fetches;
- Phase 1 ADR acceptance;
- provider/broker/paper/live work;
- claiming Phase 0A `PASS` or authorized status.

## 3. Problem statement

`DF-001` is **BLOCKED** because no collection object simultaneously satisfies:

- non-pointer local bytes;
- pinned SHA-256 match;
- parser-readable event records;
- recorded license/entitlement classification.

The read-only inventory (2026-08-15) found **20 LFS pointers** in Eric_futuresX
covering all primary ES payloads, zero locally verifiable ES event objects, and
several non-ES byte objects with unresolved or prototype-only rights.

Phase 1 cannot accept fixture-dependent choices (`ADR-RDATA-001`, `ADR-PIT-001`,
normalization mappings, capability gates) without Phase 0A evidence.

## 4. Phase 0A outcomes

| Outcome | Evidence |
|---|---|
| Admitted source selected and justified | `phase0a.admitted_source_decision` |
| Source bytes pinned and hash-verified | `phase0a.source_manifest`, `phase0a.object_hash_report` |
| Parser reads ≥1 event record offline | `phase0a.parser_report` |
| License/entitlement classified | `phase0a.license_record` |
| Capabilities truthfully mapped | `phase0a.capability_manifest`, `phase0a.sampled_schema_report` |
| Unsupported capabilities explicit false | `phase0a.capability_manifest` negative section |
| `ohlcv-1m`-only failure case documented | `phase0a.negative_capability_fixture` |
| Donor characterization complete (read-only) | `phase0a.donor_characterization_index` |
| `DF-001`, `DF-002` evaluable | `phase0a.assertion_results`, aggregate |

## 5. Admitted-source selection model

### 5.1 Selection record

`phase0a.admitted_source_decision` is a sanitized JSON record binding:

- `decision_id` (derived hash);
- `selected_path_class` (`EXTERNAL_COLLECTION_READ_ONLY`,
  `GOVERNED_FIXTURE_PATH`, `GOVERNED_SYNTHETIC`);
- opaque `source_object_id` (no absolute host path in published evidence);
- `pinned_sha256`;
- `byte_length`;
- `schema_family` (for example `GLBX.MDP3/ohlcv-1m`, `equity_intraday_jsonl`,
  `synthetic_depth_csv`);
- `license_classification` reference to `phase0a.license_record`;
- `principal_approval` capacities and approval hash;
- `alternative_es_required` boolean (false when non-ES source explicitly admitted).

No selection is effective until principal exact-hash approval of this design,
the operational plan, and the implementation authorization, **plus** an
attributable admitted-source decision when multiple planning options remain.

### 5.2 Planning options (from inventory)

1. Procure lawful Databento `GLBX.MDP3` bytes matching already-metadata-pinned
   hashes without LFS retrieval from Eric_futuresX.
2. Admit non-ES equity intraday source with narrowed Phase 1 scope.
3. Admit governed synthetic fixture with explicit synthetic classification.
4. Remain `BLOCKED` until external procurement.

Default recommendation: **option 1 or 4**. Options 2–3 require explicit
principal narrowing of ES-session acceptance bundle expectations in Revision 3
§17.6.

### 5.3 Eric_futuresX smoke sample

`.smoke_data/es_level2_data.csv` is **not** admissible as the primary admitted
source without a separate principal decision: synthetic provenance, tiny coverage,
and no recorded platform entitlement.

## 6. Assertion semantics

### 6.1 `DF-001` (Data feasibility — source integrity)

**Passing predicate (operationalized):**

1. `phase0a.admitted_source_decision` is effective and references exactly one
   pinned object.
2. `phase0a.object_hash_report` shows observed SHA-256 equals pinned value on
   non-pointer bytes.
3. `phase0a.parser_report` records ≥1 successfully parsed event record with
   parser version, record count sample, and failure count.
4. `phase0a.license_record` contains entitlement class, redistribution class,
   and principal acknowledgment; unresolved rights keep `BLOCKED`, not `PASS`.
5. Object is not a Git LFS pointer (verified by pointer scan or size/prefix rule).

**Required evidence members:** source manifest, object hash, parser report,
license record.

**Blocked reason codes (non-exhaustive):**

- `DF001_NO_LOCAL_BYTES`
- `DF001_LFS_POINTER_ONLY`
- `DF001_HASH_MISMATCH`
- `DF001_PARSER_ZERO_RECORDS`
- `DF001_LICENSE_UNRESOLVED`
- `DF001_NO_ADMITTED_SOURCE_DECISION`

### 6.2 `DF-002` (Data feasibility — capability truth)

**Passing predicate:**

1. `phase0a.capability_manifest` lists every claimed capability with:
   - `supported` boolean;
   - observed field paths or event types;
   - source-semantics citation (`phase0a.source_semantics_review`);
   - normalization notes (descriptive only in Phase 0A).
2. Every unsupported capability required by downstream roadmap claims is
   explicitly `supported: false` (not omitted).
3. `phase0a.sampled_schema_report` documents sampled records, timestamp fields,
   sequence/correction behavior **as observed or explicitly unknown**.
4. If admitted schema is `ohlcv-1m` only, manifest marks
   `trade_tick`, `quote`, `depth`, `mbo`, `aggressor`, `queue` false and links
   `phase0a.negative_capability_fixture`.

**Required evidence members:** capability manifest, sampled schema report,
source-semantics review.

**Blocked reason codes:**

- `DF002_CAPABILITY_CLAIM_WITHOUT_FIELD`
- `DF002_UNSUPPORTED_CAPABILITY_OMITTED`
- `DF002_SCHEMA_SAMPLE_MISSING`
- `DF002_NEGATIVE_CASE_MISSING_FOR_OHLCV_ONLY`

### 6.3 Registry extension

`manifests/phase0/assertion-predicates.json` upgrades to `registry_version`
`1.1.0` (or successor) adding `DF-001` and `DF-002` predicates without
retiring Phase 0 keys. Phase 0A evaluation uses a **separate**
`phase0a.assertion_run_manifest` and `evidence/phase0a/<run_id>/` tree.

Phase 0 aggregate status is unaffected; `canonical-authority.json` gains
`phase0a_status` field in a later publication step (not Phase 0A design scope).

## 7. Capability manifest schema

Logical ID: `phase0a.capability_manifest`

```json
{
  "manifest_version": "1.0.0",
  "admitted_source_id": "<opaque>",
  "schema_family": "<string>",
  "capabilities": [
    {
      "capability_id": "BAR_OHLCV_1M",
      "supported": true,
      "observed_fields": ["open", "high", "low", "close", "volume"],
      "timestamp_fields": ["ts_event"],
      "semantics_ref": "phase0a.source_semantics_review"
    }
  ],
  "explicitly_unsupported": [
    {
      "capability_id": "DEPTH_LEVEL2",
      "supported": false,
      "reason_code": "OHLCV_ONLY_SOURCE"
    }
  ]
}
```

Canonical JSON profile matches Phase 0 (`PHASE0-CANONICAL-JSON-1.0.0`).

Capability IDs align with Revision 3 capability vocabulary and `SC-002`
negative fixture (`BAR_OHLCV_1M` without event capabilities).

## 8. Parser report schema (planning)

Logical ID: `phase0a.parser_report`

Offline parser runs under implementation authorization only. Phase 0A parser:

- standard library only unless a later ADR approves a pinned third-party parser;
- reads only the admitted source object path authorized in implementation scope;
- emits record counts, first/last record summaries (field names and types only,
  no sensitive values), and structured errors;
- does not normalize to canonical contracts (Phase 2).

## 9. Donor characterization scope

Read-only inspection across all seven donors per
`docs/research/donors/README.md`. No code execution.

| Donor | Root ID | Phase 0A extension |
|---|---|---|
| Eric_futuresX | `PROTO-FUTURESX-001` | LFS inventory cross-check; metadata-only ES semantics; formula oracle mapping |
| Trading CVD Bubble | `PROTO-CVD-001` | CVD/OFI oracle candidates; demo data schema only |
| Short Squeeze | `PROTO-SHORTSQ-001` | provenance/freshness gate patterns; fixture JSONL schema |
| Internship | `PROTO-INTERNSHIP-001` | news/options workflow patterns (concept only) |
| L1 Volume Bubble | `PROTO-L1VOL-001` | volume-anomaly viz patterns |
| DS-340W | `PROTO-DS340W-001` | model comparison / walk-forward patterns (existing notes) |
| GridIQ | `PROTO-GRIDIQ-001` | dataset/cache/API/UI patterns (existing notes) |

Deliverable: `phase0a.donor_characterization_index` mapping donor components to
`PORT_ADAPT` / `CONCEPT_ONLY` / `DO_NOT_USE` with earliest phase and test
preconditions, cross-checking `DONOR_REUSE_MATRIX.md`.

Proposed `ADR-DONOR-001` scope statement is a **Phase 0A planning output**, not
acceptance.

## 10. Prototype oracle characterization (no copy)

Selected prototype formulas and contracts (CVD delta, OFI, depth metrics,
freshness gates) are characterized as **potential test oracles** only:

- inputs and outputs described;
- donor path class recorded;
- copy prohibited until `ADR-DONOR-001` and rights evidence;
- no donor code in governed evidence payloads.

## 11. Threshold preregistration rule

Data-dependent completeness or performance thresholds (record counts, coverage
percentages, latency budgets) are **blocked** until:

1. `phase0a.sampled_schema_report` exists; and
2. principal approves threshold register `phase0a.preregistered_thresholds` at
   exact hash.

## 12. Evidence model

### 12.1 Publication root

`evidence/phase0a/<run_id>/` where `run_id` derives from
`phase0a.assertion_run_manifest` per Phase 0 pattern.

### 12.2 Candidate evidence root

`phase0a.candidate_evidence_root` is separate from Phase 0
`78FA6A96…`. Immutable once accepted.

### 12.3 Deliverables register (logical IDs)

| Logical ID | Purpose |
|---|---|
| `phase0a.admitted_source_decision` | Source selection and principal binding |
| `phase0a.source_manifest` | Object identity, pinned hash, byte length |
| `phase0a.object_hash_report` | Observed hash verification |
| `phase0a.parser_report` | Offline parse evidence |
| `phase0a.license_record` | Entitlement and redistribution class |
| `phase0a.capability_manifest` | Positive and negative capabilities |
| `phase0a.sampled_schema_report` | Field/timestamp/sequence sample |
| `phase0a.source_semantics_review` | Human-readable semantics bound to manifest |
| `phase0a.negative_capability_fixture` | `ohlcv-1m`-only negative case |
| `phase0a.donor_characterization_index` | Seven-donor read-only index |
| `phase0a.oracle_characterization` | Prototype oracle map (no copy) |
| `phase0a.preregistered_thresholds` | Optional; post-fixture only |
| `phase0a.assertion_registry` | `DF-001`/`DF-002` registry snapshot |
| `phase0a.assertion_run_manifest` | One-run binding |
| `phase0a.assertion_results` | Per-assertion statuses |
| `phase0a.assertion_aggregate` | Aggregate `PASS`/`FAIL`/`BLOCKED` |
| `phase0a.candidate_evidence_root` | Ordered member hashes |
| `phase0a.approval_records` | Principal approvals |
| `phase0a.implementation_authorization` | Authorization binding |
| `phase0a.final_acceptance_result` | Terminal gate |
| `phase0a.acceptance_index` | Index and root hash |
| `phase0a.pass_publication` | Published Phase 0A PASS (future) |

## 13. Independent review (planning default)

Mirror Phase 0 postroot pattern unless principal approves a lighter review:

- one `ADVERSARIAL_REQUIREMENTS_AND_CONFORMANCE_AUDIT`;
- one `INTEGRITY_AND_REPRODUCTION_AUDIT`;
- bound to `phase0a.candidate_evidence_root` under `AI-REVIEW-PROCESS-001`.

Authoring-session review is nonqualifying.

## 14. Alternatives considered

### 14.1 Selected: separate Phase 0A track with new evidence root

Preserves Phase 0 immutability and clear gate semantics.

### 14.2 Rejected: extend Phase 0 candidate bundle

Would violate immutability of `DA8BEB60…` and blur structural vs data gates.

### 14.3 Rejected: characterize donors by running their code

Violates donor boundary rules and offline constraints.

### 14.4 Rejected: retrieve Eric_futuresX LFS objects for characterization

Explicitly prohibited; would not establish lawful entitlement without separate
license record anyway.

## 15. Minimum governance package for principal approval (before implementation)

| # | Artifact | Approval type | Owner capacity |
|---|---|---|---|
| 1 | This design spec | `EXACT_HASH_PRINCIPAL_APPROVAL` | `PROJECT_OWNER` |
| 2 | Phase 0A operational plan | `EXACT_HASH_PRINCIPAL_APPROVAL` | `PROJECT_OWNER` |
| 3 | Phase 0A implementation authorization JSON | `EXACT_HASH_PRINCIPAL_APPROVAL` | `PROJECT_OWNER`, `RELEASE_OWNER` |
| 4 | Admitted-source decision (when options remain) | `ATTRIBUTABLE_PRINCIPAL_DECISION` | `PROJECT_OWNER` |
| 5 | Assertion registry `1.1.0` predicate extension | Bundled in implementation authorization | `PROJECT_OWNER` |
| 6 | Optional: independent review procedure applicability confirmation | Reference existing `AI-REVIEW-PROCESS-001` or amend | `PROJECT_OWNER` |

Implementation authorization activation additionally requires:

- Phase 0 `phase0_status: PASS` (currently true);
- fresh hash match for all bindings;
- no unauthorized prototype drift since last preservation report.

Post-implementation acceptance (not pre-implementation):

- candidate evidence root approval;
- qualifying AI review classes;
- acceptance index and `phase0a.pass_publication`.

## 16. Reviewer questions

1. What object is the admitted source, and why is it lawful?
2. Where are the bytes, what is the pinned hash, and is the object a pointer?
3. What does the parser actually read?
4. What capabilities are true vs explicitly false?
5. How does the negative `ohlcv-1m`-only case manifest?
6. What donor material remains `DO_NOT_USE` and why?
7. Why is Phase 0A still `BLOCKED` or `PASS`?
