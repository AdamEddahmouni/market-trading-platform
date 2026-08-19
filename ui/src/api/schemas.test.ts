import { describe, expect, it } from "vitest";
import {
  OpportunitySnapshotSchema,
  WorkspaceFuturesResponseSchema,
  WorkspaceOptionsResponseSchema,
  WorkspaceOrderBookResponseSchema,
} from "./schemas";

describe("WorkspaceOptionsResponseSchema", () => {
  it("parses cooperative NVDA payload without stripping research snapshots", () => {
    const payload = {
      symbol: "NVDA",
      available: false,
      reason: "WHALE_NO_PIT_ELIGIBLE_OPTIONS",
      research_only: true,
      disclaimer: "No PIT-eligible options events for this symbol at replay cutoff.",
      strategy_snapshot: {
        available: true,
        status: "RANKED",
        outcome: "RANKED",
        symbol: "NVDA",
        as_of_time: "2026-07-21T19:45:00.000000000Z",
        best_candidate: {
          template: "long_call_atm",
          edge_alignment: "bullish_directional",
          net_expected_pnl: 309.6536,
          payoff: {
            available: true,
            expected_pnl: 326.3,
            net_expected_pnl: 309.6536,
            friction_cost: 16.6464,
            win_probability: 0.4,
          },
        },
        ranked_candidates: [
          {
            template: "long_call_atm",
            edge_alignment: "bullish_directional",
            net_expected_pnl: 309.6536,
          },
        ],
        model_version: "options_strategy_v1",
        replay_hash: "abc123",
      },
      execution_snapshot: {
        available: true,
        status: "SIMULATED",
        outcome: "FILLED",
        symbol: "NVDA",
        entry_fills: [
          {
            leg_index: 0,
            call_put: "call",
            strike: 130,
            side: "long",
            fill_price: 1.85,
            liquidity_ok: true,
          },
        ],
        lifecycle_events: [],
        realized_pnl: 42.5,
        ledger_summary: { open_positions: 0, entry_count: 1 },
        strategy_template: "long_call_atm",
        execution_replay_hash: "def456",
      },
      opportunity_snapshot: {
        available: true,
        status: "RANKED",
        outcome: "RANKED",
        symbol: "NVDA",
        fused_net_ev: 309.648336,
        fusion: {
          fused_net_ev: 309.648336,
          occurrence_weight: 0.999983,
          liquidity_factor: 1.0,
          gross_ev_before_weights: 309.6536,
          template: "long_call_atm",
          squeeze_aligned: true,
        },
        probability: {
          available: true,
          squeeze_state: "ACTIVE_SQUEEZE",
          source_ref: "cross_lane:probability",
        },
        payoff: {
          available: true,
          expected_pnl: 326.3,
          source_ref: "options:strategy",
        },
        costs: { available: true, friction_cost: 16.6464, source_ref: "options:payoff" },
        liquidity: { available: true, gates_passed: true, source_ref: "cross_lane:liquidity" },
        replay_hash: "345a3dec7a82c6345f52523f265b57c4e935d4ed41a0b7f46fb349decde89d7e",
      },
      dealer_snapshot: {
        available: true,
        estimated_dealer_gamma: -0.62,
        gamma_regime: "negative_gamma",
        confidence: "LOW",
      },
    };

    const parsed = WorkspaceOptionsResponseSchema.parse(payload);
    expect(parsed.strategy_snapshot?.best_candidate?.template).toBe("long_call_atm");
    expect(parsed.execution_snapshot?.entry_fills?.length).toBe(1);
    expect(parsed.opportunity_snapshot?.fused_net_ev).toBe(309.648336);
    expect(parsed.dealer_snapshot?.estimated_dealer_gamma).toBe(-0.62);
  });

  it("parses golden opportunity fixture fields", () => {
    const snapshot = OpportunitySnapshotSchema.parse({
      available: true,
      status: "RANKED",
      outcome: "RANKED",
      fused_net_ev: 309.648336,
      fusion: {
        occurrence_weight: 0.999983,
        liquidity_factor: 1.0,
        gross_ev_before_weights: 309.6536,
        template: "long_call_atm",
        squeeze_aligned: true,
      },
      probability: {
        available: true,
        squeeze_occurrence_probability: 0.658361,
        squeeze_hazard_probability: 0.999983,
      },
      payoff: {
        available: true,
        expected_pnl: 326.3,
        net_expected_pnl: 309.6536,
      },
      costs: { available: true, friction_cost: 16.6464 },
      liquidity: { available: true, gates_passed: true },
      model_version: "shared_opportunity_v1",
      method: "CROSS_LANE_FUSION_V1",
      replay_hash: "345a3dec7a82c6345f52523f265b57c4e935d4ed41a0b7f46fb349decde89d7e",
    });

    expect(snapshot.outcome).toBe("RANKED");
    expect(snapshot.fusion?.squeeze_aligned).toBe(true);
    expect(snapshot.replay_hash).toBe(
      "345a3dec7a82c6345f52523f265b57c4e935d4ed41a0b7f46fb349decde89d7e",
    );
  });
});

