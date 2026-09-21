"""HTTP adapter: observational Cboe options context on opportunity evidence."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Mapping

from ..cboe_options.opportunity_attachment import (
    attach_cboe_options_observational_context,
    attachment_to_dict,
)
from ..cboe_options.store import CboeOptionsStore
from ..intelligence.contracts.opportunity import OpportunityV1
from . import projections
from .store import ReplayStore

EVIDENCE_KEY = "cboe_options_observational_evidence"


def _cboe_options_store(store: ReplayStore) -> CboeOptionsStore | None:
    candidate = getattr(store, "cboe_options_store", None)
    return candidate if isinstance(candidate, CboeOptionsStore) else None


def _decision_time_for_cboe(store: ReplayStore) -> str | None:
    explicit = getattr(store, "cboe_options_decision_time", None)
    if explicit is not None and str(explicit).strip():
        return str(explicit).strip()
    as_of = projections.display_as_of_time(store)
    if as_of == projections.LIVE_AS_OF_UNAVAILABLE:
        return None
    text = str(as_of or "").strip()
    return text or None


def _attach_target_from_detail(
    detail: Mapping[str, Any],
    persist: OpportunityV1 | None,
) -> Any:
    if persist is not None:
        return persist
    instrument_id = str(detail.get("instrument_id") or "").strip()
    metadata = dict(detail.get("metadata") or {}) if isinstance(detail.get("metadata"), Mapping) else {}
    for key in ("family_admission_status", "asset_class"):
        if key in detail and key not in metadata:
            metadata[key] = detail[key]
    return SimpleNamespace(
        opportunity_id=str(detail.get("opportunity_id") or ""),
        scope=SimpleNamespace(instrument_ids=(instrument_id,) if instrument_id else ()),
        metadata=metadata,
    )


def overlay_cboe_options_evidence_on_detail(
    store: ReplayStore,
    detail: dict[str, Any],
    *,
    persist: OpportunityV1 | None = None,
) -> dict[str, Any]:
    """Attach observational Cboe options context when inputs and admission allow.

    Fail-closed:
    - missing ``cboe_options_store`` → detail unchanged
    - unresolved decision time → detail unchanged
    - not admitted / non-US-equity → detail unchanged (denial stays off surface)
    - empty store → ATTACHED with empty observations (no fabricated OI/volume)
    """

    cboe_store = _cboe_options_store(store)
    if cboe_store is None:
        return detail
    decision_time = _decision_time_for_cboe(store)
    if decision_time is None:
        return detail

    target = _attach_target_from_detail(detail, persist)
    attachment = attach_cboe_options_observational_context(
        target,
        store=cboe_store,
        decision_time=decision_time,
    )
    if attachment.disposition != "ATTACHED":
        return detail

    merged = dict(detail)
    merged[EVIDENCE_KEY] = attachment_to_dict(attachment)
    return merged


__all__ = [
    "EVIDENCE_KEY",
    "overlay_cboe_options_evidence_on_detail",
]
