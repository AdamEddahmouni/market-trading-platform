"""One-shot live EIA production characterization — sanitized stdout only."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.eia.contracts import EnergyReleaseFamily  # noqa: E402
from market_platform_foundation.eia.live import load_api_key  # noqa: E402
from market_platform_foundation.eia.redaction import sanitize_response_payload  # noqa: E402
from market_platform_foundation.eia.registry import (  # noqa: E402
    NATURAL_GAS_REGISTRY,
    NATURAL_GAS_ROUTE,
    PETROLEUM_REGISTRY,
    PETROLEUM_ROUTE,
    FULL_REGISTRY,
)
from market_platform_foundation.eia.release_schedule import (  # noqa: E402
    latest_published_release,
    next_expected_release,
)
from market_platform_foundation.eia.transport import EiaTransport, EiaTransportError  # noqa: E402


def _query_latest(transport: EiaTransport, series: str, route: str) -> dict:
    params = {
        "frequency": "weekly",
        "data[0]": "value",
        "facets[series][]": series,
        "sort[0][column]": "period",
        "sort[0][direction]": "desc",
        "length": 1,
    }
    payload = transport.query_data(route, params=params)
    rows = payload.get("response", {}).get("data", [])
    return rows[0] if rows else {}


def main() -> int:
    key = load_api_key()
    if not key:
        print("EIA_API_KEY_PRESENT=false")
        return 1

    transport = EiaTransport(api_key=key)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    out: dict[str, object] = {"retrieved_at": now, "eia_api_auth_success": False}

    try:
        pet_meta = transport.get_route_metadata("/v2/petroleum/sum/sndw")
        ng_meta = transport.get_route_metadata("/v2/natural-gas/stor/wkly")
        out["eia_api_auth_success"] = True
    except EiaTransportError as exc:
        out["error"] = str(exc)
        print(json.dumps(out, indent=2))
        return 1

    pet_resp = pet_meta.get("response", {})
    ng_resp = ng_meta.get("response", {})
    out["api_version"] = pet_resp.get("version", "unknown")
    out["routes"] = {"petroleum": PETROLEUM_ROUTE, "natural_gas": NATURAL_GAS_ROUTE}
    out["petroleum_metadata"] = {
        "frequencies": pet_resp.get("frequency", []),
        "data_columns": [d.get("name") for d in pet_resp.get("data", []) if isinstance(d, dict)],
        "facet_ids": [f.get("id") for f in pet_resp.get("facets", []) if isinstance(f, dict)],
        "date_range": pet_resp.get("dateRange", {}),
    }
    out["natural_gas_metadata"] = {
        "frequencies": ng_resp.get("frequency", []),
        "data_columns": [d.get("name") for d in ng_resp.get("data", []) if isinstance(d, dict)],
        "facet_ids": [f.get("id") for f in ng_resp.get("facets", []) if isinstance(f, dict)],
        "date_range": ng_resp.get("dateRange", {}),
    }

    raw_params = pet_resp.get("request", {}).get("params", {})
    sanitized = sanitize_response_payload(pet_meta)
    san_params = sanitized.get("response", {}).get("request", {}).get("params", {})
    out["response_echo"] = {
        "raw_api_key_echo": "present" if raw_params.get("api_key") else "absent",
        "sanitized_api_key": san_params.get("api_key", "absent"),
        "real_key_in_serialized_meta": key in json.dumps(pet_meta),
        "real_key_in_sanitized_meta": key in json.dumps(sanitized),
    }

    registry_audit: list[dict[str, object]] = []
    for cid, entry in FULL_REGISTRY.items():
        try:
            row = _query_latest(transport, entry.series, entry.route)
            registry_audit.append(
                {
                    "concept": cid,
                    "series": entry.series,
                    "region": entry.region,
                    "unit": entry.unit,
                    "metric_class": entry.metric_class.value,
                    "latest_period": row.get("period", ""),
                    "latest_value": row.get("value"),
                    "value_units": row.get("value-units", row.get("units", "")),
                    "status": "OBSERVED" if row.get("period") else "NO_DATA",
                }
            )
        except EiaTransportError:
            registry_audit.append({"concept": cid, "series": entry.series, "status": "ERROR"})
    out["registry_audit"] = registry_audit

    wpsr = latest_published_release(EnergyReleaseFamily.WPSR)
    wngsr = latest_published_release(EnergyReleaseFamily.WNGSR)
    out["wpsr"] = {
        "latest_period_end": str(wpsr.period_end) if wpsr else "",
        "scheduled_publication": str(wpsr.publication_date) if wpsr else "",
        "next_publication": str(next_expected_release(EnergyReleaseFamily.WPSR).publication_date)
        if next_expected_release(EnergyReleaseFamily.WPSR)
        else "",
    }
    out["wngsr"] = {
        "latest_period_end": str(wngsr.period_end) if wngsr else "",
        "scheduled_publication": str(wngsr.publication_date) if wngsr else "",
        "next_publication": str(next_expected_release(EnergyReleaseFamily.WNGSR).publication_date)
        if next_expected_release(EnergyReleaseFamily.WNGSR)
        else "",
    }

    commercial = PETROLEUM_REGISTRY["COMMERCIAL_CRUDE_STOCKS"]
    sample = _query_latest(transport, commercial.series, commercial.route)
    out["latest_petroleum_api_period"] = sample.get("period", "")
    ng_sample = _query_latest(
        transport,
        NATURAL_GAS_REGISTRY["LOWER48_WORKING_GAS_STORAGE"].series,
        NATURAL_GAS_ROUTE,
    )
    out["latest_ng_api_period"] = ng_sample.get("period", "")

    serialized = json.dumps(out)
    if key in serialized:
        print("SECURITY_FAILURE: real key in output")
        return 2

    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
