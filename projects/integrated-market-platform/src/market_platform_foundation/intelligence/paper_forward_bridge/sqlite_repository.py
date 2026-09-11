"""SQLite-backed forward-test repository (PLATFORM-STATE-001)."""

from __future__ import annotations

import json

from ...clock import monotonic_wall_ns
from ...local_state.connection import LocalStateConnection
from .repository import (
    assert_locked_decision_immutable,
    assert_observations_append_only,
    decision_from_row,
    decision_to_row,
    observation_from_row,
    session_from_row,
    session_to_row,
)
from .types import ForwardTestDecision, ForwardTestObservation, ForwardTestSession

CLAIM_PAPER_SUBMISSION = "paper_submission"
CLAIM_EVALUATION = "evaluation"


class SqliteForwardTestRepository:
    def __init__(self, connection: LocalStateConnection) -> None:
        self._connection = connection

    def put_session(self, session: ForwardTestSession) -> None:
        row = session_to_row(session)
        self._connection.execute(
            """
            INSERT INTO forward_test_sessions(
                session_id, account_id, mode, strategy_id, strategy_version,
                universe_json, evaluation_horizon_ns, created_at_ns, status, config_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(session_id) DO UPDATE SET
                status=excluded.status,
                config_json=excluded.config_json
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
            ),
        )

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
        existing = self.get_decision(decision.forward_test_id)
        if existing is not None:
            assert_locked_decision_immutable(existing, decision)
            assert_observations_append_only(existing, decision)
        row = decision_to_row(decision)
        self._connection.execute(
            """
            INSERT INTO forward_test_decisions(
                forward_test_id, session_id, account_id, mode, run_kind, test_mode,
                symbol, decision_time_ns, source_time_ns, state, direction, quantity,
                confidence, strategy_id, strategy_version, research_artifact_ref,
                evaluation_horizon_ns, decision_payload_json, provenance_snapshot_json,
                paper_order_id, paper_intent_id, locked_at_ns, submitted_at_ns,
                signal_outcome_json, execution_outcome_json, evaluation_state, failure_reason
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(forward_test_id) DO UPDATE SET
                state=excluded.state,
                paper_order_id=excluded.paper_order_id,
                paper_intent_id=excluded.paper_intent_id,
                locked_at_ns=excluded.locked_at_ns,
                submitted_at_ns=excluded.submitted_at_ns,
                signal_outcome_json=excluded.signal_outcome_json,
                execution_outcome_json=excluded.execution_outcome_json,
                evaluation_state=excluded.evaluation_state,
                failure_reason=excluded.failure_reason
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
    ) -> list[ForwardTestDecision]:
        if session_id is None:
            rows = self._connection.execute(
                """
                SELECT * FROM forward_test_decisions
                WHERE account_id=?
                ORDER BY decision_time_ns ASC
                """,
                (account_id,),
            ).fetchall()
        else:
            rows = self._connection.execute(
                """
                SELECT * FROM forward_test_decisions
                WHERE account_id=? AND session_id=?
                ORDER BY decision_time_ns ASC
                """,
                (account_id, session_id),
            ).fetchall()
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

    def release_evaluation_claim(self, forward_test_id: str) -> None:
        self._connection.execute(
            """
            DELETE FROM forward_test_claims
            WHERE forward_test_id=? AND claim_type=?
            """,
            (forward_test_id, CLAIM_EVALUATION),
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
        for observation in observations:
            self._connection.execute(
                """
                INSERT OR IGNORE INTO forward_test_observations(
                    observation_id, forward_test_id, observed_at_ns, source_time_ns, payload_json
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    observation.observation_id,
                    forward_test_id,
                    observation.observed_at_ns,
                    observation.source_time_ns,
                    json.dumps(observation.payload, sort_keys=True, separators=(",", ":")),
                ),
            )
