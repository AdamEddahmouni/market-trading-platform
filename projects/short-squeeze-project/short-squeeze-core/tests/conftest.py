from datetime import UTC, datetime, timedelta
from decimal import Decimal
import ipaddress
import socket
from typing import Any

import pytest

from squeeze_core.contracts import (
    AssetClass,
    DataFreshness,
    EventType,
    IngestionMethod,
    MarketSession,
    Observation,
    ObservationKind,
    PayloadType,
    Provenance,
    Quality,
    QualityState,
    TradePayload,
)


def _is_localhost(host: object) -> bool:
    text = str(host).strip().lower()
    if text in {"localhost", "localhost.localdomain"}:
        return True
    try:
        return ipaddress.ip_address(text).is_loopback
    except ValueError:
        return False


@pytest.fixture(autouse=True)
def block_external_network(monkeypatch):
    """Fail every ordinary test that attempts non-local network access.

    The application smoke tests intentionally use a loopback HTTP server, so loopback
    sockets remain available. An attempt is recorded before raising because provider
    adapters degrade on connection errors; the teardown assertion makes swallowed
    network errors visible to pytest.
    """
    attempts: list[str] = []
    real_getaddrinfo = socket.getaddrinfo
    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex

    def guarded_getaddrinfo(host, *args, **kwargs):
        if not _is_localhost(host):
            attempts.append(f"DNS:{host}")
            raise AssertionError(f"external DNS blocked during tests: {host}")
        return real_getaddrinfo(host, *args, **kwargs)

    def guarded_connect(sock, address):
        host = address[0] if isinstance(address, tuple) and address else address
        if not _is_localhost(host):
            attempts.append(f"CONNECT:{host}")
            raise AssertionError(f"external socket blocked during tests: {host}")
        return real_connect(sock, address)

    def guarded_connect_ex(sock, address):
        host = address[0] if isinstance(address, tuple) and address else address
        if not _is_localhost(host):
            attempts.append(f"CONNECT_EX:{host}")
            raise AssertionError(f"external socket blocked during tests: {host}")
        return real_connect_ex(sock, address)

    monkeypatch.setattr(socket, "getaddrinfo", guarded_getaddrinfo)
    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", guarded_connect_ex)
    yield
    assert attempts == [], f"unexpected external network attempt(s): {attempts}"


@pytest.fixture
def make_observation():
    base = datetime(2026, 1, 2, 14, 30, tzinfo=UTC)

    def factory(
        record_id: str,
        *,
        offset_seconds: int = 0,
        source_offset_seconds: int | None = None,
        sequence_number: int | None = None,
        observation_id: str | None = None,
        **overrides: Any,
    ) -> Observation:
        effective = base + timedelta(seconds=offset_seconds)
        source = base + timedelta(
            seconds=offset_seconds if source_offset_seconds is None else source_offset_seconds
        )
        values: dict[str, Any] = {
            "schema_version": "1.0.0",
            "observation_id": observation_id,
            "event_type": EventType.TRADE,
            "symbol": "TESTA",
            "asset_class": AssetClass.EQUITY,
            "source": "synthetic-fixture",
            "source_record_id": record_id,
            "source_timestamp": source,
            "received_timestamp": effective,
            "effective_timestamp": effective,
            "market_session": MarketSession.REGULAR,
            "data_freshness": DataFreshness.HISTORICAL,
            "observation_kind": ObservationKind.SYNTHETIC,
            "quality": Quality(state=QualityState.KNOWN_VALUE),
            "payload_type": PayloadType.TRADE,
            "payload": TradePayload(price=Decimal("10.00"), size=100),
            "provenance": Provenance(
                provider="synthetic-fixture",
                ingestion_method=IngestionMethod.LOADED_FIXTURE,
                origin_kind=ObservationKind.SYNTHETIC,
                normalized=False,
            ),
            "sequence_number": sequence_number,
        }
        values.update(overrides)
        return Observation.model_validate(values)

    return factory