describe("WorkspaceOrderBookResponseSchema", () => {
  it("parses OF4 OFI metadata without stripping fields", () => {
    const parsed = WorkspaceOrderBookResponseSchema.parse({
      symbol: "NVDA",
      available: true,
      research_only: true,
      latest_ofi_value: 2130.0,
      latest_ofi_method: "ofi_multilevel_cs_v1",
      latest_ofi_version: "1",
      latest_book_state_valid: true,
      snapshots: [
        {
          event_time: "2026-07-21T20:30:06.000000000Z",
          best_bid: 170.61,
          best_ask: 170.63,
          ofi_value: 2130.0,
          ofi_method: "ofi_multilevel_cs_v1",
          ofi_version: "1",
          book_state_valid: true,
        },
      ],
    });

    expect(parsed.latest_ofi_method).toBe("ofi_multilevel_cs_v1");
    expect(parsed.snapshots?.[0]?.ofi_method).toBe("ofi_multilevel_cs_v1");
    expect(parsed.latest_book_state_valid).toBe(true);
  });

  it("parses OF6 liquidity summary without stripping fields", () => {
    const parsed = WorkspaceOrderBookResponseSchema.parse({
      symbol: "NVDA",
      available: true,
      research_only: true,
      latest_liquidity_summary: {
        liquidity_method: "liquidity_depth_delta_v1",
        liquidity_version: "1",
        depth_withdrawal: 240.0,
        fragility_score: 0.096,
        resiliency_score: 0.755102,
      },
      snapshots: [
        {
          event_time: "2026-07-21T20:30:01.000000000Z",
          depth_withdrawal: 240.0,
          fragility_score: 0.096,
          liquidity_method: "liquidity_depth_delta_v1",
        },
      ],
    });

    expect(parsed.latest_liquidity_summary?.liquidity_method).toBe("liquidity_depth_delta_v1");
    expect(parsed.latest_liquidity_summary?.depth_withdrawal).toBe(240.0);
    expect(parsed.snapshots?.[0]?.fragility_score).toBe(0.096);
  });

  it("parses OF7 impact summary without stripping fields", () => {
    const parsed = WorkspaceOrderBookResponseSchema.parse({
      symbol: "NVDA",
      available: true,
      research_only: true,
      latest_impact_summary: {
        impact_method: "impact_aggression_price_v1",
        impact_version: "1",
        impact_regime: "BUY_ABSORPTION",
        absorption_score: 0.696875,
        mid_delta: 0.01,
        aggression_signed_volume: 150,
        opposing_replenishment: true,
      },
    });

    expect(parsed.latest_impact_summary?.impact_regime).toBe("BUY_ABSORPTION");
    expect(parsed.latest_impact_summary?.absorption_score).toBe(0.696875);
  });

  it("parses OF8 microstructure forecast summary without stripping fields", () => {
    const parsed = WorkspaceOrderBookResponseSchema.parse({
      symbol: "NVDA",
      available: true,
      research_only: true,
      latest_microstructure_forecast: {
        forecast_method: "microstructure_heuristic_v1",
        forecast_version: "1",
        forecast_horizon_seconds: 1,
        direction_bias: "UP",
        continuation_probability: 0.580594,
        reversal_probability: 0.15,
        expected_mid_delta: 0.005,
        composite_bias: 0.580594,
        model_confidence: 0.72,
        forecast_quality_flags: ["INSUFFICIENT_HISTORY"],
      },
    });

    expect(parsed.latest_microstructure_forecast?.direction_bias).toBe("UP");
    expect(parsed.latest_microstructure_forecast?.continuation_probability).toBe(0.580594);
    expect(parsed.latest_microstructure_forecast?.forecast_method).toBe(
      "microstructure_heuristic_v1",
    );
  });

  it("parses OF9 execution forecast summary without stripping fields", () => {
    const parsed = WorkspaceOrderBookResponseSchema.parse({
      symbol: "NVDA",
      available: true,
      research_only: true,
      latest_execution_forecast: {
        execution_method: "execution_book_aware_v1",
        execution_version: "1",
        book_model_version: "displayed_depth_l2_v1",
        queue_model_version: "none",
        aggressive_fill_probability: 0.4,
        passive_fill_probability: 0.72,
        expected_slippage_spread_fraction: 0.002,
        adverse_selection_risk: 0.35,
      },
    });

    expect(parsed.latest_execution_forecast?.execution_method).toBe("execution_book_aware_v1");
    expect(parsed.latest_execution_forecast?.aggressive_fill_probability).toBe(0.4);
  });
});

