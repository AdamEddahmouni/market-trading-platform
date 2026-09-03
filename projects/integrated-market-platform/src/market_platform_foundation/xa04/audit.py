"""XA-04 persistence surface audit matrix (IMP-XA-04)."""

from __future__ import annotations

PERSISTENCE_AUDIT_MATRIX: tuple[dict[str, str], ...] = (
    {
        "record_family": "canonical_instruments",
        "current_owner": "xa01.InstrumentRegistry",
        "identity": "XA01 canonical_id",
        "mutable": "append-only aliases/domains/relationships on instrument record",
        "needs_durability": "yes",
        "existing_storage": "in-memory only",
        "xa04_action": "persist InstrumentRecord snapshots",
    },
    {
        "record_family": "aliases_external_identifiers",
        "current_owner": "xa01.InstrumentRegistry",
        "identity": "scoped provider/type/value",
        "mutable": "immutable once bound",
        "needs_durability": "yes",
        "existing_storage": "in-memory alias index",
        "xa04_action": "persist within InstrumentRecord + alias lookup index",
    },
    {
        "record_family": "domain_participation",
        "current_owner": "xa01.InstrumentRegistry",
        "identity": "instrument + domain",
        "mutable": "append-only participation rows",
        "needs_durability": "yes",
        "existing_storage": "in-memory only",
        "xa04_action": "persist within InstrumentRecord",
    },
    {
        "record_family": "instrument_relationships",
        "current_owner": "xa01.InstrumentRegistry",
        "identity": "from + type + to",
        "mutable": "immutable",
        "needs_durability": "yes",
        "existing_storage": "in-memory only",
        "xa04_action": "persist within InstrumentRecord",
    },
    {
        "record_family": "fred_admitted_observations",
        "current_owner": "xa02.AdmissionRegistry",
        "identity": "XA02:OBS:*",
        "mutable": "immutable; revisions are separate observations",
        "needs_durability": "yes",
        "existing_storage": "in-memory only",
        "xa04_action": "persist AdmittedObservation",
    },
    {
        "record_family": "cftc_admission_envelopes",
        "current_owner": "xa03.PositioningAdmissionRegistry",
        "identity": "XA03:OBS:* envelope",
        "mutable": "immutable; revisions are separate envelopes",
        "needs_durability": "yes",
        "existing_storage": "in-memory only",
        "xa04_action": "persist AdmissionEnvelope with typed payload",
    },
    {
        "record_family": "cross_asset_reference_relationships",
        "current_owner": "xa02/xa03 registries",
        "identity": "relationship_id",
        "mutable": "immutable",
        "needs_durability": "yes",
        "existing_storage": "in-memory only",
        "xa04_action": "persist CrossAssetReferenceRelationship",
    },
    {
        "record_family": "static_catalog_definitions",
        "current_owner": "xa02/xa03 catalog.py constants",
        "identity": "code-defined",
        "mutable": "no",
        "needs_durability": "no",
        "existing_storage": "source code",
        "xa04_action": "bootstrap via existing catalog helpers; do not duplicate constants",
    },
    {
        "record_family": "tick_quote_trade_history",
        "current_owner": "market data providers",
        "identity": "n/a",
        "mutable": "n/a",
        "needs_durability": "no",
        "existing_storage": "provider-specific",
        "xa04_action": "explicitly out of scope",
    },
    {
        "record_family": "rt01_trace_spans",
        "current_owner": "rt01",
        "identity": "span id",
        "mutable": "telemetry",
        "needs_durability": "no",
        "existing_storage": "rt01",
        "xa04_action": "explicitly out of scope",
    },
)


def audit_matrix() -> list[dict[str, str]]:
    return [dict(row) for row in PERSISTENCE_AUDIT_MATRIX]
