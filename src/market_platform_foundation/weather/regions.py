"""CPC region-reference parsing and explicit taxonomy identities."""

from __future__ import annotations

from .contracts import (
    WeatherReferenceObservation,
    WeatherReferenceType,
    WeatherRegionType,
)
from .quality import WeatherQualityFlag


_KNOWN_RAW_ANOMALIES = {("VT", "8", "MOUNTAIN")}


def region_identity(
    taxonomy: str,
    region_type: WeatherRegionType | str,
    region_id: str,
) -> tuple[str, str, str]:
    """Return a taxonomy-qualified identity; CPC and EIA never alias implicitly."""

    type_value = region_type.value if isinstance(region_type, WeatherRegionType) else str(region_type)
    return taxonomy.upper(), type_value.upper(), region_id.upper()


def parse_cpc_regions(
    text: str,
    *,
    available_time: str,
    source_file_id: str = "",
    reference_version: str = "CPC_REGIONS_2014_02_07",
    content_hash: str = "",
    retrieved_time: str = "",
    ingested_time: str = "",
    provenance_ref: str = "",
) -> tuple[WeatherReferenceObservation, ...]:
    """Preserve CPC's raw state-to-Census-division mappings verbatim.

    In particular, the published Vermont-to-Mountain row is flagged and is not
    silently rewritten to a canonical Census mapping.
    """

    lines = [line.strip() for line in text.replace("\r", "\n").splitlines() if line.strip()]
    if not lines:
        raise ValueError("CPC region payload is empty")
    expected = ["ST", "State", "Census Division ID", "Census Division Name"]
    if [cell.strip() for cell in lines[0].split("|")] != expected:
        raise ValueError("Unexpected CPC state/Census-division region header")
    references: list[WeatherReferenceObservation] = []
    for line in lines[1:]:
        cells = [cell.strip() for cell in line.split("|")]
        if len(cells) != 4:
            raise ValueError("CPC region row does not match its header")
        state_id, state_name, division_id, division_name = cells
        is_anomaly = (state_id, division_id, division_name) in _KNOWN_RAW_ANOMALIES
        flags = (
            (WeatherQualityFlag.SOURCE_REGION_MAPPING_ANOMALY.value,)
            if is_anomaly
            else ()
        )
        references.append(
            WeatherReferenceObservation(
                reference_type=WeatherReferenceType.REGION_CROSSWALK,
                reference_id=f"CPC_STATE_CENSUS_DIVISION:{state_id}",
                reference_version=reference_version,
                available_from=available_time,
                source="cpc",
                source_product="CPC_STATES_CONUS_CENSUS_DIVISIONS",
                payload={
                    "state_name": state_name,
                    "raw_census_division_id": division_id,
                    "raw_census_division_name": division_name,
                    "corrected_census_division_id": None,
                    "corrected_census_division_name": None,
                    "source_file_id": source_file_id,
                },
                region_type=WeatherRegionType.STATE,
                region_id=state_id,
                content_hash=content_hash,
                retrieved_time=retrieved_time,
                ingested_time=ingested_time,
                quality_flags=flags,
                provenance_ref=provenance_ref or (f"cpc:{source_file_id}" if source_file_id else ""),
                predictive=False,
            )
        )
    return tuple(references)


__all__ = ["parse_cpc_regions", "region_identity"]
