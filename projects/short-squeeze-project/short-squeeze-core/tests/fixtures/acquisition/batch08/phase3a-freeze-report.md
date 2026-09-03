# Batch 08 — Phase 3A Request and Result Freeze (sanitized)

- Freeze policy: `phase_3d_phase3a_freeze_policy.v1`
- Phase 3A policy: `phase_3a_transparent_candidate_policy.v1`
- Phase 3A evaluation: `candidate_evaluation.v1`
- Receipt modeling: `PROVIDER_AVAILABILITY_AS_RECEIPT.v1`
- Global preflight: `PREFLIGHT_REJECTED` (unchanged: true)
- Frozen boundary: `2026-07-18T13:37:55.017661+00:00`
- Requests frozen: 15
- Results frozen: 15
- Leakage audits passed: 15
- Report id: `5a2eb737-3ffb-5045-8ec6-84a878151ea9`

## Rule-outcome matrix (25 rules × 13 cases)

| Rule | Category | Batch 07 admissibility | Outcome counts | Evidence | Metric | Readiness |
| --- | --- | --- | --- | --- | --- | --- |
| `BORROW_AVAILABILITY_CHANGE_MAXIMUM` | SHORT_PRESSURE_CONFIRMATION | BLOCKED_MISSING_EVIDENCE | UNKNOWN=15 | false | false | false |
| `BORROW_AVAILABILITY_MAXIMUM` | SHORT_PRESSURE_CONFIRMATION | BLOCKED_MISSING_EVIDENCE | UNKNOWN=15 | false | false | false |
| `BORROW_FEE_CHANGE_MINIMUM` | SHORT_PRESSURE_CONFIRMATION | BLOCKED_MISSING_EVIDENCE | UNKNOWN=15 | false | false | false |
| `BORROW_FEE_MINIMUM` | SHORT_PRESSURE_CONFIRMATION | BLOCKED_MISSING_EVIDENCE | UNKNOWN=15 | false | false | false |
| `COMPLETED_BAR_AVAILABLE` | MOMENTUM_DISCOVERY | ADMISSIBLE | PASS=15 | true | false | false |
| `CORPORATE_ACTION_CONTEXT_AVAILABLE` | CATALYST_EVIDENCE | BLOCKED_MISSING_EVIDENCE | UNKNOWN=15 | false | false | false |
| `DAYS_TO_COVER_MINIMUM` | SHORT_PRESSURE_CONFIRMATION | BLOCKED_MISSING_EVIDENCE | UNKNOWN=15 | false | false | false |
| `FLOAT_MAXIMUM` | MOMENTUM_DISCOVERY | BLOCKED_MISSING_EVIDENCE | UNKNOWN=15 | false | false | false |
| `MARKET_DATA_AVAILABLE` | MOMENTUM_DISCOVERY | ADMISSIBLE | PASS=15 | true | false | false |
| `NEWS_AVAILABLE` | CATALYST_EVIDENCE | BLOCKED_MISSING_EVIDENCE | UNKNOWN=15 | false | false | false |
| `NEWS_AVAILABLE_BEFORE_AS_OF` | CATALYST_EVIDENCE | BLOCKED_MISSING_EVIDENCE | UNKNOWN=15 | false | false | false |
| `NEWS_TIMESTAMP_KNOWN` | CATALYST_EVIDENCE | BLOCKED_MISSING_EVIDENCE | UNKNOWN=15 | false | false | false |
| `NO_DEFAULT_SUBSTITUTION` | EVIDENCE_VALIDITY | NOT_APPLICABLE | PASS=15 | false | false | false |
| `NO_MATERIAL_CONFLICTS` | EVIDENCE_VALIDITY | NOT_APPLICABLE | PASS=15 | false | false | true |
| `PERCENTAGE_CHANGE_MINIMUM` | MOMENTUM_DISCOVERY | ADMISSIBLE_WITH_CONSTRAINTS | PASS=15 | false | true | false |
| `POINT_IN_TIME_ELIGIBLE` | EVIDENCE_VALIDITY | NOT_APPLICABLE | PASS=15 | false | false | true |
| `PRICE_RANGE` | MOMENTUM_DISCOVERY | BLOCKED_MISSING_SEMANTICS | UNKNOWN=15 | false | false | false |
| `PROVIDER_SCOPE_EXPLICIT` | EVIDENCE_VALIDITY | NOT_APPLICABLE | UNKNOWN=15 | false | false | false |
| `PUBLISHED_SHORT_INTEREST_AVAILABLE` | SHORT_PRESSURE_CONFIRMATION | BLOCKED_MISSING_EVIDENCE | UNKNOWN=15 | false | false | false |
| `RELATIVE_VOLUME_MINIMUM` | MOMENTUM_DISCOVERY | BLOCKED_MISSING_SEMANTICS | UNKNOWN=15 | false | false | false |
| `REQUIRED_DOMAINS_PRESENT` | EVIDENCE_VALIDITY | NOT_APPLICABLE | FAIL=15 | false | false | true |
| `REQUIRED_HISTORY_SUFFICIENT` | EVIDENCE_VALIDITY | NOT_APPLICABLE | PASS=15 | false | false | true |
| `REQUIRED_UNITS_COMPATIBLE` | EVIDENCE_VALIDITY | NOT_APPLICABLE | PASS=15 | false | false | true |
| `SEC_FILING_AVAILABLE` | CATALYST_EVIDENCE | BLOCKED_MISSING_EVIDENCE | UNKNOWN=15 | false | false | false |
| `SHORT_INTEREST_PERCENTAGE_CHANGE_MINIMUM` | SHORT_PRESSURE_CONFIRMATION | BLOCKED_MISSING_EVIDENCE | UNKNOWN=15 | false | false | false |

