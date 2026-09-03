"""Sanitized offline/live NOAA/NWS/CPC weather capability probe."""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.weather.cpc import parse_cpc_forecast, parse_cpc_realized  # noqa: E402
from market_platform_foundation.weather.health import capability_report  # noqa: E402
from market_platform_foundation.weather.live import live_enabled, transport_from_env  # noqa: E402
from market_platform_foundation.weather.ndfd import characterize_ndfd_metadata  # noqa: E402
from market_platform_foundation.weather.nws import NwsClient  # noqa: E402
from market_platform_foundation.weather.sync import WeatherSync  # noqa: E402

OUTPUT = ROOT / "evidence" / "weather" / "capability-report.json"
CPC_ROOT = "https://ftp.cpc.ncep.noaa.gov/htdocs/degree_days/weighted"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _last_modified(transport, fallback: str) -> str:
    value = transport.last_response_headers.get("last-modified", "")
    if not value:
        return fallback
    return parsedate_to_datetime(value).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _live_characterization(sync: WeatherSync) -> dict[str, object]:
    transport = transport_from_env()
    client = NwsClient(transport=transport)
    retrieved = _now()
    mapping = client.lookup_point(40.7128, -74.0060, retrieved_time=retrieved)
    forecast = client.fetch_forecast(mapping, retrieved_time=retrieved, provider_first_observed_time=retrieved)
    hourly = client.fetch_hourly_forecast(mapping, retrieved_time=retrieved, provider_first_observed_time=retrieved)
    grid = client.fetch_grid_data(mapping, retrieved_time=retrieved, provider_first_observed_time=retrieved)
    sync.sync_nws_current_forecast(
        forecast,
        mapping=mapping,
        ingested_time=retrieved,
        content_hash=hashlib.sha256(repr(forecast).encode("utf-8")).hexdigest(),
    )

    cpc_forecast_url = f"{CPC_ROOT}/daily_forecasts_7day/latest/UtilityGas.Heating.txt"
    forecast_text = transport.request_bytes(cpc_forecast_url, accept="text/plain").decode("utf-8")
    cpc_forecast_available = _last_modified(transport, retrieved)
    forecast_rows = parse_cpc_forecast(
        forecast_text,
        forecast_available_time=cpc_forecast_available,
        source_file_id=cpc_forecast_url,
        source_file_last_modified=cpc_forecast_available,
        provider_first_observed_time=retrieved,
        retrieved_time=retrieved,
        ingested_time=retrieved,
        content_hash=hashlib.sha256(forecast_text.encode("utf-8")).hexdigest(),
    )
    sync.store.add_forecasts(forecast_rows)

    cpc_realized_url = f"{CPC_ROOT}/daily_data/latest/Population.Heating.txt"
    realized_text = transport.request_bytes(cpc_realized_url, accept="text/plain").decode("utf-8")
    cpc_realized_available = _last_modified(transport, retrieved)
    realized_rows = parse_cpc_realized(
        realized_text,
        available_time=cpc_realized_available,
        source_file_id=cpc_realized_url,
        provider_first_observed_time=retrieved,
        retrieved_time=retrieved,
        ingested_time=retrieved,
        content_hash=hashlib.sha256(realized_text.encode("utf-8")).hexdigest(),
    )
    sync.store.add_realizations(realized_rows)

    ndfd_catalog_url = "https://www.ncei.noaa.gov/thredds/catalog/model/ndfd.html"
    ndfd_catalog = transport.request_bytes(ndfd_catalog_url, accept="application/xml, text/xml")
    ndfd = characterize_ndfd_metadata(
        {
            "source": "NOAA_NCEI",
            "period_of_record": {"by_wmo_header_start": "2004-06-06", "cloud_start": "2020-04-16"},
            "access": [{"kind": "THREDDS", "url": ndfd_catalog_url}, {"kind": "NODD_S3", "url": "s3://noaa-ndfd-pds/wmo/"}],
            "formats": ["GRIB2"],
            "catalog_entries": [{"bounded_catalog_bytes": len(ndfd_catalog)}],
        }
    )
    return {
        "tested_at": retrieved,
        "nws": {
            "point_mapping": mapping.mapping_identity,
            "forecast_periods": len(forecast.periods),
            "forecast_horizon": [forecast.horizon_start, forecast.horizon_end],
            "hourly_periods": len(hourly.periods),
            "hourly_horizon": [hourly.horizon_start, hourly.horizon_end],
            "grid_elements": sorted(grid.elements),
            "grid_horizon": [grid.horizon_start, grid.horizon_end],
        },
        "cpc": {
            "latest_forecast_issue": max((row.forecast_issue_time for row in forecast_rows), default=""),
            "forecast_available_time": cpc_forecast_available,
            "forecast_targets": sorted({row.target_start for row in forecast_rows}),
            "latest_realized_date": max((row.period_start for row in realized_rows), default=""),
            "realized_available_time": cpc_realized_available,
        },
        "ndfd": ndfd,
    }


def main() -> int:
    live = live_enabled()
    sync = WeatherSync()
    live_result: dict[str, object] = {}
    if live:
        live_result = _live_characterization(sync)
    report = capability_report(live=live, store=sync.store)
    report["live_characterization"] = live_result
    report["security"] = {
        "mandatory_secret": False,
        "nws_user_agent_is_secret": False,
        "report_contains_credential_values": False,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote {OUTPUT}")
    print(f"classification={report['classification']}")
    if live_result:
        print(f"latest_cpc_forecast_issue={live_result['cpc']['latest_forecast_issue']}")
        print(f"latest_cpc_realized_date={live_result['cpc']['latest_realized_date']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
