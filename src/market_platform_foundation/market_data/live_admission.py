"""Runtime live-data admission — extends QualityObservation, fail-closed."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from ..data_quality.observations import QualityObservation, consumer_eligibility
from ..order_flow.quality import OrderFlowQualityFlag
from .live_config import clock_drift_threshold_ms, execution_freshness_threshold_ms, quote_stale_threshold_ms
from .normalization import live_envelope_from_capture
from .quality import assess_book, assess_quote, assess_ticker


ADMISSION_DISPLAY = "DISPLAY_ADMITTED"
ADMISSION_EXECUTION = "EXECUTION_ADMITTED"
ADMISSION_BLOCKED = "BLOCKED"
ADMISSION_DEGRADED = "DEGRADED"

BLOCKING_FLAG_STATES = frozenset(
    {
        "INVALID_QUOTE",
        OrderFlowQualityFlag.CROSSED_BOOK.value,
        "TIMESTAMP_REVERSAL",
        "CLOCK_DRIFT",
        "STALE",
        "PROVIDER_DISCONNECTED",
        "ENTITLEMENT_MISSING",
        "INITIAL_CACHED_EVENT",
    }
)

WARN_FLAG_STATES = frozenset(
    {
        OrderFlowQualityFlag.SEQUENCE_GAP.value,
        "DUPLICATE_TICK",
        OrderFlowQualityFlag.LOCKED_BOOK.value,
        OrderFlowQualityFlag.SPREAD_ABNORMAL.value,
        OrderFlowQualityFlag.AGGRESSOR_UNKNOWN.value,
        OrderFlowQualityFlag.DEPTH_PARTIAL.value,
        "SNAPSHOT_UPDATE_MISMATCH",
    }
)


@dataclass
class ChannelSessionState:
    prior_sequence: int | None = None
    prior_event_time_ns: int | None = None
    seen_event_ids: set[str] = field(default_factory=set)
    subscription_started_ns: int | None = None
    reconnect_generation: int = 0
    first_push_seen: bool = False


@dataclass
class LiveAdmissionEngine:
    sessions: dict[str, ChannelSessionState] = field(default_factory=dict)
    provider_connected: bool = True
    entitlement_ok: bool = True

    def _session_key(self, record: dict[str, Any]) -> str:
        instrument = str(record.get("instrument_id") or "").upper()
        capability = str(record.get("capability") or "")
        return f"{instrument}:{capability}"

    def _assess_flags(self, record: dict[str, Any], session: ChannelSessionState) -> tuple[str, ...]:
        payload = record.get("raw_payload") or {}
        capability = str(record.get("capability") or "")
        if "TICK" in capability:
            return assess_ticker(payload, prior_sequence=session.prior_sequence)
        if "DEPTH" in capability or "ORDER_BOOK" in capability:
            return assess_book(payload)
        return assess_quote(payload)

    def _flags_to_observations(
        self,
        flags: tuple[str, ...],
        *,
        scope: dict[str, str],
        available_time: int,
        event_id: str,
    ) -> list[dict[str, Any]]:
        observations: list[dict[str, Any]] = []
        for flag in flags:
            if flag in BLOCKING_FLAG_STATES or flag == "INVALID_QUOTE":
                dimension = "validity" if flag != "TIMESTAMP_REVERSAL" else "sequencing"
                severity = "ERROR"
                state = {
                    OrderFlowQualityFlag.CROSSED_BOOK.value: "INVALID_QUOTE",
                    "TIMESTAMP_REVERSAL": "REGRESSION",
                }.get(flag, flag if flag != OrderFlowQualityFlag.CROSSED_BOOK.value else "INVALID_QUOTE")
            elif flag in WARN_FLAG_STATES or flag == OrderFlowQualityFlag.SEQUENCE_GAP.value:
                dimension = "sequencing"
                severity = "WARN"
                state = {
                    "DUPLICATE_TICK": "DUPLICATE",
                    OrderFlowQualityFlag.SEQUENCE_GAP.value: "GAP",
                }.get(flag, flag)
            else:
                continue
            observations.append(
                QualityObservation(
                    dimension=dimension,
                    state=state,
                    severity=severity,
                    scope=scope,
                    available_time=available_time,
                    detected_at=available_time,
                    rule_id="QUAL-LIVE-001",
                    rule_version="1.0.0",
                    evidence_refs=[event_id],
                    observed=flag,
                ).finalize()
            )
        return observations

    def evaluate_record(
        self,
        record: dict[str, Any],
        *,
        wall_now_ns: int | None = None,
        is_first_push: bool = False,
        is_cached: bool = False,
    ) -> dict[str, Any]:
        now_ns = wall_now_ns if wall_now_ns is not None else time.time_ns()
        session_key = self._session_key(record)
        session = self.sessions.setdefault(session_key, ChannelSessionState())
        if session.subscription_started_ns is None:
            session.subscription_started_ns = now_ns

        clocks = record.get("clocks") if isinstance(record.get("clocks"), dict) else {}
        received_ns = int(clocks.get("received_time_ns") or now_ns)
        event_time_ns = int(clocks.get("event_time_ns") or received_ns)

        observations: list[dict[str, Any]] = []
        scope = {
            "channel_id": str(record.get("provider_symbol") or ""),
            "event_family": str(record.get("capability") or ""),
            "instrument_id": str(record.get("instrument_id") or "").upper(),
            "source_instance_id": str(record.get("provider") or "moomoo"),
        }

        if not self.provider_connected:
            observations.append(
                QualityObservation(
                    dimension="availability",
                    state="PROVIDER_DISCONNECTED",
                    severity="ERROR",
                    scope=scope,
                    available_time=received_ns,
                    detected_at=now_ns,
                    rule_id="QUAL-LIVE-AVAIL-001",
                    rule_version="1.0.0",
                ).finalize()
            )
        if not self.entitlement_ok:
            observations.append(
                QualityObservation(
                    dimension="availability",
                    state="ENTITLEMENT_MISSING",
                    severity="ERROR",
                    scope=scope,
                    available_time=received_ns,
                    detected_at=now_ns,
                    rule_id="QUAL-LIVE-AVAIL-002",
                    rule_version="1.0.0",
                ).finalize()
            )

        drift_ms = (received_ns - event_time_ns) // 1_000_000
        if event_time_ns > received_ns + 1_000_000:
            observations.append(
                QualityObservation(
                    dimension="timeliness",
                    state="CLOCK_DRIFT",
                    severity="ERROR",
                    scope=scope,
                    available_time=received_ns,
                    detected_at=now_ns,
                    rule_id="QUAL-LIVE-TIME-001",
                    rule_version="1.0.0",
                    expected="event_time <= received_time",
                    observed=str(event_time_ns),
                ).finalize()
            )
        elif drift_ms > clock_drift_threshold_ms():
            observations.append(
                QualityObservation(
                    dimension="timeliness",
                    state="CLOCK_DRIFT",
                    severity="WARN",
                    scope=scope,
                    available_time=received_ns,
                    detected_at=now_ns,
                    rule_id="QUAL-LIVE-TIME-002",
                    rule_version="1.0.0",
                    observed=f"{drift_ms}ms",
                ).finalize()
            )

        stale_ms = (now_ns - received_ns) // 1_000_000
        capability = str(record.get("capability") or "")
        if "L1" in capability or "SNAPSHOT" in capability:
            stale_threshold = quote_stale_threshold_ms()
            if stale_ms > stale_threshold:
                observations.append(
                    QualityObservation(
                        dimension="timeliness",
                        state="STALE",
                        severity="ERROR",
                        scope=scope,
                        available_time=received_ns,
                        detected_at=now_ns,
                        rule_id="QUAL-LIVE-TIME-003",
                        rule_version="1.0.0",
                        observed=f"{stale_ms}ms",
                    ).finalize()
                )
            elif stale_ms > execution_freshness_threshold_ms():
                observations.append(
                    QualityObservation(
                        dimension="timeliness",
                        state="EXECUTION_STALE",
                        severity="WARN",
                        scope=scope,
                        available_time=received_ns,
                        detected_at=now_ns,
                        rule_id="QUAL-LIVE-TIME-004",
                        rule_version="1.0.0",
                        observed=f"{stale_ms}ms",
                    ).finalize()
                )

        if is_cached:
            observations.append(
                QualityObservation(
                    dimension="consistency",
                    state="INITIAL_CACHED_EVENT",
                    severity="WARN",
                    scope=scope,
                    available_time=received_ns,
                    detected_at=now_ns,
                    rule_id="QUAL-LIVE-CACHE-001",
                    rule_version="1.0.0",
                ).finalize()
            )
            session.first_push_seen = True
        elif is_first_push:
            observations.append(
                QualityObservation(
                    dimension="consistency",
                    state="SNAPSHOT_UPDATE_MISMATCH",
                    severity="WARN",
                    scope=scope,
                    available_time=received_ns,
                    detected_at=now_ns,
                    rule_id="QUAL-LIVE-CACHE-002",
                    rule_version="1.0.0",
                    observed="FIRST_PUSH_SNAPSHOT",
                ).finalize()
            )
            session.first_push_seen = True

        flags = self._assess_flags(record, session)
        try:
            envelope = live_envelope_from_capture(record)
            event_id = str(envelope["normalized_event_id"])
        except ValueError as exc:
            observations.append(
                QualityObservation(
                    dimension="validity",
                    state="INVALID_QUOTE",
                    severity="ERROR",
                    scope=scope,
                    available_time=received_ns,
                    detected_at=now_ns,
                    rule_id="QUAL-LIVE-ENV-001",
                    rule_version="1.0.0",
                    observed=str(exc),
                ).finalize()
            )
            return self._finalize(record, None, observations, flags)

        if event_id in session.seen_event_ids:
            observations.append(
                QualityObservation(
                    dimension="sequencing",
                    state="DUPLICATE",
                    severity="WARN",
                    scope=scope,
                    available_time=received_ns,
                    detected_at=now_ns,
                    rule_id="QUAL-LIVE-SEQ-001",
                    rule_version="1.0.0",
                    evidence_refs=[event_id],
                ).finalize()
            )
        session.seen_event_ids.add(event_id)

        observations.extend(
            self._flags_to_observations(flags, scope=scope, available_time=received_ns, event_id=event_id)
        )

        sequence = record.get("sequence")
        if sequence is not None:
            try:
                current = int(sequence)
                if session.prior_sequence is not None and current < session.prior_sequence:
                    observations.append(
                        QualityObservation(
                            dimension="sequencing",
                            state="REGRESSION",
                            severity="ERROR",
                            scope=scope,
                            available_time=received_ns,
                            detected_at=now_ns,
                            rule_id="QUAL-LIVE-SEQ-002",
                            rule_version="1.0.0",
                            evidence_refs=[event_id],
                        ).finalize()
                    )
                session.prior_sequence = current
            except (TypeError, ValueError):
                pass
        session.prior_event_time_ns = event_time_ns

        return self._finalize(record, envelope, observations, flags)

    def _finalize(
        self,
        record: dict[str, Any],
        envelope: dict[str, Any] | None,
        observations: list[dict[str, Any]],
        flags: tuple[str, ...],
    ) -> dict[str, Any]:
        blocking_errors = [
            row
            for row in observations
            if row.get("severity") == "ERROR"
            and row.get("state")
            in {
                "INVALID_QUOTE",
                "REGRESSION",
                "CLOCK_DRIFT",
                "STALE",
                "PROVIDER_DISCONNECTED",
                "ENTITLEMENT_MISSING",
            }
        ]
        eligibility, reasons = consumer_eligibility(observations)
        if blocking_errors:
            eligibility = "BLOCKED"
            reasons = sorted(
                set(reasons)
                | {f"QUAL_BLOCKED_{row['dimension'].upper()}_{row['state']}" for row in blocking_errors}
            )
        display = ADMISSION_BLOCKED if eligibility == "BLOCKED" else ADMISSION_DISPLAY
        execution = ADMISSION_BLOCKED
        if eligibility != "BLOCKED":
            blocking_dims = {row["dimension"] for row in observations if row.get("severity") == "ERROR"}
            warn_only = all(row.get("severity") != "ERROR" for row in observations)
            if not blocking_dims and warn_only:
                execution = ADMISSION_EXECUTION
            elif blocking_dims <= {"timeliness"} and not any(
                row.get("state") in {"STALE", "CLOCK_DRIFT", "PROVIDER_DISCONNECTED"} for row in observations
            ):
                execution = ADMISSION_DEGRADED
            else:
                execution = ADMISSION_BLOCKED if blocking_dims else ADMISSION_DEGRADED
        if any(row.get("state") in {"INITIAL_CACHED_EVENT", "SNAPSHOT_UPDATE_MISMATCH"} for row in observations):
            execution = ADMISSION_BLOCKED
        if any(
            row.get("state") in {"EXECUTION_STALE", "STALE", "PROVIDER_DISCONNECTED", "ENTITLEMENT_MISSING"}
            for row in observations
        ):
            execution = ADMISSION_BLOCKED

        return {
            "admission": {
                "display": display,
                "execution": execution,
            },
            "consumer_eligibility": eligibility,
            "eligibility_reason_codes": reasons,
            "envelope": envelope,
            "observations": observations,
            "quality_flags": sorted(set(flags)),
            "record": record,
        }

    def on_reconnect(self) -> None:
        for session in self.sessions.values():
            session.reconnect_generation += 1
            session.prior_sequence = None
            session.first_push_seen = False

    def on_disconnect(self) -> None:
        self.provider_connected = False

    def on_connect(self) -> None:
        self.provider_connected = True
