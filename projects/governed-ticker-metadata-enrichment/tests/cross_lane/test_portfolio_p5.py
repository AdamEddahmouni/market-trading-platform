"""Tests for SHARED P5 cross-lane portfolio intelligence."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.cross_lane.opportunity import (  # noqa: E402
    FusedOpportunity,
)
from market_platform_foundation.cross_lane.portfolio import (  # noqa: E402
    PORTFOLIO_METHOD,
    PORTFOLIO_VIEW_VERSION,
    PortfolioPosition,
    PortfolioQualityFlag,
    PortfolioStance,
    build_portfolio_view,
    detect_contradictions,
    detect_overlap_groups,
    resolve_correlation_group,
    stance_from_template,
)

AS_OF = "2026-08-22T15:00:00Z"


def _fusion(
    net_ev: float | None = 100.0,
    template: str | None = "long_call_atm",
    squeeze_aligned: bool = False,
) -> FusedOpportunity:
    return FusedOpportunity(
        fused_net_ev=net_ev,
        occurrence_weight=1.0,
        liquidity_factor=1.0,
        gross_ev_before_weights=net_ev if net_ev is not None else 0.0,
        template=template,
        squeeze_aligned=squeeze_aligned,
    )


def _position(
    pid: str,
    symbol: str,
    lane: str,
    fusion: FusedOpportunity,
    evidence_ids: tuple[str, ...] = (),
    **kwargs,
) -> PortfolioPosition:
    return PortfolioPosition(
        position_id=pid,
        symbol=symbol,
        lane=lane,
        fusion=fusion,
        evidence_ids=evidence_ids,
        **kwargs,
    )


class StanceDerivationTests(unittest.TestCase):
    def test_directional_templates(self) -> None:
        self.assertEqual(stance_from_template("long_call_atm"), PortfolioStance.BULLISH)
        self.assertEqual(stance_from_template("bull_call_spread"), PortfolioStance.BULLISH)
        self.assertEqual(stance_from_template("long_otm_call"), PortfolioStance.BULLISH)
        self.assertEqual(stance_from_template("outright_trend_long"), PortfolioStance.BULLISH)

    def test_bearish_and_non_directional_templates(self) -> None:
        self.assertEqual(stance_from_template("long_put_atm"), PortfolioStance.BEARISH)
        self.assertEqual(stance_from_template("bear_put_spread"), PortfolioStance.BEARISH)
        self.assertEqual(stance_from_template("outright_trend_short"), PortfolioStance.BEARISH)
        self.assertEqual(stance_from_template("long_straddle"), PortfolioStance.NON_DIRECTIONAL)

    def test_unknown_templates_never_directional(self) -> None:
        self.assertEqual(stance_from_template(None), PortfolioStance.UNKNOWN)
        self.assertEqual(stance_from_template("mystery_template_v9"), PortfolioStance.NON_DIRECTIONAL)


class OverlapTests(unittest.TestCase):
    def test_same_evidence_via_two_lanes_counted_once(self) -> None:
        positions = [
            _position("ss-1", "GME", "short_squeeze", _fusion(), ("ev-borrow", "ev-si")),
            _position(
                "of-1", "GME", "order_flow", _fusion(net_ev=50.0), ("ev-borrow", "ev-cvd")
            ),
        ]
        view = build_portfolio_view(positions, as_of_time=AS_OF).to_dict()

        self.assertEqual(len(view["overlap_groups"]), 1)
        group = view["overlap_groups"][0]
        self.assertEqual(sorted(group["member_position_ids"]), ["of-1", "ss-1"])
        self.assertEqual(group["shared_evidence_ids"], ["ev-borrow"])
        # 4 citations, 3 unique -> one duplicated underlying item.
        self.assertAlmostEqual(group["net_unique_evidence_fraction"], round(3 / 4, 6))
        self.assertAlmostEqual(view["net_unique_evidence_fraction"], round(3 / 4, 6))

        by_id = {row["position_id"]: row for row in view["ranked_positions"]}
        for pid in ("ss-1", "of-1"):
            self.assertIn(PortfolioQualityFlag.EVIDENCE_OVERLAP.value, by_id[pid]["quality_flags"])
            self.assertEqual(by_id[pid]["rank_tier"], 1)

    def test_shared_event_key_without_evidence_intersection(self) -> None:
        linked = [
            _position("a2", "NVDA", "options", _fusion(), ("ev-a",), underlying_event_key="earnings-q3"),
            _position("b2", "NVDA", "futures", _fusion(), ("ev-b",), underlying_event_key="earnings-q3"),
        ]
        groups = detect_overlap_groups(linked)
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0].shared_evidence_ids, ())
        self.assertEqual(groups[0].shared_event_keys, ("earnings-q3",))

    def test_no_overlap_for_disjoint_positions(self) -> None:
        positions = [
            _position("x", "AAPL", "options", _fusion(), ("ev-x",)),
            _position("y", "MSFT", "crypto", _fusion(), ("ev-y",)),
        ]
        view = build_portfolio_view(positions, as_of_time=AS_OF).to_dict()
        self.assertEqual(view["overlap_groups"], [])
        self.assertAlmostEqual(view["net_unique_evidence_fraction"], 1.0)
        self.assertTrue(all(row["rank_tier"] == 0 for row in view["ranked_positions"]))


class CorrelationGroupTests(unittest.TestCase):
    def test_same_symbol_defaults_to_one_group(self) -> None:
        positions = [
            _position("ss-1", "gme", "short_squeeze", _fusion()),
            _position("of-1", "GME", "order_flow", _fusion(net_ev=-20.0)),
        ]
        self.assertEqual(resolve_correlation_group(positions[0]), "SYMBOL:GME")
        self.assertEqual(resolve_correlation_group(positions[1]), "SYMBOL:GME")
        view = build_portfolio_view(positions, as_of_time=AS_OF).to_dict()
        self.assertEqual(len(view["correlation_groups"]), 1)
        summary = view["correlation_groups"][0]
        self.assertTrue(summary["concentration_flagged"])
        self.assertEqual(summary["combined_ev_policy"], "WORST_CASE_MIN")
        # Worst-case conservative combination: min of member EVs, never a sum
        # or an invented correlation coefficient.
        self.assertAlmostEqual(summary["combined_fused_net_ev"], -20.0)
        for row in view["ranked_positions"]:
            self.assertIn(
                PortfolioQualityFlag.CORRELATION_GROUP_CONCENTRATION.value,
                row["quality_flags"],
            )

    def test_explicit_group_key_overrides_symbol_default(self) -> None:
        a = _position("a", "AAPL", "options", _fusion(), correlation_group="macro-rates")
        b = _position("b", "MSFT", "crypto", _fusion(), correlation_group="macro-rates")
        self.assertEqual(resolve_correlation_group(a), "macro-rates")
        groups = {resolve_correlation_group(p) for p in (a, b)}
        self.assertEqual(groups, {"macro-rates"})

    def test_cross_group_items_independent(self) -> None:
        positions = [
            _position("eq", "AAPL", "options", _fusion()),
            _position("fx", "EURUSD", "prediction_market", _fusion()),
        ]
        view = build_portfolio_view(positions, as_of_time=AS_OF).to_dict()
        self.assertEqual(len(view["correlation_groups"]), 2)
        self.assertFalse(any(g["concentration_flagged"] for g in view["correlation_groups"]))
        self.assertTrue(all(row["rank_tier"] == 0 for row in view["ranked_positions"]))


class ContradictionTests(unittest.TestCase):
    def test_opposing_stances_surface_and_demote(self) -> None:
        clean = _position("clean", "SPY", "options", _fusion(net_ev=500.0), uncertainty=0.05)
        bull = _position("ss-1", "GME", "short_squeeze", _fusion(template="bull_call_spread", net_ev=400.0))
        bear = _position("of-1", "GME", "order_flow", _fusion(template="bear_put_spread", net_ev=300.0))
        view = build_portfolio_view([bull, bear, clean], as_of_time=AS_OF).to_dict()

        self.assertEqual(len(view["contradictions"]), 1)
        contradiction = view["contradictions"][0]
        self.assertEqual(contradiction["group_key"], "SYMBOL:GME")
        self.assertEqual(
            sorted(m[0] for m in contradiction["members"]),
            ["of-1", "ss-1"],
        )
        stances = dict(contradiction["members"])
        self.assertEqual(stances["ss-1"], "BULLISH")
        self.assertEqual(stances["of-1"], "BEARISH")

        by_id = {row["position_id"]: row for row in view["ranked_positions"]}
        for pid in ("ss-1", "of-1"):
            self.assertIn(PortfolioQualityFlag.LANE_CONTRADICTION.value, by_id[pid]["quality_flags"])
            self.assertTrue(by_id[pid]["contradicted"])
            self.assertEqual(by_id[pid]["rank_tier"], 2)
        # Demoted, not hidden — contradicted rows still carry full decomposition.
        self.assertAlmostEqual(by_id["ss-1"]["fused_net_ev"], 400.0)
        self.assertEqual(by_id["ss-1"]["template"], "bull_call_spread")

        # Clean position outranks both contradicted ones despite lower EV.
        order = [row["position_id"] for row in view["ranked_positions"]]
        self.assertEqual(order.index("clean"), 0)
        self.assertLess(order.index("clean"), order.index("ss-1"))
        self.assertLess(order.index("clean"), order.index("of-1"))

    def test_contradiction_not_averaged_into_any_score(self) -> None:
        bull = _position("ss-1", "GME", "short_squeeze", _fusion(template="bull_call_spread", net_ev=400.0))
        bear = _position("of-1", "GME", "order_flow", _fusion(template="bear_put_spread", net_ev=300.0))
        snapshot = build_portfolio_view([bull, bear], as_of_time=AS_OF)
        payload = snapshot.to_dict()
        blob = json.dumps(payload)
        self.assertNotIn("universal_score", blob)
        # Both raw EVs survive verbatim; nothing blended them into one number.
        by_id = {row["position_id"]: row for row in payload["ranked_positions"]}
        self.assertAlmostEqual(by_id["ss-1"]["fused_net_ev"], 400.0)
        self.assertAlmostEqual(by_id["of-1"]["fused_net_ev"], 300.0)

    def test_non_directional_stances_never_contradict(self) -> None:
        positions = [
            _position("straddle", "GME", "options", _fusion(template="long_straddle")),
            _position("trend", "GME", "futures", _fusion(template="calendar_spread")),
        ]
        self.assertEqual(detect_contradictions(positions), [])


class RankingAndDeterminismTests(unittest.TestCase):
    def test_documented_lexicographic_policy(self) -> None:
        positions = [
            # Tier 0, worse EV but cleaner book position wins within its tier.
            _position("low-ev", "AAPL", "options", _fusion(net_ev=10.0), uncertainty=0.5),
            _position("high-ev", "MSFT", "crypto", _fusion(net_ev=999.0), uncertainty=0.1),
            _position("tied-a", "TSLA", "options", _fusion(net_ev=50.0), uncertainty=0.3),
            _position("tied-b", "TSLA", "order_flow", _fusion(net_ev=50.0), uncertainty=0.3),
        ]
        view = build_portfolio_view(positions, as_of_time=AS_OF).to_dict()
        order = [row["position_id"] for row in view["ranked_positions"]]
        # Uncertainty ascending dominates EV inside the clean tier...
        self.assertEqual(order[:2], ["high-ev", "low-ev"])
        # ...and position_id is the deterministic final tiebreak.
        self.assertEqual(order[2:], ["tied-a", "tied-b"])

    def test_identical_input_byte_identical_output(self) -> None:
        def make() -> list[PortfolioPosition]:
            return [
                _position("ss-1", "GME", "short_squeeze", _fusion(), ("e1",)),
                _position("of-1", "GME", "order_flow", _fusion(net_ev=42.0), ("e1", "e2")),
            ]

        first = json.dumps(build_portfolio_view(make(), as_of_time=AS_OF).to_dict(), sort_keys=True)
        second = json.dumps(build_portfolio_view(make(), as_of_time=AS_OF).to_dict(), sort_keys=True)
        self.assertEqual(first.encode("utf-8"), second.encode("utf-8"))

    def test_replay_hash_matches_repo_convention(self) -> None:
        positions = [_position("p", "NVDA", "options", _fusion())]
        payload = build_portfolio_view(positions, as_of_time=AS_OF).to_dict()
        self.assertIn("replay_hash", payload)
        canonical = {k: v for k, v in payload.items() if k != "replay_hash"}
        import hashlib

        blob = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
        self.assertEqual(payload["replay_hash"], hashlib.sha256(blob.encode("utf-8")).hexdigest())
        self.assertEqual(payload["version"], PORTFOLIO_VIEW_VERSION)
        self.assertEqual(payload["method"], PORTFOLIO_METHOD)


class DegenerateInputTests(unittest.TestCase):
    def test_empty_book_is_valid(self) -> None:
        view = build_portfolio_view([], as_of_time=AS_OF).to_dict()
        self.assertEqual(view["version"], PORTFOLIO_VIEW_VERSION)
        self.assertEqual(view["ranked_positions"], [])
        self.assertEqual(view["overlap_groups"], [])
        self.assertEqual(view["contradictions"], [])
        self.assertEqual(view["correlation_groups"], [])
        self.assertAlmostEqual(view["net_unique_evidence_fraction"], 1.0)

    def test_missing_uncertainty_flagged_worst_case(self) -> None:
        positions = [_position("u", "NVDA", "options", _fusion())]
        view = build_portfolio_view(positions, as_of_time=AS_OF).to_dict()
        row = view["ranked_positions"][0]
        self.assertEqual(row["uncertainty"], 1.0)
        self.assertIn(PortfolioQualityFlag.POSITION_INPUTS_INCOMPLETE.value, row["quality_flags"])

    def test_unavailable_fusion_rows_rank_last_but_visible(self) -> None:
        healthy = _position("ok", "AAPL", "options", _fusion(net_ev=25.0), uncertainty=0.9)
        dead = _position("dead", "MSFT", "crypto", _fusion(net_ev=None, template=None), uncertainty=0.01)
        view = build_portfolio_view([dead, healthy], as_of_time=AS_OF).to_dict()
        order = [row["position_id"] for row in view["ranked_positions"]]
        self.assertEqual(order, ["ok", "dead"])
        dead_row = view["ranked_positions"][1]
        self.assertEqual(dead_row["status"], "UNAVAILABLE")
        self.assertEqual(dead_row["fused_net_ev"], None)


class AntiOpaqueCompositeInvariantTests(unittest.TestCase):
    def test_per_lane_rows_retained_alongside_aggregates(self) -> None:
        positions = [
            _position("ss-1", "GME", "short_squeeze", _fusion(template="bull_call_spread", net_ev=400.0), ("e1", "e2")),
            _position("of-1", "GME", "order_flow", _fusion(template="bear_put_spread", net_ev=-30.0), ("e2",)),
            _position("opt-1", "AAPL", "options", _fusion(template="long_straddle", net_ev=75.0), ("e3",)),
        ]
        payload = build_portfolio_view(positions, as_of_time=AS_OF).to_dict()
        # One row per input lane position — aggregates never replace rows.
        self.assertEqual(len(payload["ranked_positions"]), len(positions))
        lanes = {row["lane"] for row in payload["ranked_positions"]}
        self.assertEqual(lanes, {"short_squeeze", "order_flow", "options"})
        for row in payload["ranked_positions"]:
            for field in (
                "evidence_ids",
                "template",
                "occurrence_weight",
                "liquidity_factor",
                "gross_ev_before_weights",
                "stance",
                "uncertainty",
                "fused_net_ev",
            ):
                self.assertIn(field, row)
        self.assertTrue(payload["overlap_groups"])
        blob = json.dumps(payload)
        self.assertNotIn("universal_score", blob)
        self.assertNotIn("composite", blob.lower().replace("decomposition", ""))

    def test_quality_flags_propagate_verbatim(self) -> None:
        positions = [
            _position(
                "flagged",
                "NVDA",
                "options",
                _fusion(),
                quality_flags=("OPPORTUNITY_LIQUIDITY_BLOCKED",),
            )
        ]
        payload = build_portfolio_view(positions, as_of_time=AS_OF).to_dict()
        flags = payload["ranked_positions"][0]["quality_flags"]
        self.assertIn("OPPORTUNITY_LIQUIDITY_BLOCKED", flags)
        self.assertIn(PortfolioQualityFlag.POSITION_INPUTS_INCOMPLETE.value, flags)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