## Aggregate counts

### rule_outcome_over_case_rule_pairs (denominator 375)

- `FAIL`: 15
- `PASS`: 120
- `UNKNOWN`: 240

### rule_outcome_over_categories (denominator 375)

- `CATALYST_EVIDENCE:UNKNOWN`: 75
- `EVIDENCE_VALIDITY:FAIL`: 15
- `EVIDENCE_VALIDITY:PASS`: 75
- `EVIDENCE_VALIDITY:UNKNOWN`: 15
- `MOMENTUM_DISCOVERY:PASS`: 45
- `MOMENTUM_DISCOVERY:UNKNOWN`: 45
- `SHORT_PRESSURE_CONFIRMATION:UNKNOWN`: 105

### batch07_admissibility_over_25_rules (denominator 25)

- `ADMISSIBLE`: 2
- `ADMISSIBLE_WITH_CONSTRAINTS`: 1
- `BLOCKED_MISSING_EVIDENCE`: 13
- `BLOCKED_MISSING_SEMANTICS`: 2
- `NOT_APPLICABLE`: 7

### freeze_status_over_cases (denominator 15)

- `REQUEST_AND_RESULT_FROZEN`: 15

### leakage_audit_over_cases (denominator 15)

- `LEAKAGE_AUDIT_PASSED`: 15

### evidence_use_over_25_rules (denominator 25)

- `METRIC_USED`: 1
- `NO_EVIDENCE_SUPPLIED`: 17
- `OBSERVATIONS_USED`: 2
- `READINESS_ONLY`: 5

### missingness_blocking_reason_over_rule_case_pairs (denominator 525)

- `ABSOLUTE_PRICE_LEVEL_BLOCKED_BY_BATCH07`: 15
- `EVIDENCE_META_RULE_NOT_BAR_DEPENDENT`: 105
- `NO_DETECTION_TIME_EVIDENCE_EXISTS`: 195
- `REQUIRED_DOMAIN_ABSENT_FROM_EVIDENCE`: 195
- `VOLUME_SEMANTICS_BLOCKED_BY_BATCH07`: 15

## Per-case freeze

