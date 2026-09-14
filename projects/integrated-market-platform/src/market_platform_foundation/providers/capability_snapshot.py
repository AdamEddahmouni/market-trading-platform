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
        role = CampaignRole.COMPARATOR_ONLY
        access = CapabilityAccessState.CATALOGED
        support = CapabilitySupportLevel.KNOWN_SUPPORTED
        capabilities.append(
            ProviderCapabilityEntry(
                "PAPER_EXECUTION",
                CapabilitySupportLevel.KNOWN_SUPPORTED,
                access_state=CapabilityAccessState.CATALOGED,
                notes="stdlib paper-host urllib only; live api.alpaca.markets unauthorized; alpaca SDK import remains prohibited",
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


def _latest_ftep_moomoo_probe_path(root: Path) -> Path | None:
    probe_dir = root / "artifacts/ftep-v1-activation"
    if not probe_dir.is_dir():
        return None
    candidates = sorted(
        probe_dir.glob("provider-probe-moomoo-capability-*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else None


def _access_from_probe_capability(row: Mapping[str, Any]) -> CapabilityAccessState:
    if row.get("verified_receiving"):
        return CapabilityAccessState.SAMPLE_VERIFIED
    if row.get("account_entitled") or row.get("entitled"):
        return CapabilityAccessState.ENTITLED
    if row.get("runtime_tested"):
        return CapabilityAccessState.CONFIGURED
    return CapabilityAccessState.CATALOGED


def _load_frozen_activation_manifest(root: Path, campaign_slug: str) -> dict[str, Any] | None:
    path = root / f"artifacts/forward-test-campaigns/{campaign_slug}/ACTIVATION_MANIFEST.json"
    if not path.is_file():
        return None
    try:
        payload = _load_json(path)
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    status = str(payload.get("activation_status") or payload.get("status") or "").upper()
    if status != "FROZEN":
        return None
    return payload


def _apply_frozen_campaign_binding_overlay(
    providers: list[ProviderCapabilityRecord],
    *,
    repository_root: Path,
    sources: list[dict[str, str]],
) -> list[ProviderCapabilityRecord]:
    """Promote authority provider to CAMPAIGN_BOUND when a frozen manifest binds market data."""

    manifest = _load_frozen_activation_manifest(repository_root, "FTEP-V1-002")
    if manifest is None:
        return providers
    bindings = manifest.get("market_data_bindings")
    if not isinstance(bindings, dict):
        return providers
    authority = bindings.get("authority")
    if not isinstance(authority, dict):
        return providers
    provider_id = str(authority.get("provider_id") or "MOOMOO").upper()
    capability_id = str(authority.get("capability_id") or "US_EQUITY_L1")
    manifest_path = (
        "artifacts/forward-test-campaigns/FTEP-V1-002/ACTIVATION_MANIFEST.json"
    )
    fingerprint = str(
        manifest.get("manifest_fingerprint") or manifest.get("fingerprint") or ""
    ).upper()
    evidence = tuple(
        item
        for item in (
            manifest_path,
            f"campaign_id={manifest.get('campaign_id')}",
            f"fingerprint={fingerprint}" if fingerprint else "",
        )
        if item
    )
    sources.append({"path": manifest_path, "role": "ftep_v1_002_frozen_campaign_binding"})

    updated: list[ProviderCapabilityRecord] = []
    for record in providers:
        if record.provider_id != provider_id:
            updated.append(record)
            continue
        cap_rows: list[ProviderCapabilityEntry] = []
        for entry in record.capabilities:
            if entry.capability_id == capability_id:
                cap_rows.append(
                    ProviderCapabilityEntry(
                        entry.capability_id,
                        entry.support_level,
                        access_state=CapabilityAccessState.CAMPAIGN_BOUND,
                        notes="Campaign-bound at FTEP-V1-002 manifest freeze (OD-11).",
                    )
                )
            else:
                cap_rows.append(entry)
        updated.append(
            ProviderCapabilityRecord(
                provider_id=record.provider_id,
                display_name=record.display_name,
                access_state=CapabilityAccessState.CAMPAIGN_BOUND,
                campaign_role=CampaignRole.AUTHORITY,
                support_level=record.support_level,
                capability_contract_id=record.capability_contract_id,
                observed_at=str(manifest.get("frozen_at") or record.observed_at or ""),
                dimensions=record.dimensions,
                capabilities=tuple(cap_rows),
                verification_evidence=evidence,
                notes="Frozen activation manifest campaign binding overlay.",
            )
        )
    return updated


def _apply_ftep_moomoo_probe_overlay(
    providers: list[ProviderCapabilityRecord],
    *,
    repository_root: Path,
    sources: list[dict[str, str]],
) -> list[ProviderCapabilityRecord]:
    probe_path = _latest_ftep_moomoo_probe_path(repository_root)
    if probe_path is None:
        return providers
    payload = _load_json(probe_path)
    capabilities = payload.get("capabilities")
    if not isinstance(capabilities, dict):
        return providers

    rel = str(probe_path.relative_to(repository_root)).replace("\\", "/")
    sources.append({"path": rel, "role": "ftep_moomoo_probe_overlay"})

    updated: list[ProviderCapabilityRecord] = []
    for record in providers:
        if record.provider_id != "MOOMOO":
            updated.append(record)
            continue
        cap_rows: list[ProviderCapabilityEntry] = []
        for entry in record.capabilities:
            probe_row = capabilities.get(entry.capability_id)
            if not isinstance(probe_row, dict):
                cap_rows.append(entry)
                continue
            support = (
                CapabilitySupportLevel.KNOWN_UNSUPPORTED
                if probe_row.get("provider_supports") is False
                else CapabilitySupportLevel.KNOWN_SUPPORTED
            )
            if probe_row.get("entitled") is False and probe_row.get("runtime_tested"):
                support = CapabilitySupportLevel.KNOWN_SUPPORTED
            cap_rows.append(
                ProviderCapabilityEntry(
                    entry.capability_id,
                    support,
                    access_state=_access_from_probe_capability(probe_row),
                    notes=str(probe_row.get("reason_code") or probe_row.get("notes") or "")[:200],
                )
            )
        provider_access = max(
            (row.access_state or CapabilityAccessState.CATALOGED for row in cap_rows),
            key=lambda state: list(CapabilityAccessState).index(state),
            default=CapabilityAccessState.CATALOGED,
        )
        updated.append(
            ProviderCapabilityRecord(
                provider_id=record.provider_id,
                display_name=record.display_name,
                access_state=provider_access,
                campaign_role=record.campaign_role,
                support_level=record.support_level,
                capability_contract_id=record.capability_contract_id,
                observed_at=str(payload.get("probe_timestamp") or payload.get("tested_at") or ""),
                dimensions=record.dimensions,
                capabilities=tuple(cap_rows),
                verification_evidence=(rel,),
                notes="Overlay from dated FTEP operator probe receipt.",
            )
        )
    return updated


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

    providers = _apply_ftep_moomoo_probe_overlay(
        providers,
        repository_root=root,
        sources=sources,
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
