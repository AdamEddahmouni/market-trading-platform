"""SQLite-backed forward-test repository (PLATFORM-STATE-001)."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from ...clock import monotonic_wall_ns
from ...local_state.connection import LocalStateConnection
from .run_identity import run_identity
from .campaign_binding import (
    CampaignBinding,
    CampaignBindingError,
    get_active_binding as sqlite_get_active_binding,
    record_first_lock_at_ns as sqlite_record_first_lock_at_ns,
    release_binding as sqlite_release_binding,
)
from .repository import (
    ForwardTestRepositoryError,
    assert_locked_decision_immutable,
    assert_observations_append_only,
    assert_session_config_immutable,
    decision_from_row,
    decision_to_row,
    observation_from_row,
    session_from_row,
    session_to_row,
)
from .types import ForwardTestDecision, ForwardTestObservation, ForwardTestSession

CLAIM_PAPER_SUBMISSION = "paper_submission"
CLAIM_EVALUATION = "evaluation"
_LIVE_MODE_FORBIDDEN = "FORWARD_TEST_LIVE_MODE_FORBIDDEN"


def _reject_live_mode(mode: str) -> None:
    if str(mode).upper() == "LIVE":
        raise ForwardTestRepositoryError(_LIVE_MODE_FORBIDDEN)


class SqliteForwardTestRepository:
    def __init__(self, connection: LocalStateConnection) -> None:
        self._connection = connection

    def close(self) -> None:
        self._connection.close()

    def _run_write(self, callback):
        if self._connection.in_transaction:
            return callback()
        with self._connection.transaction():
            return callback()

    def put_session(self, session: ForwardTestSession) -> None:
        _reject_live_mode(session.mode)
        existing = self.get_session(session.session_id)
        if existing is not None:
            assert_session_config_immutable(existing, session)
        row = session_to_row(session)
        identity = run_identity()
        persist_time_ns = monotonic_wall_ns()

        def _write() -> None:
            self._connection.execute(
                """
                INSERT INTO forward_test_sessions(
                    session_id, account_id, mode, strategy_id, strategy_version,
                    universe_json, evaluation_horizon_ns, created_at_ns, status, config_json,
                    campaign_id, protocol_id, activation_version, manifest_fingerprint,
                    cohort_arm, config_frozen, git_sha, simulator_version, persist_time_ns
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    status=excluded.status,
                    config_json=excluded.config_json,
                    config_frozen=excluded.config_frozen,
                    persist_time_ns=excluded.persist_time_ns
                """,
                (
                    row["session_id"],
                    row["account_id"],
                    row["mode"],
                    row["strategy_id"],
                    row["strategy_version"],
                    row["universe_json"],
                    row["evaluation_horizon_ns"],
                    row["created_at_ns"],
                    row["status"],
                    row["config_json"],
                    row["campaign_id"],
                    row["protocol_id"],
                    row["activation_version"],
                    row["manifest_fingerprint"],
                    row["cohort_arm"],
                    row["config_frozen"],
                    identity["git_sha"],
                    identity["simulator_version"],
                    persist_time_ns,
                ),
            )

        self._run_write(_write)

    def get_session(self, session_id: str) -> ForwardTestSession | None:
        row = self._connection.execute(
            "SELECT * FROM forward_test_sessions WHERE session_id=?",
            (session_id,),
        ).fetchone()
        return None if row is None else session_from_row(dict(row))

    def list_sessions(self, *, account_id: str) -> list[ForwardTestSession]:
        rows = self._connection.execute(
            """
            SELECT * FROM forward_test_sessions
            WHERE account_id=?
            ORDER BY created_at_ns ASC
            """,
            (account_id,),
        ).fetchall()
        return [session_from_row(dict(row)) for row in rows]

    def put_decision(self, decision: ForwardTestDecision) -> None:
        _reject_live_mode(decision.mode)

        def _write() -> None:
            self._put_decision_body(decision)

        self._run_write(_write)

    def _put_decision_body(self, decision: ForwardTestDecision) -> None:
        existing = self.get_decision(decision.forward_test_id)
        if existing is not None:
            assert_locked_decision_immutable(existing, decision)
            assert_observations_append_only(existing, decision)
        row = decision_to_row(decision)
        identity = run_identity()
        persist_time_ns = monotonic_wall_ns()
        available_time_ns = int(
            (decision.provenance_snapshot or {}).get("available_time_ns")
            or decision.source_time_ns
        )
        receive_time_ns = int(
            (decision.provenance_snapshot or {}).get("receive_time_ns")
            or persist_time_ns
        )
        self._connection.execute(
            """
            INSERT INTO forward_test_decisions(
                forward_test_id, session_id, account_id, mode, run_kind, test_mode,
                symbol, decision_time_ns, source_time_ns, state, direction, quantity,
                confidence, strategy_id, strategy_version, research_artifact_ref,
                evaluation_horizon_ns, decision_payload_json, provenance_snapshot_json,
                paper_order_id, paper_intent_id, locked_at_ns, submitted_at_ns,
                signal_outcome_json, execution_outcome_json, evaluation_state, failure_reason,
                evidence_class, cohort_arm, persist_time_ns, available_time_ns,
                receive_time_ns, git_sha, simulator_version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(forward_test_id) DO UPDATE SET
                state=excluded.state,
                paper_order_id=excluded.paper_order_id,
                paper_intent_id=excluded.paper_intent_id,
                locked_at_ns=excluded.locked_at_ns,
                submitted_at_ns=excluded.submitted_at_ns,
                signal_outcome_json=excluded.signal_outcome_json,
                execution_outcome_json=excluded.execution_outcome_json,
                evaluation_state=excluded.evaluation_state,
                failure_reason=excluded.failure_reason,
                persist_time_ns=excluded.persist_time_ns
            """,
            (
                row["forward_test_id"],
                row["session_id"],
                row["account_id"],
                row["mode"],
                row["run_kind"],
                row["test_mode"],
                row["symbol"],
                row["decision_time_ns"],
                row["source_time_ns"],
                row["state"],
                row["direction"],
                row["quantity"],
                row["confidence"],
                row["strategy_id"],
                row["strategy_version"],
                row["research_artifact_ref"],
                row["evaluation_horizon_ns"],
                row["decision_payload_json"],
                row["provenance_snapshot_json"],
                row["paper_order_id"],
                row["paper_intent_id"],
                row["locked_at_ns"],
                row["submitted_at_ns"],
                row["signal_outcome_json"],
                row["execution_outcome_json"],
                row["evaluation_state"],
                row["failure_reason"],
                row["evidence_class"],
                row["cohort_arm"],
                persist_time_ns,
                available_time_ns,
                receive_time_ns,
                identity["git_sha"],
                identity["simulator_version"],
            ),
        )
        if existing is None:
            self._insert_observations(decision.forward_test_id, decision.observations)
        else:
            existing_ids = {item.observation_id for item in existing.observations}
            new_observations = tuple(
                item for item in decision.observations if item.observation_id not in existing_ids
            )
            self._insert_observations(decision.forward_test_id, new_observations)
        opportunity_id = (decision.decision_payload or {}).get("opportunity_id")
        signal_id = (decision.decision_payload or {}).get("signal_id")
        if opportunity_id:
            self._connection.execute(
                """
                INSERT OR IGNORE INTO forward_test_signal_links(
                    forward_test_id, opportunity_id, signal_id, persist_time_ns
                ) VALUES (?, ?, ?, ?)
                """,
                (decision.forward_test_id, str(opportunity_id), signal_id, persist_time_ns),
            )

    def get_decision(self, forward_test_id: str) -> ForwardTestDecision | None:
        row = self._connection.execute(
            "SELECT * FROM forward_test_decisions WHERE forward_test_id=?",
            (forward_test_id,),
        ).fetchone()
        if row is None:
            return None
        observations = self._load_observations(forward_test_id)
        return decision_from_row(dict(row), observations)

    def list_decisions(
        self,
        *,
        account_id: str,
        session_id: str | None = None,
        campaign_id: str | None = None,
        strategy_id: str | None = None,
        symbol: str | None = None,
    ) -> list[ForwardTestDecision]:
        sql = """
            SELECT d.* FROM forward_test_decisions d
            LEFT JOIN forward_test_sessions s ON d.session_id = s.session_id
            WHERE d.account_id=?
        """
        params: list[Any] = [account_id]
        if session_id is not None:
            sql += " AND d.session_id=?"
            params.append(session_id)
        if campaign_id is not None:
            sql += " AND s.campaign_id=?"
            params.append(campaign_id)
        if strategy_id is not None:
            sql += " AND d.strategy_id=?"
            params.append(strategy_id)
        if symbol is not None:
            sql += " AND d.symbol=?"
            params.append(str(symbol).upper())
        sql += " ORDER BY d.decision_time_ns ASC"
        rows = self._connection.execute(sql, tuple(params)).fetchall()
        decisions: list[ForwardTestDecision] = []
        for row in rows:
            forward_test_id = str(row["forward_test_id"])
            observations = self._load_observations(forward_test_id)
            decisions.append(decision_from_row(dict(row), observations))
        return decisions

    def claim_paper_submission(self, forward_test_id: str) -> bool:
        cursor = self._connection.execute(
            """
            INSERT OR IGNORE INTO forward_test_claims(
                forward_test_id, claim_type, claimed_at_ns
            ) VALUES (?, ?, ?)
            """,
            (forward_test_id, CLAIM_PAPER_SUBMISSION, monotonic_wall_ns()),
        )
        return cursor.rowcount == 1

    def claim_evaluation(self, forward_test_id: str) -> bool:
        cursor = self._connection.execute(
            """
            INSERT OR IGNORE INTO forward_test_claims(
                forward_test_id, claim_type, claimed_at_ns
            ) VALUES (?, ?, ?)
            """,
            (forward_test_id, CLAIM_EVALUATION, monotonic_wall_ns()),
        )
        return cursor.rowcount == 1

    def commit_paper_submission(self, forward_test_id: str, decision: ForwardTestDecision) -> bool:
        def _write() -> bool:
            if not self.claim_paper_submission(forward_test_id):
                return False
            self._put_decision_body(decision)
            return True

        return bool(self._run_write(_write))

    def commit_evaluation(self, forward_test_id: str, decision: ForwardTestDecision) -> bool:
        def _write() -> bool:
            if not self.claim_evaluation(forward_test_id):
                return False
            self._put_decision_body(decision)
            return True

        return bool(self._run_write(_write))

    def release_evaluation_claim(self, forward_test_id: str) -> None:
        self._connection.execute(
            """
            DELETE FROM forward_test_claims
            WHERE forward_test_id=? AND claim_type=?
            """,
            (forward_test_id, CLAIM_EVALUATION),
        )

    def claim_active_binding(self, binding: CampaignBinding) -> None:
        active = sqlite_get_active_binding(self._connection, account_id=binding.account_id)
        if active is not None:
            if active.campaign_id != binding.campaign_id:
                raise CampaignBindingError("FORWARD_TEST_CONCURRENT_CAMPAIGN_ACTIVE")
            if active.manifest_fingerprint != binding.manifest_fingerprint:
                raise CampaignBindingError("ACTIVATION_MANIFEST_FINGERPRINT_MISMATCH")
            if active.protocol_sha256 != binding.protocol_sha256:
                raise CampaignBindingError("PROTOCOL_REF_DOC_SHA256_MISMATCH")
            # One ACTIVE row per campaign; additional cohort-arm sessions reuse it.
            return
        try:
            self._connection.execute(
                """
                INSERT INTO forward_test_campaign_bindings(
                    campaign_id, account_id, manifest_fingerprint, manifest_path,
                    protocol_id, protocol_sha256, campaign_state, activated_at_ns,
                    first_lock_at_ns, forward_test_session_id, created_at_ns, updated_at_ns
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    binding.campaign_id,
                    binding.account_id,
                    binding.manifest_fingerprint,
                    binding.manifest_path,
                    binding.protocol_id,
                    binding.protocol_sha256,
                    binding.campaign_state.value,
                    binding.activated_at_ns,
                    binding.first_lock_at_ns,
                    binding.forward_test_session_id,
                    binding.created_at_ns,
                    binding.updated_at_ns,
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise CampaignBindingError("FORWARD_TEST_CONCURRENT_CAMPAIGN_ACTIVE") from exc

    def get_active_binding(self, *, account_id: str) -> CampaignBinding | None:
        return sqlite_get_active_binding(self._connection, account_id=account_id)

    def release_binding(
        self,
        *,
        account_id: str,
        campaign_id: str | None = None,
        released_at_ns: int | None = None,
    ) -> CampaignBinding | None:
        return sqlite_release_binding(
            self._connection,
            account_id=account_id,
            campaign_id=campaign_id,
            released_at_ns=released_at_ns,
        )

    def record_first_lock_at_ns(
        self,
        *,
        account_id: str,
        campaign_id: str,
        first_lock_at_ns: int,
    ) -> None:
        sqlite_record_first_lock_at_ns(
            self._connection,
            account_id=account_id,
            campaign_id=campaign_id,
            first_lock_at_ns=first_lock_at_ns,
        )

    def _load_observations(self, forward_test_id: str) -> tuple[ForwardTestObservation, ...]:
        rows = self._connection.execute(
            """
            SELECT * FROM forward_test_observations
            WHERE forward_test_id=?
            ORDER BY observed_at_ns ASC, observation_id ASC
            """,
            (forward_test_id,),
        ).fetchall()
        return tuple(observation_from_row(dict(row)) for row in rows)

    def _insert_observations(
        self,
        forward_test_id: str,
        observations: tuple[ForwardTestObservation, ...],
    ) -> None:
        persist_time_ns = monotonic_wall_ns()
        for observation in observations:
            payload_json = json.dumps(observation.payload, sort_keys=True, separators=(",", ":"))
            existing = self._connection.execute(
                """
                SELECT payload_json FROM forward_test_observations
                WHERE observation_id=?
                """,
                (observation.observation_id,),
            ).fetchone()
            if existing is not None and str(existing[0]) != payload_json:
                raise ForwardTestRepositoryError("FORWARD_TEST_OBSERVATION_PAYLOAD_CONFLICT")
            available_time_ns = int(
                observation.payload.get("available_time_ns") or observation.source_time_ns
            )
            receive_time_ns = int(
                observation.payload.get("receive_time_ns") or observation.observed_at_ns
            )
            self._connection.execute(
                """
                INSERT OR IGNORE INTO forward_test_observations(
                    observation_id, forward_test_id, observed_at_ns, source_time_ns,
                    payload_json, persist_time_ns, available_time_ns, receive_time_ns
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    observation.observation_id,
                    forward_test_id,
                    observation.observed_at_ns,
                    observation.source_time_ns,
                    payload_json,
                    persist_time_ns,
                    available_time_ns,
                    receive_time_ns,
                ),
            )