| Case | Freeze status | Request id | Result id | Bars used | Leakage |
| --- | --- | --- | --- | --- | --- |
| `BATCH01_XNCR_20260718` | REQUEST_AND_RESULT_FROZEN | `18d79a93-b5a4-5508-ace4-dda1cf187253` | `cce7beb3-b6b2-54bd-8ffa-3042ef510e8e` | 6 | LEAKAGE_AUDIT_PASSED |
| `BATCH01_PESI_20260718` | REQUEST_AND_RESULT_FROZEN | `7f7144e0-be6a-5eab-ab27-16017af42dda` | `43806ca6-009c-5811-bb5f-ccb2baaffbec` | 6 | LEAKAGE_AUDIT_PASSED |
| `BATCH01_SLS_20260718` | REQUEST_AND_RESULT_FROZEN | `69bd43c6-05aa-511a-a65c-d9aead683eca` | `266842af-ec8e-57fd-8897-1964d1b26ac8` | 6 | LEAKAGE_AUDIT_PASSED |
| `BATCH01_ZNTL_20260718` | REQUEST_AND_RESULT_FROZEN | `a9718198-786a-5cba-9ec0-8bdf72904fff` | `32fb0637-a405-54fe-b9af-95eccc0564e2` | 6 | LEAKAGE_AUDIT_PASSED |
| `BATCH01_GPRE_20260718` | REQUEST_AND_RESULT_FROZEN | `90bedb1c-3b09-5a9d-b4e4-299163c580f9` | `76c3de43-cef2-5f40-8046-401d240176c8` | 6 | LEAKAGE_AUDIT_PASSED |
| `BATCH01_SSPC_20260718` | REQUEST_AND_RESULT_FROZEN | `302178da-df46-5710-8761-d1f1a2775c64` | `da0f91ca-a1ad-502d-a678-cd58d5c76e06` | 6 | LEAKAGE_AUDIT_PASSED |
| `BATCH01_LBGJ_20260718` | REQUEST_AND_RESULT_FROZEN | `9bfd3fff-3981-5e44-ba1c-e1211e86b347` | `c54938c4-7cab-556d-9405-1a3e3418aef6` | 6 | LEAKAGE_AUDIT_PASSED |
| `BATCH01_TRVI_20260718` | REQUEST_AND_RESULT_FROZEN | `9b5016c7-4c42-552f-b697-9756ad588b5a` | `19bd1aac-408b-5afc-a177-2271e0b19f85` | 6 | LEAKAGE_AUDIT_PASSED |
| `BATCH01_LMNX_20260718` | REQUEST_AND_RESULT_FROZEN | `ffb2bb54-c851-5190-b537-941dbbf48395` | `79865be4-3d2d-56fb-b565-f36a0fbc68a9` | 6 | LEAKAGE_AUDIT_PASSED |
| `BATCH01_MGNX_20260718` | REQUEST_AND_RESULT_FROZEN | `2a87c285-2891-542d-815d-3448339b9de3` | `8383ccd9-061e-508d-9419-c87b2c06898f` | 6 | LEAKAGE_AUDIT_PASSED |
| `BATCH01_BHVN_20260718` | REQUEST_AND_RESULT_FROZEN | `3250542f-366a-5b7f-9862-490a649fed69` | `a68d7954-063e-5967-a51f-fe294df599f5` | 6 | LEAKAGE_AUDIT_PASSED |
| `BATCH01_OBE_20260718` | REQUEST_AND_RESULT_FROZEN | `08ad9d6a-e68f-5760-bb4b-f83e33863f75` | `100457eb-bba8-5547-9165-154dbb3b38da` | 6 | LEAKAGE_AUDIT_PASSED |
| `BATCH01_AVTX_20260718` | REQUEST_AND_RESULT_FROZEN | `86cacd18-07d0-5a1f-b925-8f45a5b03f22` | `b20e982e-5800-59c5-9918-9ea5de2ffded` | 6 | LEAKAGE_AUDIT_PASSED |
| `BATCH01_KLRS_20260718` | REQUEST_AND_RESULT_FROZEN | `58604f8a-709a-5c84-9290-f45974402e70` | `7a589e6b-fad2-5a08-a9d3-54a8ff5d6009` | 6 | LEAKAGE_AUDIT_PASSED |
| `BATCH01_SG_20260718` | REQUEST_AND_RESULT_FROZEN | `b455138d-3cfb-5943-aba0-3807fd68d351` | `eab23b46-4c0b-5cfb-8e3f-b2b01a19fa3a` | 6 | LEAKAGE_AUDIT_PASSED |

## Phase 3B publication-readiness preview (publishes nothing)

| Case | Frozen request | Frozen result | Leakage passed | Outcome complete | Referenceable |
| --- | --- | --- | --- | --- | --- |
| `BATCH01_XNCR_20260718` | true | true | true | false | true |
| `BATCH01_PESI_20260718` | true | true | true | false | true |
| `BATCH01_SLS_20260718` | true | true | true | false | true |
| `BATCH01_ZNTL_20260718` | true | true | true | false | true |
| `BATCH01_GPRE_20260718` | true | true | true | false | true |
| `BATCH01_SSPC_20260718` | true | true | true | false | true |
| `BATCH01_LBGJ_20260718` | true | true | true | false | true |
| `BATCH01_TRVI_20260718` | true | true | true | false | true |
| `BATCH01_LMNX_20260718` | true | true | true | false | true |
| `BATCH01_MGNX_20260718` | true | true | true | false | true |
| `BATCH01_BHVN_20260718` | true | true | true | false | true |
| `BATCH01_OBE_20260718` | true | true | true | false | true |
| `BATCH01_AVTX_20260718` | true | true | true | false | true |
| `BATCH01_KLRS_20260718` | true | true | true | false | true |
| `BATCH01_SG_20260718` | true | true | true | false | true |

## Disclosed receipt-modeling sensitivity

- Alternative policy: `LOCAL_RETRIEVAL_RECEIPT.v1`
- Cases: 15
- Outcome counts: FAIL=15, PASS=75, UNKNOWN=285
- Rules diverging from the primary policy: `COMPLETED_BAR_AVAILABLE`, `MARKET_DATA_AVAILABLE`, `PERCENTAGE_CHANGE_MINIMUM`
