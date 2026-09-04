"""Report provider credential, gate, and local transport readiness safely."""

from __future__ import annotations

import argparse
import json
import os
import socket
from pathlib import Path
from typing import Callable, Mapping
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
PRIMARY_OBSERVATIONAL_PROVIDER = "moomoo"
PLACEHOLDERS = frozenset({"", "CHANGEME", "EXAMPLE", "PLACEHOLDER", "NOT_A_SECRET"})
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
LocalProbe = Callable[[str, int], bool]


def load_env_file(path: Path) -> dict[str, str]:
    """Read simple KEY=VALUE lines without printing or logging their values."""

    values: dict[str, str] = {}
    if not path.is_file():
        return values
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        return values
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            values[key] = value
    return values


def _effective_environment(
    environ: Mapping[str, str], repository_root: Path
) -> dict[str, str]:
    values = load_env_file(repository_root / ".env")
    private_path = _private_provider_env(environ, repository_root)
    if private_path is not None:
        values.update(load_env_file(private_path))
    values.update({str(key): str(value) for key, value in environ.items()})
    return values


def _present(value: str | None) -> bool:
    return (value or "").strip().upper() not in PLACEHOLDERS


def _all_present(environment: Mapping[str, str], keys: tuple[str, ...]) -> bool:
    return all(_present(environment.get(key)) for key in keys)


def _any_present(environment: Mapping[str, str], keys: tuple[str, ...]) -> bool:
    return any(_present(environment.get(key)) for key in keys)


def _enabled(environment: Mapping[str, str], *keys: str) -> bool:
    return any(environment.get(key, "").strip().lower() in {"1", "true", "yes"} for key in keys)


def _all_enabled(environment: Mapping[str, str], *keys: str) -> bool:
    return all(environment.get(key, "").strip().lower() in {"1", "true", "yes"} for key in keys)


def _private_provider_env(environment: Mapping[str, str], repository_root: Path) -> Path | None:
    override = environment.get("IMP_PROVIDER_ENV", "").strip()
    if override:
        path = Path(override).expanduser()
        return path if path.is_file() else None
    candidate = repository_root / ".private" / "providers.env"
    return candidate if candidate.is_file() else None


def _finviz_token_present(environment: Mapping[str, str], repository_root: Path) -> bool:
    if _any_present(environment, ("FINVIZ_API_KEY", "FINVIZ_AUTH_TOKEN", "FINVIZ_API_TOKEN")):
        return True
    token_file = repository_root / ".private" / "finviz-token.txt"
    if token_file.is_file():
        try:
            if _present(token_file.read_text(encoding="utf-8")):
                return True
        except (OSError, UnicodeError):
            pass
    provider_env = _private_provider_env(environment, repository_root)
    if provider_env is None:
        return False
    return _any_present(load_env_file(provider_env), ("FINVIZ_API_KEY", "FINVIZ_AUTH_TOKEN"))


def _safe_local_probe(host: str, port: int) -> bool:
    if host not in LOOPBACK_HOSTS:
        return False
    try:
        with socket.create_connection((host, port), timeout=0.35):
            return True
    except OSError:
        return False


def _transport_state(
    *,
    environment: Mapping[str, str],
    host: str,
    port: int,
    probe_local: LocalProbe | None,
    probe_local_services: bool,
) -> str:
    if not probe_local_services or probe_local is None:
        return "NOT_CHECKED"
    if host not in LOOPBACK_HOSTS:
        return "BLOCKED_NON_LOOPBACK"
    return "REACHABLE" if probe_local(host, port) else "UNAVAILABLE"


def _row(
    provider: str,
    role: str,
    *,
    credential_state: str,
    gate_state: str,
    transport_state: str,
    required_credentials: tuple[str, ...] = (),
    next_action: str,
) -> dict[str, object]:
    return {
        "provider": provider,
        "role": role,
        "credential_state": credential_state,
        "gate_state": gate_state,
        "transport_state": transport_state,
        "required_credentials": list(required_credentials),
        "next_action": next_action,
    }