describe("WorkspaceFuturesResponseSchema", () => {
  it("parses F4 positioning and F3 curve/carry without stripping fields", () => {
    const parsed = WorkspaceFuturesResponseSchema.parse({
      symbol: "ES",
      available: true,
      research_only: true,
      futures_curve_available: true,
      futures_carry_available: true,
      futures_positioning_available: true,
      crowding_regime: "CROWDED_LONG",
      curve_snapshot: {
        available: true,
        regime: "contango",
        instrument_family: "ES",
      },
      carry_observation: {
        available: true,
        annualized_carry: 0.0125,
        formula_tag: "calendar_implied_carry_equity_index_v1",
      },
      positioning_snapshot: {
        available: true,
        net: 75000,
        net_percentile: 1.0,
        participant_category: "managed_money",
        publication_time: "2025-05-30T17:30:00Z",
        crowding_regime: "CROWDED_LONG",
        positioning_version: "futures_positioning_v1",
      },
      oi_velocity_hypothesis: {
        label: "OI_RISING_WITH_PRICE",
        front_oi_delta: 5000,
        front_price_delta: 3.25,
        disclaimer: "OI change ≠ directional forecast; every contract has a long and short",
      },
    });

    expect(parsed.futures_positioning_available).toBe(true);
    expect(parsed.positioning_snapshot?.net).toBe(75000);
    expect(parsed.curve_snapshot?.regime).toBe("contango");
    expect(parsed.carry_observation?.annualized_carry).toBe(0.0125);
    expect(parsed.oi_velocity_hypothesis?.label).toBe("OI_RISING_WITH_PRICE");
  });

  it("parses F5 baselines without stripping fields", () => {
    const parsed = WorkspaceFuturesResponseSchema.parse({
      symbol: "ES",
      available: true,
      futures_baselines_available: true,
      trend_regime: "TREND_UP",
      trend_baseline_snapshot: {
        trend_1m: 1.325,
        trend_3m: 3.305202,
        trend_6m: 8.228549,
        trend_12m: 17.179459,
        vol_estimate: 0.00511,
        baselines_version: "futures_baselines_v1",
      },
      carry_baseline: {
        carry_percentile: 0.0,
        carry_change: -0.03886851,
        formula_tag: "CALENDAR_SPREAD_IMPLIED",
      },
      curve_momentum: {
        calendar_spread_momentum: "FLATTENING",
        regime: "contango",
      },
    });

    expect(parsed.futures_baselines_available).toBe(true);
    expect(parsed.trend_regime).toBe("TREND_UP");
    expect(parsed.trend_baseline_snapshot?.trend_3m).toBe(3.305202);
    expect(parsed.carry_baseline?.carry_percentile).toBe(0.0);
    expect(parsed.curve_momentum?.calendar_spread_momentum).toBe("FLATTENING");
  });
});
