from __future__ import annotations

import os
from dataclasses import dataclass
from enum import StrEnum


class DeploymentMode(StrEnum):
    LOCAL_FULL = "LOCAL_FULL"
    CLOUD_PROVIDER_MODE = "CLOUD_PROVIDER_MODE"
    FROZEN_DEMO = "FROZEN_DEMO"


@dataclass(frozen=True)
class RuntimeConfig:
    mode: DeploymentMode
    host: str
    port: int
    load_private: bool
    enable_local_ibkr: bool
    use_frozen_demo: bool


def deployment_mode(value: str | DeploymentMode | None = None) -> DeploymentMode:
    raw = value or os.environ.get("SQUEEZE_APP_MODE", DeploymentMode.LOCAL_FULL)
    try:
        return DeploymentMode(str(raw))
    except ValueError as exc:
        raise ValueError(f"unsupported SQUEEZE_APP_MODE {raw!r}") from exc


def resolve_runtime(mode: str | DeploymentMode | None = None, *, port: int | None = None) -> RuntimeConfig:
    selected = deployment_mode(mode)
    if selected is DeploymentMode.LOCAL_FULL:
        host = os.environ.get("HOST", "127.0.0.1")
        return RuntimeConfig(selected, host, port or 8787, True, True, False)
    env_port = os.environ.get("PORT")
    resolved_port = port or (int(env_port) if env_port else 8787)
    return RuntimeConfig(
        selected,
        "0.0.0.0" if selected is DeploymentMode.CLOUD_PROVIDER_MODE else "127.0.0.1",
        resolved_port,
        False,
        False,
        True,
    )
