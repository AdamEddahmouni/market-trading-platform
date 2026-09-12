"""Account-scoped in-memory forward-test persistence."""

from __future__ import annotations

from dataclasses import dataclass, field

from ...clock import monotonic_wall_ns
from .campaign_binding import CampaignBinding, CampaignBindingError, CampaignBindingState
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
    _campaign_bindings: dict[str, CampaignBinding] = field(default_factory=dict)
    _active_campaign_by_account: dict[str, str] = field(default_factory=dict)

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

    def claim_active_binding(self, binding: CampaignBinding) -> None:
        active = self.get_active_binding(account_id=binding.account_id)
        if active is not None:
            if active.campaign_id != binding.campaign_id:
                raise CampaignBindingError("FORWARD_TEST_CONCURRENT_CAMPAIGN_ACTIVE")
            if active.manifest_fingerprint != binding.manifest_fingerprint:
                raise CampaignBindingError("ACTIVATION_MANIFEST_FINGERPRINT_MISMATCH")
            if active.protocol_sha256 != binding.protocol_sha256:
                raise CampaignBindingError("PROTOCOL_REF_DOC_SHA256_MISMATCH")
            return
        self._campaign_bindings[binding.campaign_id] = binding
        self._active_campaign_by_account[binding.account_id] = binding.campaign_id

    def get_active_binding(self, *, account_id: str) -> CampaignBinding | None:
        campaign_id = self._active_campaign_by_account.get(account_id)
        if campaign_id is None:
            return None
        binding = self._campaign_bindings.get(campaign_id)
        if binding is None or binding.campaign_state != CampaignBindingState.ACTIVE:
            return None
        return binding

    def release_binding(
        self,
        *,
        account_id: str,
        campaign_id: str | None = None,
        released_at_ns: int | None = None,
    ) -> CampaignBinding | None:
        active = self.get_active_binding(account_id=account_id)
        if active is None:
            return None
        if campaign_id and active.campaign_id != campaign_id:
            return None
        now_ns = released_at_ns or monotonic_wall_ns()
        released = CampaignBinding(
            campaign_id=active.campaign_id,
            account_id=active.account_id,
            manifest_fingerprint=active.manifest_fingerprint,
            manifest_path=active.manifest_path,
            protocol_id=active.protocol_id,
            protocol_sha256=active.protocol_sha256,
            campaign_state=CampaignBindingState.RELEASED,
            activated_at_ns=active.activated_at_ns,
            first_lock_at_ns=active.first_lock_at_ns,
            forward_test_session_id=active.forward_test_session_id,
            created_at_ns=active.created_at_ns,
            updated_at_ns=now_ns,
        )
        self._campaign_bindings[active.campaign_id] = released
        self._active_campaign_by_account.pop(account_id, None)
        return released

    def record_first_lock_at_ns(
        self,
        *,
        account_id: str,
        campaign_id: str,
        first_lock_at_ns: int,
    ) -> None:
        active = self.get_active_binding(account_id=account_id)
        if active is None or active.campaign_id != campaign_id:
            return
        if active.first_lock_at_ns is not None:
            return
        now_ns = monotonic_wall_ns()
        updated = CampaignBinding(
            campaign_id=active.campaign_id,
            account_id=active.account_id,
            manifest_fingerprint=active.manifest_fingerprint,
            manifest_path=active.manifest_path,
            protocol_id=active.protocol_id,
            protocol_sha256=active.protocol_sha256,
            campaign_state=active.campaign_state,
            activated_at_ns=active.activated_at_ns,
            first_lock_at_ns=first_lock_at_ns,
            forward_test_session_id=active.forward_test_session_id,
            created_at_ns=active.created_at_ns,
            updated_at_ns=now_ns,
        )
        self._campaign_bindings[active.campaign_id] = updated
