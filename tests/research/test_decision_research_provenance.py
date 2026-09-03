"""Task 8 — paper intent provenance (DEC-MAN-001) + research→order boundary.

``build_user_order_intent`` gains an optional ``research_candidate_id`` so a
manual paper order can cite the decision candidate it came from, and
``normalize_execution_intent`` forwards it (audit F6). Unknown / malformed ids
fail closed at intent build. A static import-boundary test proves that loading
the decision-research package never pulls in the order-execution path.
"""

from __future__ import annotations

import sys
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from market_platform_foundation.paper.contracts import (
    build_instrument_ref,
    build_user_order_intent,
    normalize_execution_intent,
)

GOOD_CANDIDATE_ID = "CAND-" + str(
    uuid.uuid5(uuid.UUID("6ba7b811-9dad-11d1-80b4-00c04fd430c8"), "test")
)


def _intent(**overrides) -> dict:
    instrument = build_instrument_ref(instrument_id="TEST-1", symbol="BIYA")
    params = dict(
        instrument=instrument,
        side="BUY",
        quantity=100,
        observation_time=1_784_500_000_000_000_000,
        order_type="MARKET",
        client_order_id="c1",
        idempotency_key="k1",
        research_candidate_id=GOOD_CANDIDATE_ID,
    )
    params.update(overrides)
    return build_user_order_intent(**params)


class ResearchCandidateProvenanceTests(unittest.TestCase):
    def test_candidate_id_recorded_on_intent(self) -> None:
        intent = _intent()
        self.assertEqual(intent["research_candidate_id"], GOOD_CANDIDATE_ID)
        self.assertTrue(intent["intent_id"])

    def test_provenance_is_part_of_intent_identity(self) -> None:
        with_id = _intent()
        without_id = _intent(research_candidate_id=None)
        self.assertNotIn("research_candidate_id", without_id)
        self.assertNotEqual(with_id["intent_id"], without_id["intent_id"])

    def test_candidate_id_preserved_through_normalize(self) -> None:
        normalized = normalize_execution_intent(_intent())
        self.assertEqual(normalized["research_candidate_id"], GOOD_CANDIDATE_ID)

    def test_normalize_drops_absent_provenance(self) -> None:
        normalized = normalize_execution_intent(_intent(research_candidate_id=None))
        self.assertNotIn("research_candidate_id", normalized)

    def test_malformed_candidate_id_fails_closed(self) -> None:
        with self.assertRaises(ValueError):
            _intent(research_candidate_id="not-a-candidate")
        with self.assertRaises(ValueError):
            _intent(research_candidate_id="CAND-not-a-real-uuid")
        with self.assertRaises(ValueError):
            _intent(research_candidate_id="")


class ResearchToOrderImportBoundaryTests(unittest.TestCase):
    # Modules that constitute the order-execution path — research must never
    # reach any of them (a candidate is synthesized, never auto-executed).
    ORDER_EXECUTION_MODULES = (
        "market_platform_foundation.paper.execution",
        "market_platform_foundation.paper.ledger",
        "market_platform_foundation.execution.simulator",
        "market_platform_foundation.risk.decision",
    )

    def test_decision_research_has_no_import_path_to_order_creation(self) -> None:
        # Importing the research package in a CLEAN interpreter must not pull in
        # the order-execution path. Run in a subprocess so this test module's own
        # `paper.contracts` import (which triggers paper/__init__) can't pollute
        # sys.modules — that import would mask the boundary being tested.
        import json
        import os
        import subprocess
        import sys as sys_module

        code = (
            "import json, sys; "
            "import market_platform_foundation.research.decision_research as m; "
            "loaded = [n for n in sys.modules if n.startswith('market_platform_foundation.')]; "
            "print(json.dumps(sorted(loaded)))"
        )
        env = dict(os.environ)
        env["PYTHONPATH"] = str(SRC)
        proc = subprocess.run(
            [sys_module.executable, "-c", code],
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        loaded = json.loads(proc.stdout)
        violated = [name for name in loaded if name in self.ORDER_EXECUTION_MODULES]
        self.assertEqual(violated, [])

    def test_research_layer_module_sources_never_refer_to_order_execution(self) -> None:
        # Source-level scan of the whole research layer: no reference to the
        # order-execution / ledger / simulator path may appear anywhere.
        import pkgutil

        import market_platform_foundation.research as research_pkg

        pkg_path = list(research_pkg.__path__)[0]
        forbidden = ("paper.execution", "paper.ledger", "from ..execution", "execution.simulator")
        violations: list[tuple[str, str]] = []
        for module_info in pkgutil.walk_packages([pkg_path], prefix=f"{research_pkg.__name__}."):
            try:
                module_spec = module_info.module_finder.find_spec(module_info.name, None)
                if module_spec is None or not module_spec.origin or not module_spec.origin.endswith(".py"):
                    continue
                text = Path(module_spec.origin).read_text(encoding="utf-8")
            except (OSError, ValueError):
                continue
            for token in forbidden:
                if token in text:
                    violations.append((module_info.name, token))
        self.assertEqual(violations, [])


if __name__ == "__main__":
    unittest.main()
