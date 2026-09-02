"""Fail-closed configuration for the local IBKR Client Portal Gateway."""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping
from urllib.parse import urlsplit


DEFAULT_GATEWAY_URL = "https://127.0.0.1:5000/v1/api"
DEFAULT_TWS_HOST = "127.0.0.1"
DEFAULT_TWS_PORT = 4001
DEFAULT_TWS_CLIENT_ID = 37


class ConfigError(ValueError):
    """Raised when observational gateway configuration is unsafe or invalid."""


def validate_gateway_url(value: str) -> str:
    """Return a canonical loopback gateway base URL or fail closed."""

    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as exc:
        raise ConfigError("IMP_IBKR_GATEWAY_URL is invalid") from exc
    if parsed.scheme.lower() != "https":
        raise ConfigError("IMP_IBKR_GATEWAY_URL must use HTTPS")
    if parsed.username is not None or parsed.password is not None:
        raise ConfigError("IMP_IBKR_GATEWAY_URL must not contain user information")
    if parsed.query or parsed.fragment:
        raise ConfigError("IMP_IBKR_GATEWAY_URL must not contain query or fragment data")
    host = (parsed.hostname or "").lower()
    loopback = host == "localhost"
    if not loopback:
        try:
            loopback = ipaddress.ip_address(host).is_loopback
        except ValueError:
            loopback = False
    if not loopback:
        raise ConfigError("IMP_IBKR_GATEWAY_URL must use a loopback host")
    if port != 5000:
        raise ConfigError("IMP_IBKR_GATEWAY_URL must use Client Portal port 5000")
    if parsed.path.rstrip("/") != "/v1/api":
        raise ConfigError("IMP_IBKR_GATEWAY_URL must end with /v1/api")
    return value.rstrip("/")


def validate_tws_host(value: str) -> str:
    """Return a loopback TWS host or fail closed."""

    host = value.strip().lower()
    if host == "localhost":
        return value.strip()
    try:
        if ipaddress.ip_address(host).is_loopback:
            return value.strip()
    except ValueError:
        pass
    raise ConfigError("IMP_IBKR_TWS_HOST must use a loopback host")


def _gate(value: str | None) -> bool:
    normalized = (value or "").strip().lower()
    if normalized in {"", "0", "false"}:
        return False
    if normalized == "1":
        return True
    raise ConfigError("IMP_IBKR_LIVE must be 1 or disabled")


def _float(env: Mapping[str, str], key: str, default: float) -> float:
    try:
        return float(env.get(key, str(default)))
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"{key} must be numeric") from exc


def _integer(env: Mapping[str, str], key: str, default: int) -> int:
    try:
        return int(env.get(key, str(default)))
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"{key} must be an integer") from exc


@dataclass(frozen=True, slots=True)
class IbkrConfig:
    live_enabled: bool
    gateway_url: str
    capture_root: Path
    transport: str = "client_portal"
    tws_host: str = DEFAULT_TWS_HOST
    tws_port: int = DEFAULT_TWS_PORT
    tws_client_id: int = DEFAULT_TWS_CLIENT_ID
    requests_per_second: float = 10.0
    history_min_spacing_seconds: float = 15.0
    history_window_max: int = 50
    history_window_seconds: float = 600.0
    penalty_box_seconds: float = 900.0
    timeout_seconds: float = 10.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "gateway_url", validate_gateway_url(self.gateway_url))
        transport = self.transport.strip().lower()
        if transport not in {"client_portal", "tws"}:
            raise ConfigError("IMP_IBKR_TRANSPORT must be client_portal or tws")
        object.__setattr__(self, "transport", transport)
        object.__setattr__(self, "tws_host", validate_tws_host(self.tws_host))
        if self.tws_port not in {4001, 4002}:
            raise ConfigError("IMP_IBKR_TWS_PORT must be 4001 or 4002")
        if self.tws_client_id <= 0:
            raise ConfigError("IMP_IBKR_TWS_CLIENT_ID must be positive")
        if not 0 < self.requests_per_second <= 10:
            raise ConfigError("IMP_IBKR_PACING_RPS must be in (0, 10]")
        if self.history_min_spacing_seconds < 15:
            raise ConfigError("IMP_IBKR_HIST_MIN_SPACING_SEC must be at least 15")
        if not 1 <= self.history_window_max <= 50:
            raise ConfigError("IMP_IBKR_HIST_WINDOW_MAX must be in [1, 50]")
        if self.history_window_seconds < 600:
            raise ConfigError("history_window_seconds must be at least 600")
        if self.penalty_box_seconds < 900:
            raise ConfigError("IMP_IBKR_PENALTY_BOX_SEC must be at least 900")
        if self.timeout_seconds <= 0:
            raise ConfigError("timeout_seconds must be positive")

    @classmethod
    def from_env(cls, env: Mapping[str, str], *, root: Path) -> "IbkrConfig":
        capture_value = env.get("IMP_IBKR_CAPTURE_ROOT", "").strip()
        capture_root = Path(capture_value) if capture_value else root / "evidence" / "market_data" / "ibkr"
        if not capture_root.is_absolute():
            capture_root = root / capture_root
        return cls(
            live_enabled=_gate(env.get("IMP_IBKR_LIVE")),
            gateway_url=env.get("IMP_IBKR_GATEWAY_URL", DEFAULT_GATEWAY_URL).strip(),
            capture_root=capture_root,
            transport=env.get("IMP_IBKR_TRANSPORT", "client_portal"),
            tws_host=env.get("IMP_IBKR_TWS_HOST", DEFAULT_TWS_HOST),
            tws_port=_integer(env, "IMP_IBKR_TWS_PORT", DEFAULT_TWS_PORT),
            tws_client_id=_integer(env, "IMP_IBKR_TWS_CLIENT_ID", DEFAULT_TWS_CLIENT_ID),
            requests_per_second=_float(env, "IMP_IBKR_PACING_RPS", 10.0),
            history_min_spacing_seconds=_float(env, "IMP_IBKR_HIST_MIN_SPACING_SEC", 15.0),
            history_window_max=_integer(env, "IMP_IBKR_HIST_WINDOW_MAX", 50),
            penalty_box_seconds=_float(env, "IMP_IBKR_PENALTY_BOX_SEC", 900.0),
        )


__all__ = [
    "ConfigError",
    "DEFAULT_GATEWAY_URL",
    "DEFAULT_TWS_CLIENT_ID",
    "DEFAULT_TWS_HOST",
    "DEFAULT_TWS_PORT",
    "IbkrConfig",
    "validate_gateway_url",
    "validate_tws_host",
]
