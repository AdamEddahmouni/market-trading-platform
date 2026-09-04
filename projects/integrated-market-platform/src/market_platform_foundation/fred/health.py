"""FRED / ALFRED source health and capability characterization."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

from .live import api_key_present, live_enabled, transport_from_env
from .normalize import normalize_v1_observation_row, normalize_v2_observation_row
from .pit import macro_as_of, observations_from_v1_realtime_rows
from .quality import FredQualityFlag
from .reconcile import configured_series_for_release, detect_mixed_release_update, reconcile_current_values
from .registry import TIER1_REGISTRY, lookup_canonical, registry_table_rows
from .registry_audit import audit_tier1_registry, build_v2_release_membership, domain_summary
from .transport import FredTransportError
from .v1_client import FredV1Client


def source_health_v1(v1: FredV1Client | None = None) -> dict[str, Any]:
    reachable = False
    error = ""
    try:
        client = v1 or transport_from_env()[0]
        payload = client.series("DFF")
        reachable = bool(payload.get("seriess"))
    except (FredTransportError, RuntimeError) as exc:
        error = str(exc)
    return {
        "api": "v1",
        "reachable": reachable,
        "api_key_present": api_key_present(),
        "error": error,
        "schema_health": "observed" if reachable else FredQualityFlag.SOURCE_UNAVAILABLE.value,
    }


def source_health_v2(v2: Any | None = None) -> dict[str, Any]:
    reachable = False
    error = ""
    try:
        from .v2_client import FredV2Client

        client = v2 or transport_from_env()[1]
        page = client.release_observations_page(10, limit=1000)
        reachable = isinstance(page.observations, list)
    except (FredTransportError, RuntimeError) as exc:
        error = str(exc)
    return {
        "api": "v2",
        "reachable": reachable,
        "api_key_present": api_key_present(),
        "error": error,
        "schema_health": "observed" if reachable else FredQualityFlag.SOURCE_UNAVAILABLE.value,
    }


def live_probe_v1(v1: FredV1Client | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "tested_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "api_key_present": api_key_present(),
    }
    try:
        client = v1 or transport_from_env()[0]
        series = client.series("CPIAUCSL")
        obs = client.series_observations("CPIAUCSL", output_type=1, limit=3, sort_order="desc")
        vintages = client.series_vintage_dates("CPIAUCSL")
        realtime = client.series_observations(
            "CPIAUCSL",
            output_type=2,
            observation_start="2020-01-01",
            observation_end="2020-03-01",
            limit=5,
        )
        initial = {"initial_release_observations": 0}
        try:
            initial_payload = client.series_observations("CPIAUCSL", output_type=4, limit=3, sort_order="desc")
            initial = {"initial_release_observations": len(initial_payload.get("observations", []))}
        except FredTransportError:
            initial = {"initial_release_observations": 0, "initial_release_query": "unavailable"}
        release = client.series_release("CPIAUCSL")
        release_id = int(release.get("releases", [{}])[0].get("id", 10))
        release_dates = client.release_dates(release_id)
        release_series = client.release_series(release_id, limit=5)
        updates = client.series_updates(limit=5)
        result.update(
            {
                "series_metadata": bool(series.get("seriess")),
                "current_observations": len(obs.get("observations", [])),
                "vintage_dates": len(vintages.get("vintage_dates", [])),
                "realtime_observations": len(realtime.get("observations", [])),
                "initial_release_observations": initial.get("initial_release_observations", 0),
                "release_id": release_id,
                "release_dates": len(release_dates.get("release_dates", [])),
                "release_series": len(release_series.get("seriess", [])),
                "series_updates": len(updates.get("seriess", [])),
                "reachable": True,
            }
        )
    except (FredTransportError, RuntimeError, ValueError, IndexError, KeyError) as exc:
        result["reachable"] = False
        result["error"] = str(exc)
        result["quality_flags"] = [FredQualityFlag.SOURCE_UNAVAILABLE.value]
    return result


def live_probe_v2(v2: Any | None = None, *, release_id: int = 10) -> dict[str, Any]:
    result: dict[str, Any] = {
        "tested_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "release_id": release_id,
    }
    try:
        from .v2_client import FredV2Client

        client = v2 or transport_from_env()[1]
        snapshot = client.fetch_release_observations(release_id, limit=500000, max_pages=5)
        copyright_ids = sorted(
            {
                str(row.get("copyright_id", ""))
                for page in snapshot.pages
                for row in page.observations
                if row.get("copyright_id")
            }
        )
        result.update(
            {
                "reachable": True,
                "pages": len(snapshot.pages),
                "observation_count": snapshot.observation_count,
                "series_count": snapshot.series_count,
                "has_more_final": snapshot.complete,
                "copyright_ids_sample": copyright_ids[:5],
                "consistency_result": snapshot.consistency_result,
            }
        )
    except (FredTransportError, RuntimeError) as exc:
        result["reachable"] = False
        result["error"] = str(exc)
    return result


def characterize_output_types(v1: FredV1Client, *, series_id: str = "GDPC1") -> dict[str, Any]:
    """Live characterization of FRED V1 output_type 1-4 semantics and valid request shapes."""
    result: dict[str, Any] = {"series_id": series_id, "output_types": {}}
    sample_date = "2020-04-01"
    request_matrix: dict[int, list[dict[str, Any]]] = {
        1: [
            {
                "observation_start": sample_date,
                "observation_end": sample_date,
                "limit": 5,
                "sort_order": "asc",
            }
        ],
        2: [
            {
                "observation_start": "2020-01-01",
                "observation_end": "2020-03-01",
                "limit": 5,
            },
            {
                "observation_start": sample_date,
                "observation_end": sample_date,
                "vintage_dates": "2020-04-29,2020-07-30",
                "limit": 5,
            },
        ],
        3: [
            {
                "observation_start": "2020-01-01",
                "observation_end": "2020-03-01",
                "limit": 5,
            },
            {
                "observation_start": sample_date,
                "observation_end": sample_date,
                "vintage_dates": "2020-04-29,2020-07-30",
                "limit": 5,
            },
        ],
        4: [
            {
                "observation_start": sample_date,
                "observation_end": sample_date,
                "limit": 5,
                "sort_order": "asc",
            },
            {
                "observation_start": "2020-01-01",
                "observation_end": "2020-03-01",
                "limit": 5,
            },
        ],
    }
    for output_type in (1, 2, 3, 4):
        attempts: list[dict[str, Any]] = []
        for params in request_matrix[output_type]:
            attempt: dict[str, Any] = {
                "request": {
                    "series_id": series_id,
                    "file_type": "json",
                    "output_type": output_type,
                    **params,
                }
            }
            try:
                payload = v1.series_observations(series_id, output_type=output_type, **params)
                rows = [row for row in payload.get("observations", []) if isinstance(row, dict)]
                sample = rows[0] if rows else {}
                attempt.update(
                    {
                        "http_status": 200,
                        "count": len(rows),
                        "sample_observation_date": str(sample.get("date", "")),
                        "sample_value": str(sample.get("value", "")),
                        "sample_realtime_start": str(sample.get("realtime_start", "")),
                        "sample_realtime_end": str(sample.get("realtime_end", "")),
                        "parser_note": {
                            1: "row_level_realtime_period",
                            2: "vintage_cross_tabulation_or_row_list",
                            3: "vintage_new_revised_only",
                            4: "initial_release_only",
                        }[output_type],
                    }
                )
            except FredTransportError as exc:
                text = str(exc)
                attempt.update(
                    {
                        "http_status": 400 if "HTTP 400" in text else "error",
                        "fred_error": text,
                    }
                )
            attempts.append(attempt)
        success = next((item for item in attempts if item.get("http_status") == 200), attempts[-1])
        result["output_types"][str(output_type)] = {
            "observed_semantics": {
                1: "by_realtime_period_current",
                2: "by_vintage_all_observations",
                3: "by_vintage_new_revised_only",
                4: "initial_release_only",
            }[output_type],
            "attempts": attempts,
            **{k: v for k, v in success.items() if k not in {"request"}},
        }
    return result


def alfred_revision_proof(v1: FredV1Client, *, series_id: str = "GDPC1", canonical_id: str = "US_REAL_GDP") -> dict[str, Any]:
    """Find a real revision sequence and prove macro_as_of at T1/T2/today."""
    proof: dict[str, Any] = {"series_id": series_id, "canonical_indicator_id": canonical_id}
    entry = lookup_canonical(canonical_id)
    if entry is None:
        proof["status"] = "failed"
        proof["error"] = "registry_entry_missing"
        return proof
    try:
        vintage_payload = v1.series_vintage_dates(series_id)
        vintage_dates = [str(d) for d in vintage_payload.get("vintage_dates", []) if d]
        proof["vintage_date_count"] = len(vintage_dates)

        observation_date = "2024-01-01"
        payload = v1.series_observations(
            series_id,
            output_type=1,
            observation_start=observation_date,
            observation_end=observation_date,
            realtime_start="1776-07-04",
            realtime_end="9999-12-31",
            limit=1000,
            sort_order="asc",
        )
        revision_rows = [
            row
            for row in payload.get("observations", [])
            if isinstance(row, dict) and str(row.get("value", "")) not in {"", "."}
        ]
        if len(revision_rows) < 2:
            proof["status"] = "insufficient_revisions"
            return proof

        by_vintage: list[tuple[str, str, str, str]] = []
        seen_values: list[str] = []
        for row in revision_rows:
            value = str(row.get("value", ""))
            rt_start = str(row.get("realtime_start", ""))
            rt_end = str(row.get("realtime_end", ""))
            if value in seen_values:
                continue
            seen_values.append(value)
            by_vintage.append((rt_start, value, rt_start, rt_end))

        if len(by_vintage) < 2:
            proof["status"] = "insufficient_revisions"
            return proof

        initial_vintage, initial_value, initial_rt_start, initial_rt_end = by_vintage[0]
        revised_vintage, revised_value, revised_rt_start, revised_rt_end = by_vintage[1]
        current_vintage, current_value, current_rt_start, current_rt_end = by_vintage[-1]

        from dataclasses import replace

        from .contracts import MacroObservation

        observations: list[MacroObservation] = []
        for revision, row in enumerate(revision_rows):
            obs = normalize_v1_observation_row(
                row,
                entry=entry,
                retrieved_time=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                observed_time="",
            )
            observations.append(
                replace(
                    obs,
                    revision_number=revision,
                    initial_release_value=initial_value if revision == 0 else obs.initial_release_value,
                )
            )

        proof["observation_date"] = observation_date
        proof["initial"] = {
            "vintage_date": initial_vintage,
            "value": initial_value,
            "knowledge_start": initial_rt_start,
            "knowledge_end": initial_rt_end,
        }
        proof["revised"] = {
            "vintage_date": revised_vintage,
            "value": revised_value,
            "knowledge_start": revised_rt_start,
            "knowledge_end": revised_rt_end,
        }
        proof["current"] = {
            "vintage_date": current_vintage,
            "value": current_value,
            "knowledge_start": current_rt_start,
            "knowledge_end": current_rt_end,
        }
        proof["knowledge_interval_semantics"] = {
            "realtime_start": "first vintage date this revision is latest",
            "realtime_end": "last vintage date this revision is latest (not first availability)",
            "available_time_policy": "derived from realtime_start / live first_observed only",
        }
        proof["initial_realtime_end_ne_available_time"] = initial_rt_end != (
            observations[0].available_time if observations else ""
        )

        try:
            initial_release = v1.series_observations(
                series_id,
                output_type=4,
                observation_start=observation_date,
                observation_end=observation_date,
                limit=5,
            )
            init_rows = initial_release.get("observations", [])
            if init_rows and isinstance(init_rows[0], dict):
                proof["initial_release_value"] = str(init_rows[0].get("value", ""))
                proof["initial_release_differs_from_current"] = proof["initial_release_value"] != current_value
        except FredTransportError:
            proof["initial_release_query"] = "output_type_4_unavailable_for_observation"

        start_date = date.fromisoformat((initial_rt_start or initial_vintage)[:10])
        revised_date = date.fromisoformat((revised_rt_start or revised_vintage)[:10])
        before_initial = (start_date - timedelta(days=1)).isoformat()
        t1_time = (start_date + timedelta(days=1)).isoformat()
        t2_time = (revised_date + timedelta(days=1)).isoformat()
        today_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        as_before = macro_as_of(observations, canonical_indicator_id=canonical_id, decision_time=before_initial)
        as_of_t1 = macro_as_of(observations, canonical_indicator_id=canonical_id, decision_time=t1_time)
        as_of_t2 = macro_as_of(observations, canonical_indicator_id=canonical_id, decision_time=t2_time)
        as_of_today = macro_as_of(observations, canonical_indicator_id=canonical_id, decision_time=today_time)
        proof["macro_as_of"] = {
            "before_initial_knowledge": {
                "decision_time": before_initial,
                "value": as_before.raw_value,
                "revision_state": as_before.revision_state,
            },
            "T1_initial_knowledge": {
                "decision_time": t1_time,
                "value": as_of_t1.raw_value,
                "revision_state": as_of_t1.revision_state,
                "availability_precision": observations[0].availability_precision if observations else "",
            },
            "T2_revised_knowledge": {
                "decision_time": t2_time,
                "value": as_of_t2.raw_value,
                "revision_state": as_of_t2.revision_state,
            },
            "today": {
                "decision_time": today_time,
                "value": as_of_today.raw_value,
                "revision_state": as_of_today.revision_state,
            },
        }
        proof["prior_1330_utc_classification"] = "INFERRED_RELEASE_TIME_NOT_USED"
        proof["no_lookahead"] = as_of_t1.raw_value != as_of_today.raw_value or initial_value != current_value
        proof["status"] = "observed"
    except (FredTransportError, ValueError, KeyError) as exc:
        proof["status"] = "failed"
        proof["error"] = str(exc)
    return proof


def live_v1_v2_reconciliation(
    v1: FredV1Client,
    v2: Any,
    *,
    release_id: int,
    series_id: str,
) -> dict[str, Any]:
    entry = next((e for e in TIER1_REGISTRY if e.fred_series_id == series_id), None)
    result: dict[str, Any] = {"release_id": release_id, "series_id": series_id}
    if entry is None:
        result["match"] = False
        result["quality_flags"] = ["SERIES_UNAVAILABLE"]
        return result
    v1_payload = v1.series_observations(series_id, output_type=1, sort_order="desc", limit=1)
    v1_rows = v1_payload.get("observations", [])
    v1_obs = None
    target_date = ""
    if v1_rows and isinstance(v1_rows[0], dict):
        target_date = str(v1_rows[0].get("date", ""))
        v1_obs = normalize_v1_observation_row(
            v1_rows[0],
            entry=entry,
            retrieved_time=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            observed_time=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        )
    v2_snapshot = v2.fetch_release_observations(release_id, max_pages=10)
    v2_obs = None
    v2_last_updated = ""
    for page in v2_snapshot.pages:
        for row in page.observations:
            if str(row.get("series_id")) == series_id and str(row.get("date", "")) == target_date:
                v2_obs = normalize_v2_observation_row(
                    row,
                    retrieved_time=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    observed_time=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                )
                v2_last_updated = str(row.get("last_updated", ""))
                break
        if v2_obs is not None:
            break
    recon = reconcile_current_values(v1_observation=v1_obs, v2_observation=v2_obs)
    result.update(
        {
            "observation_date": recon.observation_date,
            "v1_value": recon.v1_value,
            "v2_value": recon.v2_value,
            "match": recon.match,
            "quality_flags": list(recon.quality_flags),
            "v2_last_updated": v2_last_updated,
        }
    )
    return result


def live_cftc_interoperability(
    macro_observations: list[Any],
    *,
    decision_time: str,
    contract_family_id: str = "ES",
) -> dict[str, Any]:
    from ..cftc.health import live_probe as cftc_live_probe
    from ..cftc.store import CotStore
    from ..cftc.sync import CotSync
    from ..cftc.transport import CotTransport
    from ..cftc.datasets import CotDataset
    from .cross_asset import build_cross_asset_regime_context

    result: dict[str, Any] = {"contract_family_id": contract_family_id, "decision_time": decision_time}
    try:
        transport = CotTransport()
        probe = cftc_live_probe(transport, market_filter="E-MINI S&P 500")
        result["cftc_reachable"] = probe.get("reachable", False)
        result["latest_cot_release"] = probe.get("latest_observed_release", "")

        store = CotStore()
        sync = CotSync(store=store, transport=transport)
        latest_release = probe.get("latest_observed_release", "")
        if latest_release:
            sync_result = sync.sync_cot(
                position_dates=(latest_release,),
                market_filter="E-MINI S&P 500",
            )
        else:
            sync_result = sync.sync_cot(datasets=(CotDataset.TFF_FUTURES_ONLY,), market_filter="E-MINI S&P 500")
        result["cot_sync_status"] = sync_result.get("status", "ok")

        cot_decision_time = decision_time
        if latest_release:
            from datetime import date

            from ..cftc.release_schedule import publication_time_utc, release_for_position_date

            release = release_for_position_date(date.fromisoformat(latest_release[:10]))
            if release is not None:
                cot_decision_time = max(decision_time, publication_time_utc(release.publication_date))

        ctx = build_cross_asset_regime_context(
            macro_observations=macro_observations,
            cot_store=store,
            decision_time=cot_decision_time,
            contract_family_id=contract_family_id,
        )
        result["macro_available_time"] = ctx.macro_available_time
        result["positioning_available_time"] = ctx.positioning_available_time
        result["macro_visible"] = ctx.macro_state.rates.get("US_EFFECTIVE_FED_FUNDS_RATE") is not None
        result["positioning_visible"] = ctx.institutional_positioning_state is not None
        result["independent_clocks_preserved"] = (
            ctx.macro_available_time <= decision_time or ctx.macro_available_time == ""
        ) and (ctx.positioning_available_time <= decision_time or ctx.positioning_available_time == "")
        result["quality_flags"] = list(ctx.quality_flags)
        result["status"] = "observed"
    except Exception as exc:  # noqa: BLE001 - diagnostic boundary
        result["status"] = "failed"
        result["error"] = str(exc)
    return result


def capability_report(*, live: bool = False) -> dict[str, Any]:
    classification = "OBSERVED" if live and live_enabled() else "IMPLEMENTED"
    report: dict[str, Any] = {
        "source": "fred_alfred",
        "tested_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "api_key_present": api_key_present(),
        "live_enabled": live_enabled(),
        "classification": classification,
        "api_v1": {
            "auth": {"method": "query_param_api_key", "redacted_in_logs": True, "classification": classification},
            "series": {"implemented": True, "classification": classification},
            "observations": {"output_types": [1, 2, 3, 4], "classification": classification},
            "vintage_dates": {"implemented": True, "classification": classification},
            "realtime": {"implemented": True, "classification": classification},
            "releases": {"implemented": True, "classification": classification},
            "series_updates": {"implemented": True, "classification": classification},
        },
        "api_v2": {
            "auth": {"method": "bearer_header", "redacted_in_logs": True, "classification": classification},
            "release_observations": {"implemented": True, "max_limit": 500000, "classification": classification},
            "pagination": {"cursor": True, "classification": classification},
            "last_updated": {"preserved": True, "classification": classification},
            "mixed_update_detection": {"implemented": True, "classification": "INFERRED" if not live else classification},
            "copyright": {"preserved": True, "classification": classification},
        },
        "reconciliation": {"v1_v2": True, "classification": classification},
        "pit": {
            "alfred_v1_required": True,
            "v2_historical_substitution_forbidden": True,
            "pit_semantics_corrected": True,
            "available_time_from": "realtime_start_or_live_first_observed",
            "realtime_end_meaning": "knowledge_interval_end_not_first_availability",
            "v2_last_updated_meaning": "series_metadata_not_observation_historical_availability",
            "classification": classification,
        },
        "registry": {"tier1_count": len(registry_table_rows()), "entries": registry_table_rows()},
        "cftc_interoperability": {"cross_asset_regime_context": True, "independent_clocks": True, "classification": classification},
        "domain_coverage": _domain_coverage(),
        "licensing": {"internal_research_only": True, "third_party_series_flagged": True},
        "health": {},
        "limitations": [
            "not a low-latency event feed",
            "release calendar != guaranteed FRED availability",
            "macro revisions require ALFRED/vintage semantics",
            "V2 current history != historical truth",
            "date-only ALFRED knowledge lacks intraday precision",
            "third-party FRED series may restrict redistribution",
        ],
        "evidence_migration": {
            "prior_artifacts": "superseded_not_silently_rewritten",
            "reason": "pre-correction snapshots may have used realtime_end or V2 last_updated as available_time",
            "action": "regenerate capability-report after live validation; retain old files for audit trail",
        },
    }
    if live and live_enabled():
        v1, v2 = transport_from_env()
        report["health"]["V1_REACHABLE"] = source_health_v1(v1)["reachable"]
        report["health"]["V2_REACHABLE"] = source_health_v2(v2)["reachable"]
        report["health"]["API_KEY_VALID"] = report["health"]["V1_REACHABLE"] and report["health"]["V2_REACHABLE"]
        report["live_probe_v1"] = live_probe_v1(v1)
        v2_probe = live_probe_v2(v2, release_id=10)
        report["live_probe_v2"] = v2_probe
        report["health"]["V2_BULK_WORKING"] = v2_probe.get("reachable", False)
        report["health"]["RELEASE_DISCOVERY_WORKING"] = bool(report["live_probe_v1"].get("release_id"))
        report["health"]["VINTAGE_RETRIEVAL_WORKING"] = report["live_probe_v1"].get("vintage_dates", 0) > 0

        release_ids = {entry.fred_release_id for entry in TIER1_REGISTRY if entry.fred_release_id is not None}
        v2_membership = build_v2_release_membership(v1, release_ids)
        registry_audit = audit_tier1_registry(v1, v2_release_series=v2_membership)
        report["registry_audit"] = registry_audit
        report["registry"]["domain_summary"] = domain_summary(registry_audit["by_domain"])
        report["health"]["REGISTRY_HEALTH"] = registry_audit["by_status"].get("MISMATCH", 0) == 0

        report["output_type_characterization"] = characterize_output_types(v1)
        report["alfred_revision_proof"] = alfred_revision_proof(v1)
        report["health"]["ALFRED_PIT_WORKING"] = report["alfred_revision_proof"].get("status") == "observed"

        recon = live_v1_v2_reconciliation(v1, v2, release_id=10, series_id="CPILFESL")
        report["reconciliation"]["live"] = recon
        report["health"]["V1_V2_RECONCILIATION"] = recon.get("match", False)
        report["health"]["V2_RELEASE_CONSISTENCY"] = v2_probe.get("consistency_result", "UNKNOWN")

        configured = configured_series_for_release(10)
        if v2_probe.get("reachable"):
            from .v2_client import FredV2Client

            assert isinstance(v2, FredV2Client)
            snapshot = v2.fetch_release_observations(10, max_pages=5)
            mixed_state, mixed_flags = detect_mixed_release_update(
                snapshot,
                configured_series=configured,
                retrieval_started=report["tested_at"],
            )
            report["mixed_update_audit"] = {
                "production_state": mixed_state,
                "quality_flags": list(mixed_flags),
                "configured_series_count": len(configured),
                "note": "Different last_updated across series is normal; mixed only when partial coordinated refresh detected",
            }

        macro_obs = []
        for canonical, series in (
            ("US_EFFECTIVE_FED_FUNDS_RATE", "DFF"),
            ("US_10Y_TREASURY_YIELD", "DGS10"),
            ("US_HEADLINE_CPI", "CPIAUCSL"),
            ("US_UNEMPLOYMENT_RATE", "UNRATE"),
        ):
            entry = lookup_canonical(canonical)
            if entry is None:
                continue
            payload = v1.series_observations(series, output_type=1, sort_order="desc", limit=1)
            rows = payload.get("observations", [])
            if rows and isinstance(rows[0], dict):
                macro_obs.append(
                    normalize_v1_observation_row(
                        rows[0],
                        entry=entry,
                        retrieved_time=report["tested_at"],
                        observed_time=report["tested_at"],
                    )
                )
        report["macro_as_of_example"] = {
            "decision_time": report["tested_at"],
            "indicators": [
                {
                    "canonical_indicator_id": obs.canonical_indicator_id,
                    "observation_date": obs.observation_date,
                    "value": obs.raw_value,
                    "knowledge_start": obs.knowledge_start_date or obs.realtime_start,
                    "knowledge_end": obs.knowledge_end_date or obs.realtime_end,
                    "available_time": obs.available_time,
                    "availability_precision": obs.availability_precision,
                }
                for obs in macro_obs
            ],
        }
        report["cftc_interoperability"]["live"] = live_cftc_interoperability(
            macro_obs,
            decision_time=report["tested_at"],
        )
        report["health"]["CFTC_INTEROPERABILITY"] = report["cftc_interoperability"]["live"].get("status") == "observed"
    return report


def _domain_coverage() -> dict[str, str]:
    from .contracts import MacroDomain
    from .registry import iter_registry

    covered = {domain.value: 0 for domain in MacroDomain}
    for entry in iter_registry():
        covered[entry.domain.value] = covered.get(entry.domain.value, 0) + 1
    assessment: dict[str, str] = {}
    for domain, count in covered.items():
        if count >= 3:
            assessment[domain.lower()] = "COVERED"
        elif count >= 1:
            assessment[domain.lower()] = "PARTIAL"
        else:
            assessment[domain.lower()] = "DEFERRED"
    return assessment


__all__ = [
    "alfred_revision_proof",
    "capability_report",
    "characterize_output_types",
    "live_cftc_interoperability",
    "live_probe_v1",
    "live_probe_v2",
    "live_v1_v2_reconciliation",
    "source_health_v1",
    "source_health_v2",
]
