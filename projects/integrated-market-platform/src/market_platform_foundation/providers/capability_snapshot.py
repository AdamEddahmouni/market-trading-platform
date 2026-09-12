"""Deterministic capability-matrix snapshot from Wave A inventory artifacts."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from .capability_contract import (
    CapabilityAccessState,
    CapabilityDimension,
    CapabilityDimensionState,
    CapabilityMatrixSnapshot,
    CapabilitySupportLevel,
    CampaignRole,
    ProviderCapabilityEntry,
    ProviderCapabilityRecord,
    redact_mapping,
    validate_snapshot,
)

DEFAULT_WAVE_A_DIR = Path("artifacts/wave-a-findings")
SOURCE_PATHS: tuple[tuple[str, str], ...] = (
    ("artifacts/wave-a-findings/provider-inventory.json", "provider_catalog"),
    ("artifacts/wave-a-findings/finviz-moomoo-audit.json", "provider_access_finviz_moomoo"),
    ("artifacts/wave-a-findings/ibkr-tradier-alpaca-audit.json", "broker_audit_ibkr_tradier_alpaca"),
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _readiness_index(
    readiness_providers: Sequence[Mapping[str, object]], provider_key: str
) -> Mapping[str, object] | None:
    for row in readiness_providers:
        if row.get("provider") == provider_key:
            return row
    return None


def _finviz_record(audit: Mapping[str, Any]) -> ProviderCapabilityRecord:
    finviz = audit.get("providers", {}).get("finviz", {})
    classifications = finviz.get("classifications", [])
    dimensions: list[CapabilityDimension] = []
    for row in classifications:
        dim = str(row.get("dimension", ""))
        raw_state = str(row.get("state", "UNKNOWN"))
        state = _classification_to_dimension_state(raw_state)
        observed = row.get("as_of")
        if observed is None and isinstance(finviz.get("live_session"), dict):
            observed = finviz["live_session"].get("observed_at")
        dimensions.append(
            CapabilityDimension(
                dimension=dim,
                state=state,
                observed_at=str(observed) if observed else None,
                evidence_refs=tuple(str(item) for item in row.get("evidence", ())),
            )
        )
    access = CapabilityAccessState.CATALOGED
    if any(row.state == CapabilityDimensionState.STALE for row in dimensions):
        access = CapabilityAccessState.SAMPLE_VERIFIED
    return ProviderCapabilityRecord(
        provider_id=str(finviz.get("provider_id", "FINVIZ_ELITE")),
        display_name="Finviz Elite",
        access_state=access,
        campaign_role=CampaignRole.CONTEXT_ONLY,
        support_level=CapabilitySupportLevel.KNOWN_SUPPORTED,
        capability_contract_id="finviz.elite/discovery@1.0.0",
        observed_at=str(audit.get("observed_at", {}).get("end", "")) or None,
        dimensions=tuple(dimensions),
        capabilities=(
            ProviderCapabilityEntry("SCREENER_CONTEXT", CapabilitySupportLevel.KNOWN_SUPPORTED),
            ProviderCapabilityEntry("NEWS_EXPORT", CapabilitySupportLevel.KNOWN_SUPPORTED),
            ProviderCapabilityEntry("OPTIONS_CHAIN", CapabilitySupportLevel.KNOWN_SUPPORTED),
            ProviderCapabilityEntry(
                "OPTIONS_EXECUTION_DATA",
                CapabilitySupportLevel.KNOWN_UNSUPPORTED,
                notes="Probe notes: execution data not authorized",
            ),
        ),
        notes="Wave A read-only; live session UNCONFIGURED at audit time.",
    )


def _moomoo_record(audit: Mapping[str, Any]) -> ProviderCapabilityRecord:
    moomoo = audit.get("providers", {}).get("moomoo", {})
    classifications = moomoo.get("classifications", [])
    dimensions = tuple(
        CapabilityDimension(
            dimension=str(row.get("dimension", "")),
            state=_classification_to_dimension_state(str(row.get("state", "UNKNOWN"))),
            observed_at=str(row.get("as_of")) if row.get("as_of") else None,
            evidence_refs=tuple(str(item) for item in row.get("evidence", ())),
        )
        for row in classifications
    )
    access = CapabilityAccessState.CATALOGED
    stale = moomoo.get("stale_evidence", {})
    if stale.get("path"):
        access = CapabilityAccessState.SAMPLE_VERIFIED
    capabilities: list[ProviderCapabilityEntry] = [
        ProviderCapabilityEntry("US_EQUITY_L1", CapabilitySupportLevel.KNOWN_SUPPORTED),
        ProviderCapabilityEntry("US_EQUITY_DEPTH", CapabilitySupportLevel.KNOWN_SUPPORTED),
        ProviderCapabilityEntry("US_EQUITY_TICKS", CapabilitySupportLevel.KNOWN_SUPPORTED),
        ProviderCapabilityEntry(
            "US_FUTURES_QUOTE",
            CapabilitySupportLevel.UNKNOWN,
            notes="Stale probe showed entitlement gap; treat as unknown until refreshed",
        ),
    ]
    return ProviderCapabilityRecord(
        provider_id=str(moomoo.get("provider_id", "MOOMOO")),
        display_name="Moomoo OpenD",
        access_state=access,
        campaign_role=CampaignRole.AUTHORITY,
        support_level=CapabilitySupportLevel.KNOWN_SUPPORTED,
        capability_contract_id="moomoo.observational/us_equity@1.0.0",
        observed_at=str(audit.get("observed_at", {}).get("end", "")) or None,
        dimensions=dimensions,
        capabilities=tuple(capabilities),
        notes="Primary observational provider; Wave A OpenD not running at audit time.",
    )


def _classification_to_dimension_state(raw: str) -> CapabilityDimensionState:
    normalized = raw.upper().replace(" ", "_")
    aliases = {
        "UNKNOWN_THIS_SESSION": CapabilityDimensionState.UNKNOWN,
        "NOT_CONNECTED": CapabilityDimensionState.NOT_CONNECTED,
        "STALE_ACCESS_VERIFIED": CapabilityDimensionState.STALE,
        "ENTITLED_STALE": CapabilityDimensionState.STALE,
        "ACCESS_AVAILABLE": CapabilityDimensionState.VERIFIED,
        "DISABLED": CapabilityDimensionState.BLOCKED,
        "NOT_AVAILABLE_ON_AUDIT_PATHS": CapabilityDimensionState.UNSUPPORTED,
    }
    if normalized in aliases:
        return aliases[normalized]
    try:
        return CapabilityDimensionState(normalized)
    except ValueError:
        return CapabilityDimensionState.UNKNOWN


def _broker_record(
    broker_key: str,
    payload: Mapping[str, Any],
    *,
    readiness_row: Mapping[str, object] | None,
) -> ProviderCapabilityRecord:
    provider_id = str(payload.get("provider_id", broker_key))
    integration = str(payload.get("integration_level", ""))
    access = CapabilityAccessState.CATALOGED
    support = CapabilitySupportLevel.KNOWN_SUPPORTED
    role = CampaignRole.UNASSIGNED
    capabilities: list[ProviderCapabilityEntry] = []
    notes = integration

    if broker_key == "ibkr":
        role = CampaignRole.CHALLENGER
        access = CapabilityAccessState.SAMPLE_VERIFIED
        for row in payload.get("historical_canary_2026_09_09", {}).get("capabilities", ()):
            cap_id = str(row.get("capability", ""))
            result = str(row.get("result", ""))
            if "NOT_ENTITLED" in result:
                capabilities.append(
                    ProviderCapabilityEntry(
                        cap_id,
                        CapabilitySupportLevel.KNOWN_SUPPORTED,
                        access_state=CapabilityAccessState.ENTITLED,
                        notes=result,
                    )
                )
            elif "VERIFIED" in result:
                capabilities.append(
                    ProviderCapabilityEntry(
                        cap_id,
                        CapabilitySupportLevel.KNOWN_SUPPORTED,
                        access_state=CapabilityAccessState.SAMPLE_VERIFIED,
                        notes=str(row.get("note", "")),
                    )
                )
            else:
                capabilities.append(
                    ProviderCapabilityEntry(cap_id, CapabilitySupportLevel.UNKNOWN, notes=result)
                )
    elif broker_key == "tradier":
        role = CampaignRole.COMPARATOR_ONLY
        access = CapabilityAccessState.CONFIGURED
        capabilities.append(
            ProviderCapabilityEntry(
                "PAPER_EXECUTION",
                CapabilitySupportLevel.KNOWN_SUPPORTED,
                access_state=CapabilityAccessState.CATALOGED,
                notes=str(payload.get("transport_state", "FIXTURE_ONLY")),
            )
        )
    elif broker_key == "alpaca":
        role = CampaignRole.PROHIBITED
        access = CapabilityAccessState.BLOCKED
        support = CapabilitySupportLevel.KNOWN_UNSUPPORTED
        capabilities.append(
            ProviderCapabilityEntry(
                "PAPER_EXECUTION",
                CapabilitySupportLevel.KNOWN_UNSUPPORTED,
                access_state=CapabilityAccessState.BLOCKED,
            )
        )

    if readiness_row:
        gate = str(readiness_row.get("gate_state", ""))
        transport = str(readiness_row.get("transport_state", ""))
        if gate == "DISABLED" and access not in (
            CapabilityAccessState.BLOCKED,
            CapabilityAccessState.SAMPLE_VERIFIED,
        ):
            access = CapabilityAccessState.CONFIGURED
        notes = f"{notes}; readiness gate={gate} transport={transport}".strip("; ")

    return ProviderCapabilityRecord(
        provider_id=provider_id,
        display_name=provider_id.replace("_", " ").title(),
        access_state=access,
        campaign_role=role,
        support_level=support,
        capability_contract_id=f"{provider_id}/broker@1.0.0",
        capabilities=tuple(capabilities),
        notes=notes[:400],
    )


def build_capability_matrix_snapshot(
    *,
    repository_root: Path,
    wave_a_dir: Path | None = None,
    readiness_report: Mapping[str, Any] | None = None,
    observed_at: str | None = None,
) -> CapabilityMatrixSnapshot:
    """Assemble a deterministic snapshot from static Wave A artifacts."""

    root = repository_root.resolve()
    wave_dir = (wave_a_dir or root / DEFAULT_WAVE_A_DIR).resolve()
    sources: list[dict[str, str]] = []
    loaded: dict[str, Any] = {}
    for rel_path, role in SOURCE_PATHS:
        path = root / rel_path
        if not path.is_file():
            path = wave_dir / Path(rel_path).name
        if path.is_file():
            loaded[role] = redact_mapping(_load_json(path))
            sources.append({"path": str(path.relative_to(root)).replace("\\", "/"), "role": role})

    finviz_moomoo = loaded.get("provider_access_finviz_moomoo", {})
    broker_audit = loaded.get("broker_audit_ibkr_tradier_alpaca", {})
    inventory = loaded.get("provider_catalog", {})

    readiness_providers: list[Mapping[str, object]] = []
    if readiness_report is not None:
        readiness_providers = list(readiness_report.get("providers", []))

    providers: list[ProviderCapabilityRecord] = []
    if finviz_moomoo:
        providers.append(_finviz_record(finviz_moomoo))
        providers.append(_moomoo_record(finviz_moomoo))
    brokers = broker_audit.get("brokers", {})
    for key in ("ibkr", "tradier", "alpaca"):
        if key not in brokers:
            continue
        readiness_key = {
            "ibkr": "ibkr_observational",
            "tradier": "tradier_paper",
            "alpaca": "alpaca",
        }[key]
        providers.append(
            _broker_record(
                key,
                brokers[key],
                readiness_row=_readiness_index(readiness_providers, readiness_key),
            )
        )

    if inventory and not any(item["role"] == "provider_catalog" for item in sources):
        inv_path = root / "artifacts/wave-a-findings/provider-inventory.json"
        if inv_path.is_file():
            sources.append(
                {
                    "path": "artifacts/wave-a-findings/provider-inventory.json",
                    "role": "provider_catalog",
                }
            )

    providers.sort(key=lambda row: row.provider_id)
    snapshot = CapabilityMatrixSnapshot(
        observed_at=observed_at or _utc_now_iso(),
        sources=tuple(sources),
        providers=tuple(providers),
        secrets_included=False,
    )
    validate_snapshot(snapshot)
    return snapshot


def serialize_snapshot(snapshot: CapabilityMatrixSnapshot) -> str:
    """Return canonical JSON (sorted keys, trailing newline)."""

    validate_snapshot(snapshot)
    return json.dumps(redact_mapping(snapshot.to_dict()), indent=2, sort_keys=True) + "\n"
