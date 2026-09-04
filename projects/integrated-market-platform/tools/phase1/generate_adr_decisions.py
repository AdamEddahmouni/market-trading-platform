"""Generate Phase 1 accepted ADR decision records."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DECISIONS = ROOT / "docs/superpowers/decisions"
APPROVED_AT = "2026-08-15T14:30:00.000000000Z"
PRINCIPAL = "PROJECT-PRINCIPAL-001"
REV3_SHA = "7C6AE5FC9037CA37D44CD1A2FAACD0CB821192920C46CF001541DCD2121FEB35"
REV3_PATH = (
    "docs/superpowers/specs/2026-08-14-integrated-market-platform-foundation-design-revision-3.md"
)
PHASE0A_PASS_SHA = "8992B4ACA21F2BD1F7CFF743DA2D084755100800E08F5234B0AB0B081324F0A7"
PHASE0A_PASS_PATH = "docs/superpowers/governance/2026-08-15-phase-0a-pass-publication.json"
DONOR_MATRIX_PATH = "docs/research/donors/DONOR_REUSE_MATRIX.md"
DONOR_PERMS_PATH = "docs/superpowers/governance/2026-08-14-donor-code-permissions.json"


def base_bindings() -> list[dict[str, str]]:
    return [
        {
            "effectivity_state": "EFFECTIVE",
            "logical_id": "foundation.canonical_specification.revision_3",
            "logical_path": REV3_PATH,
            "sha256": REV3_SHA,
        },
        {
            "effectivity_state": "EFFECTIVE",
            "logical_id": "phase0a.pass_publication",
            "logical_path": PHASE0A_PASS_PATH,
            "sha256": PHASE0A_PASS_SHA,
        },
    ]


def evidence_ref(logical_id: str, path: str) -> dict[str, str]:
    data = (ROOT / path).read_bytes()
    import hashlib

    return {
        "logical_id": logical_id,
        "repository_relative_path": path.replace("\\", "/"),
        "sha256": hashlib.sha256(data).hexdigest().upper(),
    }


def accepted_adr(
    *,
    adr_id: str,
    logical_id: str,
    title: str,
    decision_summary: str,
    selected_option: str,
    alternatives: list[dict[str, object]],
    consequences: dict[str, list[str]],
    evidence: list[dict[str, str]],
    extra: dict[str, object] | None = None,
) -> dict[str, object]:
    doc: dict[str, object] = {
        "adr_id": adr_id,
        "alternatives": alternatives,
        "approval": {
            "approved_at": APPROVED_AT,
            "approved_by_principal_id": PRINCIPAL,
            "approved_capacities": ["PROJECT_OWNER", "RELEASE_OWNER"],
            "approval_scope": "EXACT_HASH_PRINCIPAL_APPROVAL",
        },
        "artifact_type": "ARCHITECTURE_DECISION_RECORD",
        "authority_bindings": base_bindings(),
        "conformance_evidence": evidence,
        "consequences": consequences,
        "created_at": APPROVED_AT,
        "decision": {
            "selected_option_id": selected_option,
            "summary": decision_summary,
            "title": title,
        },
        "effectivity": {
            "current_state": "ACCEPTED",
            "decision_only": True,
            "non_authorization_statement": (
                "Acceptance records the decision only. It does not authorize "
                "Phase 2 implementation, adapters, replay, models, providers, "
                "brokers, donor execution, or network access."
            ),
        },
        "logical_id": logical_id,
        "owner_capacities": ["ARCHITECTURE_LEAD", "PROJECT_OWNER"],
        "sanitization": {
            "absolute_paths_included": False,
            "account_identifiers_included": False,
            "credential_values_included": False,
            "remote_urls_included": False,
        },
        "schema_version": "1.0.0",
        "status": "ACCEPTED",
    }
    if extra:
        doc.update(extra)
    return doc


def write_adr(filename: str, doc: dict[str, object]) -> None:
    path = DECISIONS / filename
    path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    canonical = evidence_ref(
        "foundation.canonical",
        "src/market_platform_foundation/canonical.py",
    )
    phase0a_manifest = evidence_ref(
        "phase0a.capability_manifest",
        "evidence/phase0a/C41AC9855C8307BFB54D836632061C521D0DE06DDA65D8467F53DB534F8D539C/capability_manifest.json",
    )
    phase0a_semantics = evidence_ref(
        "phase0a.source_semantics_review",
        "evidence/phase0a/C41AC9855C8307BFB54D836632061C521D0DE06DDA65D8467F53DB534F8D539C/source_semantics_review.json",
    )
    phase0a_source = evidence_ref(
        "phase0a.source_manifest",
        "evidence/phase0a/C41AC9855C8307BFB54D836632061C521D0DE06DDA65D8467F53DB534F8D539C/source_manifest.json",
    )
    donor_matrix = evidence_ref("phase1.donor_reuse_matrix", DONOR_MATRIX_PATH)
    donor_perms = evidence_ref("phase1.donor_code_permissions", DONOR_PERMS_PATH)
    offline_guard = evidence_ref(
        "foundation.offline_guard",
        "src/market_platform_foundation/offline_guard.py",
    )

    spec_resolved = [
        (
            "2026-08-15-adr-num-001-exact-numeric-representation.json",
            "ADR-NUM-001",
            "phase1.adr_num_001",
            "Exact numeric representation",
            "Authoritative prices and quantities use integer minor units plus exact rational scale; binary floats are never authoritative.",
            "NUM-OPTION-001",
            "Revision 3 section 7.1 and Revision 1 section 23 fix integer minor units with exact rational scale.",
        ),
        (
            "2026-08-15-adr-tsp-001-timestamp-precision.json",
            "ADR-TSP-001",
            "phase1.adr_tsp_001",
            "Timestamp precision",
            "Canonical timestamps are UTC epoch nanoseconds with preserved source precision; no invented sub-nanosecond precision.",
            "TSP-OPTION-001",
            "Revision 3 section 7.3 requires UTC epoch nanoseconds with preserved source precision.",
        ),
        (
            "2026-08-15-adr-id-001-event-identity.json",
            "ADR-ID-001",
            "phase1.adr_id_001",
            "Event identity and idempotency",
            "Normalized event identity is deterministic from declared identity fields; identical replay is a no-op and conflicts are quarantined.",
            "ID-OPTION-001",
            "Revision 1 section 23 fixes deterministic normalized identity and quarantine on conflict.",
        ),
        (
            "2026-08-15-adr-id-002-source-vs-normalized-identity.json",
            "ADR-ID-002",
            "phase1.adr_id_002",
            "Source-record versus normalized-event identity",
            "Fully qualified source identity and immutable normalized identity remain distinct dimensions.",
            "ID2-OPTION-001",
            "Revision 1 section 23 requires separate source and normalized identities.",
        ),
        (
            "2026-08-15-adr-seq-001-sequence-scope.json",
            "ADR-SEQ-001",
            "phase1.adr_seq_001",
            "Sequence-number scope",
            "Sequence numbers are scoped to explicit provider, venue, publisher, channel, and source-instance dimensions with reset semantics.",
            "SEQ-OPTION-001",
            "Revision 1 section 23 requires explicit sequence scope; admitted equity fixture has NULL sequence and ordering derives from bar epoch.",
        ),
        (
            "2026-08-15-adr-src-001-envelope-identity-dimensions.json",
            "ADR-SRC-001",
            "phase1.adr_src_001",
            "Venue, publisher, channel, and source-instance identity",
            "Venue, publisher, channel, and source-instance are separate envelope dimensions.",
            "SRC-OPTION-001",
            "Revision 1 section 23 fixes four separate envelope dimensions.",
        ),
        (
            "2026-08-15-adr-ord-001-ordering-tie-break.json",
            "ADR-ORD-001",
            "phase1.adr_ord_001",
            "Ordering and deterministic tie-break",
            "Replay ordering uses the Revision 3 section 7.2 tuple with versioned precedence ranks.",
            "ORD-OPTION-001",
            "Revision 1 section 23 fixes the ordering tuple and versioned precedence.",
        ),
        (
            "2026-08-15-adr-sch-001-schema-compatibility.json",
            "ADR-SCH-001",
            "phase1.adr_sch_001",
            "Schema compatibility and migrations",
            "Semantic versions, major-break rules, pure hashed migrations, and no in-place rewrite of historical evidence.",
            "SCH-OPTION-001",
            "Revision 1 section 23 fixes semantic versioning and hashed migrations.",
        ),
        (
            "2026-08-15-adr-ref-001-bitemporal-reference-data.json",
            "ADR-REF-001",
            "phase1.adr_ref_001",
            "Reference-data bitemporality",
            "Reference data carries market-valid and knowledge-valid intervals required for as-of lookup.",
            "REF-OPTION-001",
            "Revision 1 section 23 requires bitemporal reference intervals.",
        ),
        (
            "2026-08-15-adr-run-001-atomic-run-lifecycle.json",
            "ADR-RUN-001",
            "phase1.adr_run_001",
            "Atomic run lifecycle",
            "Runs follow the staged state machine with terminal marker; completed runs are immutable.",
            "RUN-OPTION-001",
            "Revision 1 section 23 fixes staged lifecycle and terminal immutability.",
        ),
        (
            "2026-08-15-adr-det-001-determinism-hashing.json",
            "ADR-DET-001",
            "phase1.adr_det_001",
            "Determinism and artifact hashing",
            "Canonical JSON encoding and ordered SHA-256 manifests define artifact identity.",
            "DET-OPTION-001",
            "Implemented in market_platform_foundation.canonical and exercised by Phase 0 evidence tooling.",
        ),
    ]

    for filename, adr_id, logical_id, title, summary, option, rationale in spec_resolved:
        ev = [canonical]
        if adr_id == "ADR-DET-001":
            ev.append(offline_guard)
        write_adr(
            filename,
            accepted_adr(
                adr_id=adr_id,
                logical_id=logical_id,
                title=title,
                decision_summary=summary,
                selected_option=option,
                alternatives=[
                    {
                        "decision": "ACCEPTED",
                        "name": option,
                        "option_id": option,
                        "tradeoffs": [rationale],
                    }
                ],
                consequences={
                    "negative": ["Conformance fixtures must be added during Phase 2 contract work."],
                    "positive": ["Specification invariant is now recorded with evidence binding."],
                },
                evidence=ev,
            ),
        )

    write_adr(
        "2026-08-15-adr-store-001-storage-engine.json",
        accepted_adr(
            adr_id="ADR-STORE-001",
            logical_id="phase1.adr_store_001",
            title="Storage layout and physical engine",
            decision_summary=(
                "Logical storage layout is fixed now; physical engines are SQLite for run metadata "
                "and manifests and DuckDB for analytical columnar datasets once Phase 2 begins. "
                "No production storage is implemented in Phase 1."
            ),
            selected_option="STORE-OPTION-002",
            alternatives=[
                {
                    "decision": "REJECTED",
                    "name": "SQLITE_ONLY",
                    "option_id": "STORE-OPTION-001",
                    "tradeoffs": [
                        "Simple offline packaging but weak analytical scan performance on multi-million-row fixtures."
                    ],
                },
                {
                    "decision": "ACCEPTED",
                    "name": "SQLITE_METADATA_DUCKDB_ANALYTICAL",
                    "option_id": "STORE-OPTION-002",
                    "tradeoffs": [
                        "Matches admitted 8MB equity fixture today while leaving room for larger analytical tables later.",
                        "Requires separate offline dependency authorization before DuckDB is introduced in Phase 2."
                    ],
                },
            ],
            consequences={
                "negative": [
                    "DuckDB dependency must be separately authorized before Phase 2 storage implementation."
                ],
                "positive": [
                    "Logical layout can be implemented without committing to a single engine for all workloads."
                ],
            },
            evidence=[phase0a_source, canonical],
        ),
    )

    write_adr(
        "2026-08-15-adr-time-001-short-squeeze-timestamp-mapping.json",
        accepted_adr(
            adr_id="ADR-TIME-001",
            logical_id="phase1.adr_time_001",
            title="Short Squeeze effective_timestamp versus canonical available_time",
            decision_summary=(
                "For Short Squeeze market-bar records, canonical available_time is the bar-end "
                "instant from provider_metadata.bar_end when present; otherwise UTC nanoseconds derived "
                "from the bar epoch suffix in source_record_id. Record-level effective_timestamp is "
                "ingestion metadata only and must not be used as market availability for bars."
            ),
            selected_option="TIME-OPTION-002",
            alternatives=[
                {
                    "decision": "REJECTED",
                    "name": "USE_EFFECTIVE_TIMESTAMP_DIRECTLY",
                    "option_id": "TIME-OPTION-001",
                    "tradeoffs": [
                        "Would assign the same ingestion timestamp to every bar in the fixture and create look-ahead risk."
                    ],
                },
                {
                    "decision": "ACCEPTED",
                    "name": "BAR_END_OR_SOURCE_RECORD_EPOCH",
                    "option_id": "TIME-OPTION-002",
                    "tradeoffs": [
                        "Preserves per-bar timing from observed provider metadata or source_record_id epoch suffix.",
                        "Requires explicit mapping table before any canonical normalization."
                    ],
                },
            ],
            consequences={
                "negative": [
                    "News and corporate-action records still require separate availability mappings before reuse."
                ],
                "positive": [
                    "Prevents ingestion-time masquerading as market availability for intraday bars."
                ],
            },
            evidence=[phase0a_semantics, phase0a_source],
        ),
    )

    write_adr(
        "2026-08-15-adr-prot-001-prototype-reuse-boundary.json",
        accepted_adr(
            adr_id="ADR-PROT-001",
            logical_id="phase1.adr_prot_001",
            title="Extract, adapt, or reimplement prototype primitives",
            decision_summary=(
                "Prototype working trees remain external. Reuse is CONCEPT_ONLY or PORT_ADAPT through "
                "independent reimplementation only after separate authorization; no direct copy, import, "
                "or execution of donor code from the governed repository."
            ),
            selected_option="PROT-OPTION-001",
            alternatives=[
                {
                    "decision": "ACCEPTED",
                    "name": "EXTERNAL_REFERENCE_WITH_SEPARATE_PORT_ADAPT_AUTH",
                    "option_id": "PROT-OPTION-001",
                    "tradeoffs": [
                        "Preserves prototype integrity and keeps governed subject offline-safe."
                    ],
                }
            ],
            consequences={
                "negative": ["Higher implementation cost than direct copy."],
                "positive": ["License, provenance, and offline boundaries remain auditable."],
            },
            evidence=[donor_matrix, donor_perms],
        ),
    )

    write_adr(
        "2026-08-15-adr-data-001-admitted-fixture-identity.json",
        accepted_adr(
            adr_id="ADR-DATA-001",
            logical_id="phase1.adr_data_001",
            title="Pinned admitted fixture and capability manifest",
            decision_summary=(
                "The admitted research fixture is ADMITTED-SHORTSQ-BIYA-BARS-001: non-pointer equity "
                "intraday JSONL read-only from the collection. ES futures session claims remain blocked."
            ),
            selected_option="DATA-OPTION-002",
            alternatives=[
                {
                    "decision": "REJECTED_FOR_CURRENT_SCOPE",
                    "name": "ES_EVENT_LEVEL_SESSION",
                    "option_id": "DATA-OPTION-001",
                    "tradeoffs": ["No lawful non-pointer ES event object is verified locally."],
                },
                {
                    "decision": "ACCEPTED",
                    "name": "EQUITY_INTRADAY_NARROWED_SCOPE",
                    "option_id": "DATA-OPTION-002",
                    "tradeoffs": [
                        "Enables foundational decisions without ES capability claims.",
                        "Revision 1 section 17.6 ES acceptance bundle remains blocked."
                    ],
                },
            ],
            consequences={
                "negative": [
                    "Sweep and CVD strategies requiring depth remain blocked.",
                    "ES end-to-end acceptance bundle cannot proceed until lawful ES bytes are procured."
                ],
                "positive": [
                    "Fixture-dependent ADRs can bind to verified non-pointer bytes and capability truth."
                ],
            },
            evidence=[phase0a_manifest, phase0a_source, phase0a_semantics],
        ),
    )

    write_adr(
        "2026-08-15-adr-strat-001-first-strategy-selection.json",
        accepted_adr(
            adr_id="ADR-STRAT-001",
            logical_id="phase1.adr_strat_001",
            title="First strategy selection and thresholds",
            decision_summary=(
                "No first strategy is selected in Phase 1. Liquidity-sweep reversal and CVD divergence "
                "remain rejected for the admitted equity OHLCV-only fixture. Strategy preregistration "
                "is deferred until a source with verified depth or trade semantics is admitted."
            ),
            selected_option="STRAT-OPTION-003",
            alternatives=[
                {
                    "decision": "REJECTED",
                    "name": "LIQUIDITY_SWEEP_REVERSAL",
                    "option_id": "STRAT-OPTION-001",
                    "tradeoffs": ["Requires verified multi-level depth semantics absent from admitted fixture."],
                },
                {
                    "decision": "REJECTED",
                    "name": "CVD_DIVERGENCE",
                    "option_id": "STRAT-OPTION-002",
                    "tradeoffs": ["Requires trade direction and tick semantics absent from admitted fixture."],
                },
                {
                    "decision": "ACCEPTED",
                    "name": "DEFER_STRATEGY_SELECTION",
                    "option_id": "STRAT-OPTION-003",
                    "tradeoffs": [
                        "Honest capability gating; no threshold may be selected from final P&L.",
                        "Phase 6 strategy work remains blocked until capability-qualified source exists."
                    ],
                },
            ],
            consequences={
                "negative": ["No preregistered strategy hypothesis exists yet."],
                "positive": ["Prevents unsupported microstructure claims on OHLCV-only data."],
            },
            evidence=[phase0a_manifest],
        ),
    )

    write_adr(
        "2026-08-15-adr-donor-001-component-disposition.json",
        accepted_adr(
            adr_id="ADR-DONOR-001",
            logical_id="phase1.adr_donor_001",
            title="Component-level donor disposition and rights",
            decision_summary=(
                "Donor reuse follows DONOR_REUSE_MATRIX classifications: PORT_ADAPT requires independent "
                "reimplementation and separate authorization; CONCEPT_ONLY permits ideas only; DO_NOT_USE "
                "rows are permanent exclusions unless new rights evidence and ADR exist."
            ),
            selected_option="DONOR-OPTION-001",
            alternatives=[
                {
                    "decision": "ACCEPTED",
                    "name": "MATRIX_GOVERNED_DISPOSITION",
                    "option_id": "DONOR-OPTION-001",
                    "tradeoffs": [
                        "Every component has explicit classification and phase gate.",
                        "DS-340W and GridIQ unresolved rights remain DO_NOT_USE."
                    ],
                }
            ],
            consequences={
                "negative": ["Matrix maintenance burden as donors evolve."],
                "positive": ["No implicit permission through absence of a row."],
            },
            evidence=[donor_matrix, donor_perms],
        ),
    )

    write_adr(
        "2026-08-15-adr-rdata-001-research-dataset-identity.json",
        accepted_adr(
            adr_id="ADR-RDATA-001",
            logical_id="phase1.adr_rdata_001",
            title="Immutable research dataset identity and fingerprint",
            decision_summary=(
                "Research datasets receive immutable identity from canonical manifest hash, schema version, "
                "member file hashes, and admission decision reference. Published datasets are append-only."
            ),
            selected_option="RDATA-OPTION-001",
            alternatives=[
                {
                    "decision": "ACCEPTED",
                    "name": "MANIFEST_ROOTED_IDENTITY",
                    "option_id": "RDATA-OPTION-001",
                    "tradeoffs": [
                        "Supports reproducible Phase 5R publication without mutable dataset aliases."
                    ],
                }
            ],
            consequences={
                "negative": ["Corrections require new dataset version, not in-place rewrite."],
                "positive": ["Training and evaluation can bind to exact dataset bytes."],
            },
            evidence=[canonical, phase0a_source],
        ),
    )

    write_adr(
        "2026-08-15-adr-pit-001-feature-label-availability.json",
        accepted_adr(
            adr_id="ADR-PIT-001",
            logical_id="phase1.adr_pit_001",
            title="Feature and label availability semantics",
            decision_summary=(
                "Feature rows may use only inputs with available_time less than or equal to the prediction "
                "cutoff. Label rows may use only outcomes strictly after the declared horizon from that cutoff. "
                "Walk-forward folds store cutoff boundaries in the run manifest."
            ),
            selected_option="PIT-OPTION-001",
            alternatives=[
                {
                    "decision": "ACCEPTED",
                    "name": "CUTOFF_BOUNDED_AVAILABILITY",
                    "option_id": "PIT-OPTION-001",
                    "tradeoffs": [
                        "Aligns with Revision 3 model-test requirements and ADR-TIME-001 bar availability mapping."
                    ],
                }
            ],
            consequences={
                "negative": ["Requires explicit availability fields on every feature input."],
                "positive": ["Leakage checks become machine-verifiable in later phases."],
            },
            evidence=[phase0a_semantics, canonical],
        ),
    )

    write_adr(
        "2026-08-15-adr-model-001-model-artifact-identity.json",
        accepted_adr(
            adr_id="ADR-MODEL-001",
            logical_id="phase1.adr_model_001",
            title="Model spec, artifact, and prediction identity",
            decision_summary=(
                "Model identity is the tuple of model spec hash, training dataset fingerprint, preprocessing "
                "state hash, random seed policy, and artifact bytes hash. Predictions record that tuple."
            ),
            selected_option="MODEL-OPTION-001",
            alternatives=[
                {
                    "decision": "ACCEPTED",
                    "name": "TUPLE_ROOTED_MODEL_IDENTITY",
                    "option_id": "MODEL-OPTION-001",
                    "tradeoffs": [
                        "Enables reproduction without conflating score, probability, and calibrated outputs."
                    ],
                }
            ],
            consequences={
                "negative": ["Higher manifest verbosity."],
                "positive": ["Canonical model evidence can be audited independently of code version alone."],
            },
            evidence=[canonical],
        ),
    )

    write_adr(
        "2026-08-15-adr-fcast-001-forecast-interface.json",
        accepted_adr(
            adr_id="ADR-FCAST-001",
            logical_id="phase1.adr_fcast_001",
            title="Forecast model interface and fallback reporting",
            decision_summary=(
                "Forecast models expose typed inputs, horizon, fallback reason codes, and null probability "
                "until calibration. Multiple model families require explicit interface version in manifests."
            ),
            selected_option="FCAST-OPTION-001",
            alternatives=[
                {
                    "decision": "ACCEPTED",
                    "name": "TYPED_INTERFACE_WITH_EXPLICIT_FALLBACK",
                    "option_id": "FCAST-OPTION-001",
                    "tradeoffs": [
                        "Prevents silent model-family mixing and unsupported probability claims."
                    ],
                }
            ],
            consequences={
                "negative": ["More boilerplate per model family."],
                "positive": ["Comparable only within declared interface version and calibration state."],
            },
            evidence=[canonical],
        ),
    )

    write_adr(
        "2026-08-15-adr-dcache-001-dataset-cache-semantics.json",
        accepted_adr(
            adr_id="ADR-DCACHE-001",
            logical_id="phase1.adr_dcache_001",
            title="Dataset cache identity and invalidation",
            decision_summary=(
                "Dataset caches are content-addressed, byte-bounded, disposable, and invalidated on source "
                "hash or schema version change. Cache hits must not weaken replay determinism."
            ),
            selected_option="DCACHE-OPTION-001",
            alternatives=[
                {
                    "decision": "ACCEPTED",
                    "name": "CONTENT_ADDRESSED_BOUNDED_CACHE",
                    "option_id": "DCACHE-OPTION-001",
                    "tradeoffs": [
                        "Supports offline replay while preventing silent stale-data reuse."
                    ],
                }
            ],
            consequences={
                "negative": ["Eviction and corruption tests required before production caching."],
                "positive": ["Cache identity is auditable separately from dataset identity."],
            },
            evidence=[canonical],
        ),
    )

    write_adr(
        "2026-08-15-adr-whale-001-institutional-evidence-vocabulary.json",
        accepted_adr(
            adr_id="ADR-WHALE-001",
            logical_id="phase1.adr_whale_001",
            title="Institutional evidence vocabulary and allowed claims",
            decision_summary=(
                "Institutional evidence uses eight families: filings, public positioning, large prints, "
                "options flow, fund or ETF flow, cross-asset context, amendments, and conflicts. Delayed "
                "filings remain delayed in replay; unknown aggressor stays unknown."
            ),
            selected_option="WHALE-OPTION-001",
            alternatives=[
                {
                    "decision": "ACCEPTED",
                    "name": "EIGHT_FAMILY_VOCABULARY_WITH_EXPLICIT_UNKNOWNNESS",
                    "option_id": "WHALE-OPTION-001",
                    "tradeoffs": [
                        "Prevents invented identity or stale evidence upgrades without provenance."
                    ],
                }
            ],
            consequences={
                "negative": ["Feature surface remains blocked until entitled sources exist."],
                "positive": ["Later whale features cannot overclaim available evidence."],
            },
            evidence=[donor_matrix],
        ),
    )

    write_adr(
        "2026-08-15-adr-llm-001-provider-neutral-inference.json",
        accepted_adr(
            adr_id="ADR-LLM-001",
            logical_id="phase1.adr_llm_001",
            title="Provider-neutral inference and no-execution authority",
            decision_summary=(
                "AI integration uses a provider-neutral inference boundary with citation-required answers, "
                "explicit abstention, and no order, risk, or execution authority. GridIQ Gemini invocation "
                "remains DO_NOT_USE as written."
            ),
            selected_option="LLM-OPTION-001",
            alternatives=[
                {
                    "decision": "ACCEPTED",
                    "name": "PROVIDER_NEUTRAL_READ_ONLY_ASSISTANT",
                    "option_id": "LLM-OPTION-001",
                    "tradeoffs": [
                        "Requires separate provider authorization and offline test doubles before any integration."
                    ],
                }
            ],
            consequences={
                "negative": ["No AI features until provider and safety ADR implementation phases."],
                "positive": ["Prevents donor provider coupling and unsupported trade authority."],
            },
            evidence=[donor_matrix, offline_guard],
        ),
    )

    # Promote existing drafts
    repo_path = DECISIONS / "2026-08-14-adr-repo-001-governed-repository-boundary.json"
    repo_doc = json.loads(repo_path.read_text(encoding="utf-8"))
    repo_doc["status"] = "ACCEPTED"
    repo_doc["effectivity"]["current_state"] = "ACCEPTED"
    repo_doc["approval"] = {
        "approved_at": APPROVED_AT,
        "approved_by_principal_id": PRINCIPAL,
        "approved_capacities": ["PROJECT_OWNER", "RELEASE_OWNER"],
        "approval_scope": "EXACT_HASH_PRINCIPAL_APPROVAL",
    }
    repo_doc["conformance_evidence"] = [
        evidence_ref(
            "phase0.repository_registration",
            "docs/superpowers/governance/2026-08-14-repository-registration.json",
        )
    ]
    repo_path.write_text(json.dumps(repo_doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    off_path = DECISIONS / "2026-08-14-adr-off-001-conformance-design.json"
    off_doc = json.loads(off_path.read_text(encoding="utf-8"))
    off_doc["status"] = "ACCEPTED"
    off_doc["effectivity"]["current_state"] = "ACCEPTED"
    off_doc["approval"] = {
        "approved_at": APPROVED_AT,
        "approved_by_principal_id": PRINCIPAL,
        "approved_capacities": ["PROJECT_OWNER", "RELEASE_OWNER"],
        "approval_scope": "EXACT_HASH_PRINCIPAL_APPROVAL",
    }
    off_doc["conformance_evidence"] = [
        offline_guard,
        evidence_ref("phase0.registry_snapshot", "manifests/phase0/registry.json"),
    ]
    off_path.write_text(json.dumps(off_doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print("generated Phase 1 ADR decisions")


if __name__ == "__main__":
    main()
