"""Current-state read views — covered by reader stream tests."""

from __future__ import annotations

import unittest

from market_platform_foundation.of01.protocols import DispositionScope, DispositionSelectionPolicyV1
from market_platform_foundation.of01.readers import SQLiteLedgerReader
from market_platform_foundation.of01.records import ActionCategory, ActorType
from tests.of01.support import DisposableAuthority
from tests.of01.test_readers_stream import _register_run_envelope


class TestCurrentState(unittest.TestCase):
    def test_run_view_cites_commit_sequence(self) -> None:
        auth = DisposableAuthority()
        try:
            writer = auth.open_writer()
            envelope = _register_run_envelope(auth.authority_id)
            run_id = envelope.command.run.run_id  # type: ignore[attr-defined]
            writer.submit(envelope)
            writer.close()
            reader = SQLiteLedgerReader(auth.store)
            policy = DispositionSelectionPolicyV1(
                scope=DispositionScope.RUN.value,
                allowed_authority_types=frozenset({ActorType.SYSTEM.value}),
                allowed_action_categories=frozenset({ActionCategory.NO_ACTION.value}),
            )
            view = reader.get_run(run_id, policy)
            self.assertIsNotNone(view)
            assert view is not None
            self.assertGreaterEqual(view.as_of_commit_sequence, 1)
            self.assertEqual(view.current_state, "REGISTERED")
        finally:
            auth.close()


if __name__ == "__main__":
    unittest.main()