def _gateway_parts(environment: Mapping[str, str]) -> tuple[str, int]:
    raw = environment.get("IMP_IBKR_GATEWAY_URL", "https://127.0.0.1:5000/v1/api")
    parsed = urlparse(raw)
    host = parsed.hostname or ""
    try:
        port = parsed.port or 443
    except ValueError:
        return host, 0
    return host, port


def _ibkr_parts(environment: Mapping[str, str]) -> tuple[str, int, str]:
    transport = environment.get("IMP_IBKR_TRANSPORT", "client_portal").strip().lower()
    if transport == "tws":
        host = environment.get("IMP_IBKR_TWS_HOST", "127.0.0.1").strip()
        try:
            port = int(environment.get("IMP_IBKR_TWS_PORT", "4001"))
        except (TypeError, ValueError):
            port = 0
        return host, port, transport
    host, port = _gateway_parts(environment)
    return host, port, "client_portal"


def collect_readiness(
    environ: Mapping[str, str] | None = None,
    *,
    repository_root: Path | None = None,
    probe_local: LocalProbe | None = None,
    probe_local_services: bool = False,
) -> dict[str, object]:
    """Return a value-blind provider readiness report.

    The local ``.env`` is read only to determine presence. Secret values are
    never copied into the returned report.
    """

    root = (repository_root or ROOT).resolve()
    environment = _effective_environment(environ or {}, root)
    providers: list[dict[str, object]] = []

    anthropic_configured = _present(environment.get("ANTHROPIC_API_KEY"))
    providers.append(
        _row(
            "anthropic",
            "assistant",
            credential_state="CONFIGURED" if anthropic_configured else "MISSING",
            gate_state=(
                "ENABLED"
                if anthropic_configured
                and environment.get("IMP_ASSISTANT_PROVIDER", "").strip().lower() == "anthropic"
                and not _enabled(environment, "IMP_ASSISTANT_STUB")
                else "DISABLED"
            ),
            transport_state="IMPLEMENTED",
            required_credentials=("ANTHROPIC_API_KEY",),
            next_action="Set IMP_ASSISTANT_PROVIDER=anthropic to use the configured key."
            if anthropic_configured
            else "Add an Anthropic API key or use grounded/stub inference.",
        )
    )

    for provider, keys, gate, action in (
        (
            "finra",
            ("FINRA_CLIENT_ID", "FINRA_CLIENT_SECRET"),
            ("IMP_FINRA_LIVE", "IMP_FINRA_OTC_THRESHOLD_LIVE"),
            "Enable the FINRA live gate after confirming the client secret rotation metadata.",
        ),
        (
            "fred",
            ("FRED_API_KEY",),
            ("IMP_FRED_LIVE",),
            "Enable IMP_FRED_LIVE for bounded FRED/ALFRED validation.",
        ),
        (
            "eia",
            ("EIA_API_KEY",),
            ("IMP_EIA_LIVE",),
            "Enable IMP_EIA_LIVE for bounded EIA validation.",
        ),
    ):
        configured = _all_present(environment, keys)
        providers.append(
            _row(
                provider,
                "research",
                credential_state="CONFIGURED" if configured else "MISSING",
                gate_state="ENABLED" if _enabled(environment, *gate) else "DISABLED",
                transport_state="IMPLEMENTED",
                required_credentials=keys,
                next_action=action if configured else f"Add {', '.join(keys)}.",
            )
        )

    sec_identity = _present(environment.get("SEC_USER_AGENT"))
    for provider, gate, action in (
        (
            "sec_edgar",
            ("IMP_EDGAR_LIVE", "SEC_LIVE_TESTS"),
            "Set SEC_USER_AGENT to a descriptive contact identity before enabling live EDGAR.",
        ),
        (
            "sec_ftd",
            ("IMP_SEC_FTD_LIVE",),
            "Reuse the descriptive SEC_USER_AGENT before enabling live FTD retrieval.",
        ),
    ):
        providers.append(
            _row(
                provider,
                "regulatory",
                credential_state="CONFIGURED" if sec_identity else "MISSING",
                gate_state="ENABLED" if _enabled(environment, *gate) else "DISABLED",
                transport_state="IMPLEMENTED",
                required_credentials=("SEC_USER_AGENT",),
                next_action="Ready for gated validation." if sec_identity else action,
            )
        )

    news_provider_env = _private_provider_env(environment, root)
    news_file_values = load_env_file(news_provider_env) if news_provider_env else {}
    for provider, key, gate in (
        ("newsapi", "NEWSAPI_API_KEY", "IMP_NEWSAPI_LIVE"),
        ("finnhub", "FINNHUB_API_KEY", "IMP_FINNHUB_LIVE"),
    ):
        configured = _present(environment.get(key)) or _present(news_file_values.get(key))
        providers.append(
            _row(
                provider,
                "news_catalyst",
                credential_state="CONFIGURED" if configured else "MISSING",
                gate_state="ENABLED" if _enabled(environment, gate) else "DISABLED",
                transport_state="IMPLEMENTED_READ_ONLY",
                required_credentials=(key,),
                next_action=(
                    f"Run tools/news/probe.py --symbol AAPL for bounded validation."
                    if configured
                    else f"Add {key} with tools/news/auth.py configure."
                ),
            )
        )

    finviz = _finviz_token_present(environment, root)
    providers.append(
        _row(
            "finviz",
            "discovery",
            credential_state="CONFIGURED" if finviz else "MISSING",
            gate_state="ENABLED" if _enabled(environment, "IMP_FINVIZ_LIVE") else "DISABLED",
            transport_state="IMPLEMENTED_READ_ONLY",
            required_credentials=("FINVIZ_API_KEY", "FINVIZ_AUTH_TOKEN"),
            next_action=(
                "Run tools/finviz/auth.py status, then validate a prospective capture."
                if finviz
                else "Configure a Finviz Elite token or operator login recovery."
            ),
        )
    )

    moomoo_host = environment.get("IMP_MOOMOO_HOST", "127.0.0.1").strip()
    try:
        moomoo_port = int(environment.get("IMP_MOOMOO_PORT", "11111"))
    except ValueError:
        moomoo_port = 0
    moomoo_gate = _all_enabled(environment, "IMP_LIVE_OBSERVATIONAL", "IMP_MOOMOO_LIVE")
    providers.append(
        _row(
            "moomoo_observational",
            "primary_observational_market_data",
            credential_state="NOT_REQUIRED",
            gate_state="ENABLED" if moomoo_gate else "DISABLED",
            transport_state=_transport_state(
                environment=environment,
                host=moomoo_host,
                port=moomoo_port,
                probe_local=probe_local,
                probe_local_services=probe_local_services,
            ),
            next_action=(
                "Start OpenD, sign in with an entitled Moomoo account, then run the capability probe."
                if not moomoo_gate
                else "Confirm OpenD session and entitlements with tools/moomoo/probe.py."
            ),
        )
    )

    ibkr_host, ibkr_port, ibkr_transport = _ibkr_parts(environment)
    provider_env = _private_provider_env(environment, root)
    ibkr_file_configured = False
    if provider_env is not None:
        ibkr_file_configured = _all_present(
            load_env_file(provider_env),
            ("IBKR_USERNAME", "IBKR_PASSWORD"),
        )
    providers.append(
        _row(
            "ibkr_observational",
            "secondary_observational_market_data",
            credential_state=(
                "CREDENTIAL_FILE_PRESENT_MANUAL_LOGIN_REQUIRED"
                if ibkr_file_configured
                else "MANUAL_SESSION_REQUIRED"
            ),
            gate_state="ENABLED" if _enabled(environment, "IMP_IBKR_LIVE") else "DISABLED",
            transport_state=_transport_state(
                environment=environment,
                host=ibkr_host,
                port=ibkr_port,
                probe_local=probe_local,
                probe_local_services=probe_local_services,
            ),
            required_credentials=("IBKR_USERNAME", "IBKR_PASSWORD", "IBKR_TOTP_SECRET"),
            next_action=(
                "Confirm desktop IB Gateway is logged in and accepting local socket connections."
                if ibkr_transport == "tws"
                else "Start Client Portal Gateway and complete manual brokerage login."
            ),
        )
    )

    tradier_configured = _present(environment.get("IMP_TRADIER_TOKEN"))
    providers.append(
        _row(
            "tradier_paper",
            "sandbox_execution",
            credential_state="CONFIGURED" if tradier_configured else "MISSING",
            gate_state=(
                "ENABLED"
                if _all_enabled(environment, "IMP_TRADIER_PAPER", "IMP_BROKER_PAPER_EXECUTION")
                else "DISABLED"
            ),
            transport_state="FIXTURE_ONLY",
            required_credentials=("IMP_TRADIER_TOKEN",),
            next_action=(
                "Implement and verify the sandbox HTTP transport before submitting orders."
                if tradier_configured
                else "Add a Tradier sandbox token only when sandbox lifecycle testing is needed."
            ),
        )
    )

    moomoo_paper_configured = _all_present(
        environment,
        ("IMP_MOOMOO_PAPER_KEY", "IMP_MOOMOO_PAPER_SECRET"),
    )
    providers.append(
        _row(
            "moomoo_paper",
            "simulated_execution",
            credential_state="CONFIGURED" if moomoo_paper_configured else "MISSING",
            gate_state=(
                "ENABLED"
                if _all_enabled(environment, "IMP_MOOMOO_PAPER", "IMP_MOOMOO_PAPER_EXECUTION")
                else "DISABLED"
            ),
            transport_state="FIXTURE_ONLY",
            required_credentials=("IMP_MOOMOO_PAPER_KEY", "IMP_MOOMOO_PAPER_SECRET"),
            next_action="Keep fixture replay until the proprietary OpenD paper wire is implemented."
            if moomoo_paper_configured
            else "Do not add keys until a real simulated-environment transport is in scope.",
        )
    )

    mongo_configured = _present(environment.get("IMP_MONGODB_URI"))
    providers.append(
        _row(
            "mongodb",
            "operational_persistence",
            credential_state="CONFIGURED" if mongo_configured else "MISSING",
            gate_state="CONFIGURED" if mongo_configured else "OPTIONAL",
            transport_state="IMPLEMENTED_OPTIONAL",
            required_credentials=("IMP_MONGODB_URI",),
            next_action="Use a test-prefixed database for integration tests."
            if mongo_configured
            else "Add Mongo only if durable shared persistence is required.",
        )
    )

    for provider, role, gate in (
        ("cftc", "public_positioning", "RUN_LIVE_CFTC"),
        ("threshold_sources", "public_short_status", "IMP_NASDAQ_REGSHO_LIVE"),
        ("cboe_options", "public_options_statistics", "IMP_CBOE_OPTIONS_LIVE"),
        ("weather", "public_weather", "IMP_WEATHER_LIVE"),
    ):
        providers.append(
            _row(
                provider,
                role,
                credential_state="NOT_REQUIRED",
                gate_state="ENABLED" if _enabled(environment, gate) else "DISABLED",
                transport_state="IMPLEMENTED_PUBLIC",
                next_action=f"Enable {gate} for bounded live validation.",
            )
        )

    return {
        "schema_version": "1.0",
        "primary_observational_provider": PRIMARY_OBSERVATIONAL_PROVIDER,
        "secrets_included": False,
        "providers": providers,
    }


def _print_report(report: Mapping[str, object], *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(report, indent=2, sort_keys=True))
        return
    print(f"PRIMARY_OBSERVATIONAL_PROVIDER={report['primary_observational_provider']}")
    for row in report["providers"]:  # type: ignore[union-attr]
        print(
            f"{row['provider']}: credential={row['credential_state']} "
            f"gate={row['gate_state']} transport={row['transport_state']}"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Print a machine-readable report")
    parser.add_argument(
        "--probe-local",
        action="store_true",
        help="Probe loopback Moomoo and IBKR ports; never probes external hosts",
    )
    args = parser.parse_args(argv)
    report = collect_readiness(
        os.environ,
        probe_local=_safe_local_probe,
        probe_local_services=args.probe_local,
    )
    _print_report(report, as_json=args.json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
