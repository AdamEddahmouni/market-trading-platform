# Phase 8 — deterministic end-to-end acceptance (design spec)

**Status:** Approved for implementation  
**Spec date:** 2026-08-17  
**Scope:** Phase 8 only — deterministic, network-denied end-to-end acceptance on the admitted equity intraday fixture  
**Prerequisites:** Phase 0 `PASS` through Phase 7 `PASS`

## 1. Purpose

Prove one deterministic, network-denied, end-to-end run from admitted fixture ingestion
through strategy evaluation, independent risk, conservative simulation, and exact
accounting — producing a terminal acceptance bundle that satisfies `AE-001` on the
narrowed foundation milestone authorized by `ADR-DATA-001`.

## 2. In scope

- Single orchestrated pipeline chaining Phases 3→7 on `ADMITTED-SHORTSQ-BIYA-BARS-001`
- Terminal acceptance bundle with input manifests, canonical events, features,
  strategy evaluations, intents, risk decisions, orders, fills, ledger,
  reconciliation, attribution, assertion results, and run-root hash
- Rollup verifier (`ROLLUP-001`): all applicable Revision 1 §17.5 foundation
  assertions resolve to `PASS` via published phase bundles or documented proxies
- `AE-001`: terminal `COMPLETE` bundle; all referenced hashes resolve
- `DET-001`: two network-denied runs produce identical end-to-end run-root SHA-256
- `SAFE-003`: network-denied end-to-end run passes
- Limitations report explicitly documenting ES deferral and admitted-capability boundaries
- Adversarial fixtures for incomplete bundle and hash mismatch
- Postreview gate + `phase8.pass_publication`

## 3. Out of scope

- ES futures session or `DF-001`/`DF-002` for ES (remains `BLOCKED`)
- New feature, strategy, risk, or execution semantics
- Research UI, broker adapters, whale ingestion, or LLM integration
- Any capability upgrade beyond the admitted fixture manifest

## 4. ES milestone reconciliation

Revision 1 §17.6 and §24 item 2 originally required an ES session. `ADR-DATA-001`
and Phase 0A narrowed the admitted fixture to non-ES equity intraday bars. Phase 8
completes the **narrowed foundation milestone** — ES acceptance is **deferred**, not
waived. The limitations report must cite this explicitly.

## 5. Completion definition

Phase 8 is complete when the end-to-end pipeline passes on the admitted fixture,
`AE-001`, `DET-001`, `SAFE-003`, and `ROLLUP-001` all pass, determinism is proven
under network denial, and `phase8.pass_publication` is published.
