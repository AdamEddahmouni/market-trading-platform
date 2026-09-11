"""Account-scoped in-memory forward-test persistence."""

from __future__ import annotations

from dataclasses import dataclass, field

from .repository import (
    assert_locked_decision_immutable,
    assert_observations_append_only,
    assert_session_config_immutable,
)
from .types import ForwardTestDecision, ForwardTestSession


@dataclass
class ForwardTestStore:
    """In-memory forward-test records keyed by account."""

    _sessions: dict[str, ForwardTestSession] = field(default_factory=dict)
    _decisions: dict[str, ForwardTestDecision] = field(default_factory=dict)
    _by_account_sessions: dict[str, list[str]] = field(default_factory=dict)
    _by_account_decisions: dict[str, list[str]] = field(default_factory=dict)
    _paper_submission_keys: set[str] = field(default_factory=set)
    _evaluation_keys: set[str] = field(default_factory=set)

    def put_session(self, session: ForwardTestSession) -> None:
        existing = self._sessions.get(session.session_id)
        if existing is not None:
            assert_session_config_immutable(existing, session)
        self._sessions[session.session_id] = session
        bucket = self._by_account_sessions.setdefault(session.account_id, [])
        if session.session_id not in bucket:
            bucket.append(session.session_id)

    def get_session(self, session_id: str) -> ForwardTestSession | None:
        return self._sessions.get(session_id)

    def list_sessions(self, *, account_id: str) -> list[ForwardTestSession]:
        ids = self._by_account_sessions.get(account_id, [])
        return [self._sessions[item] for item in ids if item in self._sessions]

    def put_decision(self, decision: ForwardTestDecision) -> None:
        existing = self._decisions.get(decision.forward_test_id)
        if existing is not None:
            assert_locked_decision_immutable(existing, decision)
            assert_observations_append_only(existing, decision)
        self._decisions[decision.forward_test_id] = decision
        bucket = self._by_account_decisions.setdefault(decision.account_id, [])
        if decision.forward_test_id not in bucket:
            bucket.append(decision.forward_test_id)

    def get_decision(self, forward_test_id: str) -> ForwardTestDecision | None:
        return self._decisions.get(forward_test_id)

    def list_decisions(
        self,
        *,
        account_id: str,
        session_id: str | None = None,
    ) -> list[ForwardTestDecision]:
        ids = self._by_account_decisions.get(account_id, [])
        rows = [self._decisions[item] for item in ids if item in self._decisions]
        if session_id is None:
            return rows
        return [row for row in rows if row.session_id == session_id]

    def claim_paper_submission(self, forward_test_id: str) -> bool:
        if forward_test_id in self._paper_submission_keys:
            return False
        self._paper_submission_keys.add(forward_test_id)
        return True

    def claim_evaluation(self, forward_test_id: str) -> bool:
        if forward_test_id in self._evaluation_keys:
            return False
        self._evaluation_keys.add(forward_test_id)
        return True

    def release_evaluation_claim(self, forward_test_id: str) -> None:
        self._evaluation_keys.discard(forward_test_id)
