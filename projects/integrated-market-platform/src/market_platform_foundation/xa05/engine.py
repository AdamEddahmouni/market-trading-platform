"""XA-05 state construction from XA catalog evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from market_platform_foundation.xa01.enums import AnalyticalDomain
from market_platform_foundation.xa02.catalog import ADMITTED_RATES_SERIES
from market_platform_foundation.xa02.contracts import AdmittedObservation, AdmissionEnvelope
from market_platform_foundation.xa03.catalog import ADMITTED_POSITIONING_MARKETS
from market_platform_foundation.xa04.repository import CrossAssetCatalogRepository

from .classifiers import (
  FreshnessClassifierConfig,
  PolicyRateClassifierConfig,
  PositioningClassifierConfig,
  YieldCurveClassifierConfig,
  classify_data_freshness,
  classify_policy_rate,
  classify_positioning_concentration,
  classify_yield_curve,
  resolve_classifier_version,
)
from .contracts import (
  CrossAssetStrategicState,
  DimensionClassification,
  StateCompleteness,
  dimension_to_dict,
)
from .enums import EpistemicClass, EvidenceAvailabilityStatus, StateDimensionId
from .errors import Xa05Error, Xa05ErrorCode
from .provenance import (
  build_reproducibility_metadata,
  derive_state_id,
  envelope_evidence_reference,
  scalar_evidence_reference,
)


@dataclass(frozen=True, slots=True)
class StateConstructionConfig:
  yield_curve_classifier_version: str = "imp-xa05-yield-curve-v1"
  policy_rate_classifier_version: str = "imp-xa05-policy-rate-v1"
  positioning_classifier_version: str = "imp-xa05-positioning-v1"
  freshness_classifier_version: str = "imp-xa05-freshness-v1"

  def classifier_versions(self) -> dict[str, str]:
    return {
      "yield_curve": self.yield_curve_classifier_version,
      "policy_rate": self.policy_rate_classifier_version,
      "positioning": self.positioning_classifier_version,
      "freshness": self.freshness_classifier_version,
    }

  def validate(self) -> None:
    for version in self.classifier_versions().values():
      resolve_classifier_version(version)


class CrossAssetStateEngine:
  """Deterministic, provenance-aware strategic state constructor."""

  def __init__(self, repository: CrossAssetCatalogRepository) -> None:
    self._repository = repository

  def construct_state(
    self,
    *,
    decision_time: str,
    construction_time: str,
    config: StateConstructionConfig | None = None,
  ) -> CrossAssetStrategicState:
    if not decision_time:
      raise Xa05Error(
        Xa05ErrorCode.INVALID_DECISION_TIME,
        "decision_time is required",
        {},
      )
    active_config = config or StateConstructionConfig()
    try:
      active_config.validate()
    except ValueError as exc:
      raise Xa05Error(
        Xa05ErrorCode.UNKNOWN_CLASSIFIER_VERSION,
        str(exc),
        active_config.classifier_versions(),
      ) from exc

    scalar_rows = self._repository.query_scalar_observations_as_of(decision_time)
    envelope_rows = self._repository.query_admission_envelopes_as_of(decision_time)
    scalar_selection = _select_latest_scalar_observations(scalar_rows)
    envelope_selection = _select_latest_envelopes(envelope_rows)

    evidence_refs = tuple(
      sorted(
        [
          *(scalar_evidence_reference(item.selected) for item in scalar_selection.values() if item.selected),
          *(
            envelope_evidence_reference(item.selected)
            for item in envelope_selection.values()
            if item.selected is not None
          ),
        ],
        key=lambda ref: ref.observation_id,
      )
    )
    observation_ids = tuple(ref.observation_id for ref in evidence_refs)

    yield_config = resolve_classifier_version(active_config.yield_curve_classifier_version)
    assert isinstance(yield_config, YieldCurveClassifierConfig)
    policy_config = resolve_classifier_version(active_config.policy_rate_classifier_version)
    assert isinstance(policy_config, PolicyRateClassifierConfig)
    positioning_config = resolve_classifier_version(active_config.positioning_classifier_version)
    assert isinstance(positioning_config, PositioningClassifierConfig)
    freshness_config = resolve_classifier_version(active_config.freshness_classifier_version)
    assert isinstance(freshness_config, FreshnessClassifierConfig)

    yields = {
      indicator_id: (
        None
        if indicator_id not in scalar_selection or scalar_selection[indicator_id].selected is None
        else scalar_selection[indicator_id].selected.normalized_value
      )
      for indicator_id in (
        yield_config.short_indicator_id,
        yield_config.long_indicator_id,
        "US_5Y_TREASURY_YIELD",
        "US_30Y_TREASURY_YIELD",
      )
    }
    curve_label, curve_status, curve_features = classify_yield_curve(yields, config=yield_config)
    curve_support = _supporting_scalar_refs(scalar_selection, (yield_config.short_indicator_id, yield_config.long_indicator_id))
    curve_conflict = _conflict_notes(scalar_selection, (yield_config.short_indicator_id, yield_config.long_indicator_id))

    policy_value = (
      None
      if policy_config.indicator_id not in scalar_selection
      or scalar_selection[policy_config.indicator_id].selected is None
      else scalar_selection[policy_config.indicator_id].selected.normalized_value
    )
    policy_label, policy_status, policy_features = classify_policy_rate(policy_value, config=policy_config)
    policy_support = _supporting_scalar_refs(scalar_selection, (policy_config.indicator_id,))

    positioning_item = envelope_selection.get(positioning_config.market_report_id)
    positioning_envelope = positioning_item.selected if positioning_item else None
    positioning_payload = positioning_envelope.positioning_payload if positioning_envelope else None
    positioning_label, positioning_status, positioning_features = classify_positioning_concentration(
      long_positions=None if positioning_payload is None else positioning_payload.long_positions,
      short_positions=None if positioning_payload is None else positioning_payload.short_positions,
      open_interest=None if positioning_payload is None else positioning_payload.open_interest,
      config=positioning_config,
    )
    positioning_support = (
      (envelope_evidence_reference(positioning_envelope),)
      if positioning_envelope is not None
      else ()
    )
    positioning_conflict = (
      (f"{positioning_config.market_report_id}:conflicting_revisions",)
      if positioning_item and positioning_item.conflicting
      else ()
    )

    latest_available = _latest_available_time(evidence_refs)
    freshness_label, freshness_status, freshness_features = classify_data_freshness(
      decision_time=decision_time,
      latest_available_time=latest_available,
      config=freshness_config,
    )

    participating_domains = _participating_domains(scalar_selection, envelope_selection)
    participation_dimension = DimensionClassification(
      dimension_id=StateDimensionId.CROSS_DOMAIN_PARTICIPATION,
      classification=",".join(domain.value for domain in participating_domains) or "NONE",
      definition_version="imp-xa05-domain-participation-v1",
      evidence_status=(
        EvidenceAvailabilityStatus.AVAILABLE
        if participating_domains
        else EvidenceAvailabilityStatus.INSUFFICIENT
      ),
      epistemic_class=EpistemicClass.OBSERVED_FACT,
      supporting_evidence=evidence_refs,
      numeric_features={"domain_count": float(len(participating_domains))},
    )

    dimensions = (
      DimensionClassification(
        dimension_id=StateDimensionId.RATES_CURVE_CONFIGURATION,
        classification=curve_label,
        definition_version=yield_config.version,
        evidence_status=curve_status,
        epistemic_class=EpistemicClass.MODEL_OUTPUT,
        supporting_evidence=curve_support,
        contradicting_evidence=_conflicting_scalar_refs(scalar_selection, (yield_config.short_indicator_id, yield_config.long_indicator_id)),
        numeric_features=curve_features,
        notes=curve_conflict,
      ),
      DimensionClassification(
        dimension_id=StateDimensionId.POLICY_RATE_LEVEL,
        classification=policy_label,
        definition_version=policy_config.version,
        evidence_status=policy_status,
        epistemic_class=EpistemicClass.MODEL_OUTPUT,
        supporting_evidence=policy_support,
        contradicting_evidence=_conflicting_scalar_refs(scalar_selection, (policy_config.indicator_id,)),
        numeric_features=policy_features,
        notes=_conflict_notes(scalar_selection, (policy_config.indicator_id,)),
      ),
      DimensionClassification(
        dimension_id=StateDimensionId.POSITIONING_CONCENTRATION,
        classification=positioning_label,
        definition_version=positioning_config.version,
        evidence_status=positioning_status,
        epistemic_class=EpistemicClass.MODEL_OUTPUT,
        supporting_evidence=positioning_support,
        notes=positioning_conflict,
      ),
      DimensionClassification(
        dimension_id=StateDimensionId.DATA_FRESHNESS,
        classification=freshness_label,
        definition_version=freshness_config.version,
        evidence_status=freshness_status,
        epistemic_class=EpistemicClass.MODEL_OUTPUT,
        supporting_evidence=evidence_refs,
        numeric_features=freshness_features,
      ),
      participation_dimension,
    )

    dimension_payload = [dimension_to_dict(item) for item in dimensions]
    provenance = build_reproducibility_metadata(
      decision_time=decision_time,
      classifier_versions=active_config.classifier_versions(),
      evidence_observation_ids=observation_ids,
      dimension_payload=dimension_payload,
    )
    state_id = derive_state_id(
      decision_time=decision_time,
      semantic_fingerprint_value=provenance.semantic_fingerprint,
    )
    completeness = _completeness(dimensions)
    unknowns = tuple(
      item.dimension_id.value
      for item in dimensions
      if item.evidence_status in {EvidenceAvailabilityStatus.MISSING, EvidenceAvailabilityStatus.INSUFFICIENT}
    )
    conflicts = tuple(
      f"{item.dimension_id.value}:{note}"
      for item in dimensions
      for note in item.notes
    )
    return CrossAssetStrategicState(
      state_id=state_id,
      decision_time=decision_time,
      construction_time=construction_time,
      analytical_domains=participating_domains,
      dimensions=dimensions,
      evidence_references=evidence_refs,
      completeness=completeness,
      provenance=provenance,
      unknowns=unknowns,
      conflicts=conflicts,
    )


@dataclass(frozen=True, slots=True)
class _ScalarSelection:
  selected: AdmittedObservation | None
  conflicting: tuple[AdmittedObservation, ...] = ()
  candidates: tuple[AdmittedObservation, ...] = ()


@dataclass(frozen=True, slots=True)
class _EnvelopeSelection:
  selected: AdmissionEnvelope | None
  conflicting: bool = False
  candidates: tuple[AdmissionEnvelope, ...] = ()


def _select_latest_scalar_observations(
  rows: tuple[AdmittedObservation, ...],
) -> dict[str, _ScalarSelection]:
  grouped: dict[str, list[AdmittedObservation]] = {}
  for row in rows:
    grouped.setdefault(row.canonical_indicator_id, []).append(row)
  result: dict[str, _ScalarSelection] = {}
  for indicator_id, candidates in grouped.items():
    ordered = sorted(candidates, key=lambda item: (item.available_time, item.observation_id), reverse=True)
    if not ordered:
      result[indicator_id] = _ScalarSelection(selected=None, candidates=tuple())
      continue
    latest_time = ordered[0].available_time
    at_latest = [item for item in ordered if item.available_time == latest_time]
    values = {item.normalized_value for item in at_latest}
    conflicting = tuple(at_latest) if len(values) > 1 else ()
    result[indicator_id] = _ScalarSelection(
      selected=ordered[0],
      conflicting=conflicting,
      candidates=tuple(ordered),
    )
  return result


def _select_latest_envelopes(
  rows: tuple[AdmissionEnvelope, ...],
) -> dict[str, _EnvelopeSelection]:
  grouped: dict[str, list[AdmissionEnvelope]] = {}
  for row in rows:
    grouped.setdefault(row.source_subject_id, []).append(row)
  result: dict[str, _EnvelopeSelection] = {}
  for subject_id, candidates in grouped.items():
    ordered = sorted(candidates, key=lambda item: (item.available_time, item.observation_id), reverse=True)
    if not ordered:
      result[subject_id] = _EnvelopeSelection(selected=None, candidates=tuple())
      continue
    latest_time = ordered[0].available_time
    at_latest = [item for item in ordered if item.available_time == latest_time]
    conflicting = _positioning_values_conflict(at_latest)
    result[subject_id] = _EnvelopeSelection(
      selected=ordered[0],
      conflicting=conflicting,
      candidates=tuple(ordered),
    )
  return result


def _positioning_values_conflict(rows: list[AdmissionEnvelope]) -> bool:
  signatures: set[tuple[int | None, int | None, int | None]] = set()
  for row in rows:
    payload = row.positioning_payload
    if payload is None:
      continue
    signatures.add((payload.long_positions, payload.short_positions, payload.open_interest))
  return len(signatures) > 1


def _supporting_scalar_refs(
  selection: Mapping[str, _ScalarSelection],
  indicator_ids: tuple[str, ...],
) -> tuple:
  from .contracts import EvidenceReference

  refs: list[EvidenceReference] = []
  for indicator_id in indicator_ids:
    item = selection.get(indicator_id)
    if item and item.selected is not None:
      refs.append(scalar_evidence_reference(item.selected))
  return tuple(refs)


def _conflicting_scalar_refs(
  selection: Mapping[str, _ScalarSelection],
  indicator_ids: tuple[str, ...],
):
  refs = []
  for indicator_id in indicator_ids:
    item = selection.get(indicator_id)
    if item and item.conflicting:
      refs.extend(scalar_evidence_reference(row) for row in item.conflicting)
  return tuple(refs)


def _conflict_notes(
  selection: Mapping[str, _ScalarSelection],
  indicator_ids: tuple[str, ...],
) -> tuple[str, ...]:
  notes: list[str] = []
  for indicator_id in indicator_ids:
    item = selection.get(indicator_id)
    if item and item.conflicting:
      notes.append(f"{indicator_id}:conflicting_revisions")
  return tuple(notes)


def _latest_available_time(refs) -> str | None:
  if not refs:
    return None
  return max(ref.available_time for ref in refs)


def _participating_domains(
  scalar_selection: Mapping[str, _ScalarSelection],
  envelope_selection: Mapping[str, _EnvelopeSelection],
) -> tuple[AnalyticalDomain, ...]:
  domains: set[AnalyticalDomain] = set()
  admitted_scalar_ids = {item.canonical_indicator_id for item in ADMITTED_RATES_SERIES}
  for indicator_id, item in scalar_selection.items():
    if indicator_id in admitted_scalar_ids and item.selected is not None:
      match = next((row for row in ADMITTED_RATES_SERIES if row.canonical_indicator_id == indicator_id), None)
      if match:
        domains.add(match.domain)
  admitted_market_ids = {item.market_report_id for item in ADMITTED_POSITIONING_MARKETS}
  for market_id, item in envelope_selection.items():
    if market_id in admitted_market_ids and item.selected is not None:
      match = next((row for row in ADMITTED_POSITIONING_MARKETS if row.market_report_id == market_id), None)
      if match:
        domains.add(match.domain)
  return tuple(sorted(domains, key=lambda item: item.value))


def _completeness(dimensions: tuple[DimensionClassification, ...]) -> StateCompleteness:
  requested = len(dimensions)
  missing = sum(1 for item in dimensions if item.evidence_status is EvidenceAvailabilityStatus.MISSING)
  conflicting = sum(1 for item in dimensions if item.evidence_status is EvidenceAvailabilityStatus.CONFLICTING)
  insufficient = sum(
    1 for item in dimensions if item.evidence_status is EvidenceAvailabilityStatus.INSUFFICIENT
  )
  populated = sum(
    1
    for item in dimensions
    if item.evidence_status
    in {
      EvidenceAvailabilityStatus.AVAILABLE,
      EvidenceAvailabilityStatus.STALE,
    }
  )
  return StateCompleteness(
    dimensions_requested=requested,
    dimensions_populated=populated,
    dimensions_missing=missing,
    dimensions_conflicting=conflicting,
    dimensions_insufficient=insufficient,
  )
