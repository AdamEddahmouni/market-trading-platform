# Phase 1 — foundational ADR decisions (design spec)

**Status:** Approved for decision work  
**Spec date:** 2026-08-15  
**Scope:** Phase 1 only — ADR acceptance, verifier, and decision publication  
**Canonical specification:** Revision 3 `foundation.canonical_specification.revision_3`

## 1. Purpose

Record every foundational decision affecting identity, time, arithmetic, determinism,
storage, safety, and prototype reuse before Phase 2 contract implementation begins.

## 2. Completion definition

Phase 1 is complete when:

1. Phase 0A `PASS` is published.
2. Every row in `manifests/phase1/adr-registry.json` has an `ACCEPTED` decision file
   with resolvable `conformance_evidence` hashes.
3. `phase1.adr_verifier_result.overall_status` is `PASS`.
4. `phase1.decision_publication` is `PUBLISHED`.
5. `canonical-authority.json` records `phase1_status: PASS` without breaking Phase 0
   or Phase 0A publication bindings.

## 3. Out of scope

- Canonical contract implementation (Phase 2).
- Adapters, replay engines, models, strategies.
- Provider, broker, donor execution, or network access.
- Claiming ES-session acceptance while only equity OHLCV fixture is admitted.

## 4. Verifier contract

The ADR verifier loads the registry, verifies each decision file exists, requires
`status: ACCEPTED`, and requires at least one conformance evidence reference with
`logical_id` and `sha256`. Any missing or non-accepted row is reported `BLOCKING`.

## 5. Evidence model

The Phase 1 decision bundle contains:

- `phase1.adr_verifier_result`
- `phase1.adr_acceptance_index`
- `phase1.candidate_evidence_root`

Publication binds these artifacts and updates authority manifest `phase1_status`.
