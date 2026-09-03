/** UX Prototype V0 — static mock fixtures. All mock: true where backend absent. */

export const AS_OF = "2026-08-15T10:42:18.328-04:00";
export const AS_OF_DISPLAY = "10:42:18.328 ET";

/** Replay timeline — significant events for scrubber navigation (Flow F). */
export const REPLAY_SESSION = {
  sessionStart: "09:30:00",
  sessionEnd: "16:00:00",
  liveAsOf: AS_OF_DISPLAY,
  events: [
    { time: "09:31:00", label: "Volume abnormal", symbol: "NVDA" },
    { time: "09:37:00", label: "Large buying increases", symbol: "NVDA" },
    { time: "09:41:00", label: "CVD divergence positive", symbol: "NVDA" },
    { time: "10:31:14", label: "Quote gap begins", symbol: "SYSTEM" },
    { time: "10:37:00", label: "Offer liquidity consumed", symbol: "NVDA" },
    { time: "10:42:18", label: "Live cursor (current)", symbol: "NVDA" },
  ],
  defaultReplay: "10:37:00",
};

/** Point-in-time snapshots keyed by HH:MM:SS — knowable-at-time state for replay. */
export const REPLAY_SNAPSHOTS = {
  "10:37:00": {
    asOfDisplay: "10:37:00.000 ET",
    nvdaPrice: 141.52,
    nvdaChangePct: 1.68,
    quality: "GOOD",
    marketStoryCutoff: "10:37",
    attentionTransition: "WATCH → CONFIRMED",
  },
  "10:42:18": {
    asOfDisplay: AS_OF_DISPLAY,
    nvdaPrice: 142.38,
    nvdaChangePct: 2.14,
    quality: "PARTIAL",
    marketStoryCutoff: "10:42",
    attentionTransition: "WATCH → CONFIRMED",
  },
};

export const REGIME = {
  summary: "Risk-on · Tech leading · VIX compressed",
  mock: true,
};

/** System-wide quality detail — Flow J fixture. */
export const SYSTEM_QUALITY = {
  state: "PARTIAL",
  gapType: "quote_gap",
  gapLabel: "Quote stream gap",
  timeRange: { start: "10:31:14.000 ET", end: "10:31:22.000 ET", durationSec: 8 },
  affectedSymbols: ["NVDA", "AAPL", "MSFT"],
  detectedAt: "10:37:05.112 ET",
  summary:
    "Upstream quote gap degrades aggressor-classified features. OBSERVED bar prices remain usable; DERIVED flow metrics should be treated with caution.",
  modules: [
    { name: "Prices (OHLCV)", epistemic: "OBSERVED", quality: "GOOD", note: "1m bars complete for session" },
    { name: "CVD / aggressor flow", epistemic: "DERIVED", quality: "PARTIAL", note: "Gap overlaps inference window" },
    { name: "Relative volume", epistemic: "DERIVED", quality: "GOOD", note: "Bar-derived; unaffected" },
    { name: "Attention ranking", epistemic: "INFERRED", quality: "PARTIAL", note: "Uses degraded CVD inputs" },
    { name: "Institutional", epistemic: "OBSERVED", quality: "UNAVAILABLE", note: "No entitled source" },
  ],
  trustGuidance: [
    { layer: "OBSERVED prices", trust: "GOOD", detail: "Last trade / bar close reliable within fixture" },
    { layer: "DERIVED volume features", trust: "GOOD", detail: "Bar aggregation unaffected by quote gap" },
    { layer: "DERIVED flow (CVD)", trust: "PARTIAL", detail: "May misclassify aggressor during gap window" },
    { layer: "INFERRED attention", trust: "PARTIAL", detail: "Downstream of partial flow features" },
  ],
  symbolDrilldown: {
    NVDA: {
      summary: "Bar prices intact; flow-derived features degraded during gap window.",
      modules: [
        { name: "Price (OHLCV)", epistemic: "OBSERVED", quality: "GOOD", note: "Bars complete" },
        { name: "CVD / aggressor", epistemic: "DERIVED", quality: "PARTIAL", note: "Gap overlaps 10:31–10:31 window" },
        { name: "Attention ranking", epistemic: "INFERRED", quality: "PARTIAL", note: "Uses CVD confirmation" },
      ],
    },
    AAPL: {
      summary: "Same quote gap; bar data unaffected.",
      modules: [
        { name: "Price (OHLCV)", epistemic: "OBSERVED", quality: "GOOD", note: "Bars complete" },
        { name: "CVD / aggressor", epistemic: "DERIVED", quality: "PARTIAL", note: "Gap in quote stream" },
        { name: "Relative volume", epistemic: "DERIVED", quality: "GOOD", note: "Bar-derived only" },
      ],
    },
    MSFT: {
      summary: "Same quote gap; limited watchlist impact.",
      modules: [
        { name: "Price (OHLCV)", epistemic: "OBSERVED", quality: "GOOD", note: "Bars complete" },
        { name: "CVD / aggressor", epistemic: "DERIVED", quality: "PARTIAL", note: "Gap in quote stream" },
      ],
    },
  },
  inspect: {
    type: "System data quality",
    epistemicClass: "DERIVED",
    definition: "Platform-wide quality assessment for quote gap event.",
    asOf: AS_OF_DISPLAY,
    quality: {
      state: "PARTIAL",
      gapType: "quote_gap",
      timeRange: "10:31:14–10:31:22 ET",
      affectedSymbols: ["NVDA", "AAPL", "MSFT"],
      freshness: "STALE during gap; FRESH after recovery",
      corrections: "None applied — gap flagged, not interpolated",
    },
    provenance: ["quality_monitor", "→ gap_detector", "→ quote_stream_adapter", "→ historical_equity_intraday"],
    raw: {
      event_id: "quality-quote-gap-001",
      gap_type: "quote_gap",
      symbols: ["NVDA", "AAPL", "MSFT"],
      start: "2026-08-15T10:31:14.000-04:00",
      end: "2026-08-15T10:31:22.000-04:00",
    },
    usedBy: [
      { name: "Context bar", type: "feature", detail: "Global PARTIAL quality badge", route: "#/now" },
      { name: "Quality detail panel", type: "feature", detail: "Module trust matrix", mock: true },
      { name: "SYSTEM attention card", type: "alert", detail: "Tier-1 pinned quality event", route: "#/now" },
    ],
  },
};

/** CVD derivation fixture — Flow D partial (inspector DERIVATION tab). */
export const CVD_DERIVATION = {
  type: "CVD contribution",
  epistemicClass: "DERIVED",
  definition: "Cumulative volume delta at 10:37:42 from classified trades in observation window.",
  asOf: "10:37:42.118 ET",
  derivation: {
    method: "aggressor_cvd",
    version: "v1.2-mock",
    formula: "CVD += signed_volume(trade) where sign = aggressor_side(trade)",
    inputs: [
      { name: "trade_window", value: "10:36:00–10:37:42", quality: "PARTIAL" },
      { name: "aggressor_classifier", value: "quote_rule_v1", quality: "PARTIAL" },
      { name: "baseline_band", value: "0.72", quality: "GOOD" },
    ],
    inputTrades: [
      { id: "evt-88291", time: "10:37:02.441", price: 141.5, size: 2400, side: "BUY", mock: true },
      { id: "evt-88294", time: "10:37:08.102", price: 141.52, size: 800, side: "BUY", mock: true },
      { id: "evt-88301", time: "10:37:15.887", price: 141.48, size: 1200, side: "SELL", mock: true },
      { id: "evt-88312", time: "10:37:38.221", price: 141.51, size: 3200, side: "BUY", mock: true },
    ],
    qualityNote: "PARTIAL — quote gap 10:31:14–10:31:22 may affect classifier calibration",
  },
  evidence: [
    "4 trades in window contributed +5,200 net delta (MOCK)",
    "Threshold band 0.72 crossed at 10:36:48",
  ],
  timeline: [
    { time: "10:37:02", label: "Trade evt-88291 BUY 2400 @ 141.50", type: "event", mock: true },
    { time: "10:37:08", label: "Trade evt-88294 BUY 800 @ 141.52", type: "event", mock: true },
    { time: "10:37:15", label: "Trade evt-88301 SELL 1200 @ 141.48", type: "event", mock: true },
    { time: "10:37:38", label: "Trade evt-88312 BUY 3200 @ 141.51", type: "event", mock: true },
    { time: "10:37:42", label: "CVD contribution computed", type: "milestone", changed: true, mock: true },
  ],
  provenance: [
    "CVD aggregator (MOCK)",
    "→ aggressor_classifier v1",
    "→ canonical trade events",
    "→ historical_equity_intraday fixture",
  ],
  raw: { feature: "cvd", symbol: "NVDA", value: 5200, mock: true },
  usedBy: [
    { name: "Attention ranking", type: "feature", detail: "CVD confirmation criterion on NVDA card", route: "#/now" },
    { name: "Squeeze monitor", type: "feature", detail: "CONFIRMED transition input", route: "#/instrument/NVDA" },
    { name: "Market Story", type: "feature", detail: "CVD divergence event at 09:41", route: "#/instrument/NVDA" },
  ],
};

/** Squeeze state transition timeline — Flow E fixture. */
export const NVDA_SQUEEZE_TIMELINE = [
  { time: "09:31", label: "Volume abnormal — monitoring elevated", type: "event", mock: true },
  { time: "09:37", label: "Large buying increases", type: "event", mock: true },
  { time: "09:41", label: "CVD divergence positive", type: "event", mock: true },
  { time: "10:31:14", label: "Quote gap begins (system)", type: "quality", changed: false },
  { time: "10:36:48", label: "CVD crossed confirmation band", type: "criterion", changed: true, mock: true },
  { time: "10:37:02", label: "Offer liquidity consumed", type: "criterion", changed: true, mock: true },
  { time: "10:37:10", label: "State transition WATCH → CONFIRMED", type: "milestone", state: "CONFIRMED", changed: true, mock: true },
];

export const ATTENTION_ITEMS = [
  {
    id: "att-nvda-1",
    symbol: "NVDA",
    tier: 2,
    transition: "WATCH → CONFIRMED",
    ago: "2m",
    reasons: [
      "CVD confirmation crossed threshold (MOCK)",
      "Large-buy participation increased (MOCK)",
      "Offer liquidity consumed (MOCK)",
    ],
    reasonCodes: [
      "state_transition:squeeze_watch_to_confirmed",
      "magnitude:rel_volume_3.4x",
      "watchlist:default",
      "position:none",
    ],
    unchanged: "Options flow ambiguous",
    epistemicClass: "INFERRED",
    quality: "PARTIAL",
    mock: true,
    explanation: {
      title: "State transition: WATCH → CONFIRMED",
      meaning:
        "Multiple independent flow signals crossed confirmation thresholds within the observation window.",
      why:
        "Supports continued monitoring escalation — not a trade recommendation.",
      alignment: [
        { label: "Catalysts", state: "↑ LONG", strength: "Moderate", mock: true },
        { label: "Model", state: "—", strength: "No artifact", mock: true },
      ],
      qualityNote: "PARTIAL — Quote gap 10:31:14–10:31:22 may affect aggressor inference.",
    },
    inspect: {
      type: "Attention card",
      epistemicClass: "INFERRED",
      definition: "Ranked attention item based on state transition and magnitude.",
      asOf: AS_OF_DISPLAY,
      derivation: {
        method: "attention_ranker",
        version: "v0.3-mock",
        formula: "rank = tier(state_transition) × magnitude(rel_volume) × watchlist_weight",
        inputs: [
          { name: "state_transition", value: "WATCH→CONFIRMED", quality: "PARTIAL" },
          { name: "rel_volume", value: "3.4×", quality: "GOOD" },
          { name: "cvd_confirmation", value: "crossed", quality: "PARTIAL" },
        ],
        qualityNote: "PARTIAL — CVD input degraded by quote gap",
      },
      quality: {
        state: "PARTIAL",
        reason: "Downstream of partial CVD / aggressor features",
        affectedInputs: ["cvd_confirmation", "large_buy_detector"],
        observedLayer: "GOOD — price bars unaffected",
      },
      timeline: NVDA_SQUEEZE_TIMELINE,
      provenance: [
        "Attention ranking (MOCK)",
        "→ state_transition:squeeze_watch_to_confirmed",
        "→ magnitude:rel_volume 3.4x (MOCK)",
        "→ watchlist:default",
      ],
      raw: { attention_id: "att-nvda-1", mock: true, reasons: ["state_transition", "magnitude"] },
      usedBy: [
        { name: "NOW attention feed", type: "feature", detail: "Tier-2 ranked card — NVDA", route: "#/now" },
        { name: "Squeeze monitor", type: "feature", detail: "WATCH → CONFIRMED state machine", route: "#/instrument/NVDA" },
        { name: "Default watchlist", type: "watchlist", detail: "NVDA pulse row", mock: true },
        { name: "Unusual volume screener", type: "screener", detail: "Match row (3.4× rel vol)", route: "#/explore" },
      ],
    },
    transitionDetail: {
      title: "Transition detail: WATCH → CONFIRMED",
      fromState: "WATCH",
      toState: "CONFIRMED",
      changed: [
        { criterion: "CVD confirmation", from: "below threshold", to: "crossed threshold", mock: true },
        { criterion: "Large-buy participation", from: "normal", to: "elevated", mock: true },
        { criterion: "Offer liquidity", from: "present", to: "consumed", mock: true },
      ],
      unchanged: [
        "Options flow ambiguous",
        "Institutional evidence unavailable",
        "Model artifact absent",
      ],
      asOf: AS_OF_DISPLAY,
      inspect: {
        type: "State transition",
        epistemicClass: "INFERRED",
        definition: "Squeeze monitor state change with criterion-level diff.",
        asOf: AS_OF_DISPLAY,
        evidence: [
          "CVD crossed 0.72 confirmation band at 10:36:48 (MOCK)",
          "Large-buy count +34% vs 20m baseline (MOCK)",
          "Offer liquidity at 141.50 consumed at 10:37:02 (MOCK)",
        ],
        timeline: NVDA_SQUEEZE_TIMELINE,
        derivation: {
          method: "squeeze_monitor",
          version: "v0-mock",
          formula: "CONFIRMED = cvd_cross ∧ large_buy_elevated ∧ liquidity_consumed",
          inputs: [
            { name: "cvd_confirmation", value: "crossed 0.72", quality: "PARTIAL" },
            { name: "large_buy_participation", value: "+34%", quality: "PARTIAL" },
            { name: "offer_liquidity", value: "consumed", quality: "PARTIAL" },
          ],
        },
        provenance: [
          "squeeze_monitor v0 (MOCK)",
          "→ CVD feature",
          "→ large_trade_detector (MOCK)",
        ],
        raw: { transition: "WATCH→CONFIRMED", mock: true },
      },
    },
  },
  {
    id: "att-system-1",
    symbol: "SYSTEM",
    tier: 1,
    transition: "QUALITY DEGRADED",
    ago: "5m",
    reasons: ["Quote gap affects CVD on 3 watchlist symbols"],
    reasonCodes: [
      "quality:quote_gap",
      "scope:watchlist_3_symbols",
      "tier:1_system",
    ],
    unchanged: null,
    epistemicClass: "DERIVED",
    quality: "PARTIAL",
    mock: false,
    explanation: {
      title: "Data quality: PARTIAL",
      meaning: "Some derived metrics may be unreliable due to upstream gaps.",
      why: "Prevents silent use of degraded flow metrics.",
      alignment: [],
      qualityNote: "Gap window 10:31:14–10:31:22 ET on NVDA, AAPL, MSFT.",
    },
    inspect: {
      type: "System quality event",
      epistemicClass: "DERIVED",
      definition: "Platform-wide data health notification.",
      asOf: AS_OF_DISPLAY,
      quality: SYSTEM_QUALITY.inspect.quality,
      derivation: {
        method: "gap_detector",
        version: "v1.0",
        formula: "gap = max(timestamp_delta) > threshold in quote stream",
        inputs: [
          { name: "quote_stream", value: "historical_equity_intraday", quality: "PARTIAL" },
          { name: "threshold_ms", value: "500", quality: "GOOD" },
        ],
      },
      provenance: [
        "Quality monitor",
        "→ gap detector",
        "→ quote stream (fixture)",
      ],
      raw: { event: "quote_gap", symbols: ["NVDA", "AAPL", "MSFT"], mock: false },
      usedBy: [
        { name: "Context bar quality badge", type: "feature", detail: "PARTIAL indicator when system degraded", route: "#/now" },
        { name: "CVD / aggressor features", type: "feature", detail: "Downstream PARTIAL quality propagation", mock: true },
        { name: "Attention ranking", type: "feature", detail: "NVDA card quality badge", route: "#/now" },
      ],
    },
  },
  {
    id: "att-aapl-1",
    symbol: "AAPL",
    tier: 2,
    transition: "NEW WATCH",
    ago: "8m",
    reasons: ["Relative volume 2.1x session baseline (MOCK)"],
    reasonCodes: ["magnitude:rel_volume_2.1x", "watchlist:default"],
    unchanged: "Institutional evidence unavailable",
    epistemicClass: "DERIVED",
    quality: "GOOD",
    mock: true,
    explanation: {
      title: "New watch: elevated relative volume",
      meaning: "Bar-derived volume exceeded baseline threshold.",
      why: "Warrants monitoring; no flow confirmation yet.",
      alignment: [],
      qualityNote: "GOOD — bar data complete for session.",
    },
    inspect: {
      type: "Attention card",
      epistemicClass: "DERIVED",
      definition: "Volume anomaly detection on admitted OHLCV fixture.",
      asOf: AS_OF_DISPLAY,
      derivation: {
        method: "rel_volume_detector",
        version: "v1-mock",
        formula: "rel_volume = bar_volume / session_baseline_volume",
        inputs: [
          { name: "bar_volume", value: "2.1× baseline", quality: "GOOD" },
          { name: "session_baseline", value: "20d median", quality: "GOOD" },
        ],
      },
      provenance: ["rel_volume feature", "→ 1m bars", "→ historical_equity_intraday fixture"],
      raw: { symbol: "AAPL", rel_volume: 2.1, mock: true },
    },
  },
];

export const WATCHLIST_PULSE = [
  { symbol: "NVDA", change: 2.14, mock: true },
  { symbol: "AAPL", change: -0.42, mock: true },
  { symbol: "MSFT", change: 0.08, mock: true },
  { symbol: "ES", change: 0.0, mock: true },
];

export const INSTRUMENTS = {
  NVDA: {
    symbol: "NVDA",
    price: 142.38,
    changePct: 2.14,
    quality: "PARTIAL",
    epistemicClass: "OBSERVED",
    mock: true,
    alignment: [
      {
        module: "Order Flow",
        state: "unavailable",
        detail: "⊘ UNAVAILABLE",
        inspect: null,
      },
      {
        module: "Options",
        state: "unavailable",
        detail: "⊘ UNAVAILABLE",
        inspect: null,
      },
      {
        module: "Institutional",
        state: "unavailable",
        detail: "⊘ UNAVAILABLE",
        inspect: null,
      },
      {
        module: "Catalysts",
        state: "long",
        detail: "↑ LONG Moderate",
        mock: true,
        inspect: {
          type: "Catalyst alignment",
          epistemicClass: "INFERRED",
          definition: "Upcoming catalyst density supports bullish monitoring bias.",
          asOf: AS_OF_DISPLAY,
          derivation: {
            method: "catalyst_scorer",
            version: "v0.1-mock",
            formula: "score = w1×event_density + w2×revision_sentiment − w3×negative_filings",
            inputs: [
              { name: "event_calendar", value: "earnings T-12", quality: "GOOD" },
              { name: "analyst_revisions", value: "positive cluster", quality: "GOOD" },
            ],
          },
          evidence: [
            "Earnings in 12 sessions (MOCK)",
            "Analyst revision cluster positive (MOCK)",
            "No negative filing in 48h window",
          ],
          provenance: ["catalyst_scorer v0 (MOCK)", "→ event calendar", "→ filing feed (delayed)"],
          timeline: [
            { time: "08:00", label: "Earnings date confirmed T-12", type: "event", mock: true },
            { time: "10:15", label: "Analyst revision cluster positive", type: "event", mock: true },
            { time: "10:42", label: "Catalyst score → LONG Moderate", type: "milestone", state: "LONG", mock: true },
          ],
          raw: { module: "catalysts", direction: "LONG", strength: "moderate", mock: true },
          usedBy: [
            { name: "Evidence alignment panel", type: "feature", detail: "Catalysts row — ↑ LONG Moderate", route: "#/instrument/NVDA" },
            { name: "Conflict detector", type: "feature", detail: "Opposes Model SHORT signal", route: "#/instrument/NVDA" },
            { name: "Explanation drawer", type: "feature", detail: "Alignment summary on NVDA alert", route: "#/now" },
          ],
        },
      },
      {
        module: "Model",
        state: "short",
        detail: "↓ SHORT Weak",
        mock: true,
        inspect: {
          type: "Model alignment",
          epistemicClass: "MODEL",
          definition: "Short-bias model output from admitted bar features only.",
          asOf: AS_OF_DISPLAY,
          derivation: {
            method: "bar_model_v0",
            version: "0.2-mock",
            formula: "signal = mean_reversion(rsi_proxy_5m) + overbought_penalty",
            inputs: [
              { name: "rsi_proxy_5m", value: "72.4", quality: "GOOD" },
              { name: "options_skew", value: "UNAVAILABLE", quality: "UNAVAILABLE" },
            ],
            qualityNote: "Degraded — missing options skew input",
          },
          evidence: [
            "Mean-reversion signal elevated at 10:41 (MOCK)",
            "Overbought RSI proxy on 5m bars (MOCK)",
            "No options skew input — model degraded",
          ],
          provenance: ["bar_model_v0 (MOCK)", "→ 1m OHLCV fixture", "→ feature cutoff 10:41"],
          timeline: [
            { time: "10:35", label: "RSI proxy crossed 70", type: "event", mock: true },
            { time: "10:41", label: "Mean-reversion signal elevated", type: "criterion", changed: true, mock: true },
            { time: "10:42", label: "Model output → SHORT Weak", type: "milestone", state: "SHORT", mock: true },
          ],
          raw: { module: "model", direction: "SHORT", strength: "weak", mock: true },
          usedBy: [
            { name: "Evidence alignment panel", type: "feature", detail: "Model row — ↓ SHORT Weak", route: "#/instrument/NVDA" },
            { name: "Conflict detector", type: "feature", detail: "Opposes Catalysts LONG signal", route: "#/instrument/NVDA" },
          ],
        },
      },
    ],
    conflict: {
      domains: ["Catalysts", "Model"],
      summary: "Catalysts ↑ LONG vs Model ↓ SHORT — domains disagree",
      inspect: {
        type: "Evidence conflict",
        epistemicClass: "INFERRED",
        definition: "Multiple evidence domains produce opposing directional signals.",
        asOf: AS_OF_DISPLAY,
        derivation: {
          method: "alignment_aggregator",
          version: "v0.1-mock",
          formula: "conflict = count(distinct(direction)) > 1 among available domains",
          inputs: [
            { name: "catalysts", value: "LONG moderate", quality: "GOOD" },
            { name: "model", value: "SHORT weak", quality: "PARTIAL" },
            { name: "order_flow", value: "UNAVAILABLE", quality: "UNAVAILABLE" },
          ],
        },
        timeline: [
          { time: "10:41", label: "Model output SHORT (bar features)", type: "event", mock: true },
          { time: "10:42", label: "Conflict detected — Catalysts vs Model", type: "milestone", changed: true, mock: true },
        ],
        evidence: [
          "Catalysts: ↑ LONG Moderate — event density + revision cluster (MOCK)",
          "Model: ↓ SHORT Weak — mean-reversion on bar features (MOCK)",
          "Order Flow: UNAVAILABLE — cannot arbitrate",
          "Institutional: UNAVAILABLE — cannot arbitrate",
        ],
        provenance: [
          "alignment_aggregator (MOCK)",
          "→ catalyst_scorer",
          "→ bar_model_v0",
        ],
        raw: {
          conflict_id: "nvda-align-1",
          domains: [
            { name: "Catalysts", direction: "LONG", epistemic: "INFERRED", strength: "moderate" },
            { name: "Model", direction: "SHORT", epistemic: "MODEL", strength: "weak" },
          ],
          mock: true,
        },
        usedBy: [
          { name: "Conflict callout", type: "feature", detail: "Catalysts vs Model banner", route: "#/instrument/NVDA" },
          { name: "Evidence alignment panel", type: "feature", detail: "Highlights opposing domain rows", route: "#/instrument/NVDA" },
        ],
      },
    },
    sparkline: [138.2, 139.1, 138.8, 140.2, 141.0, 140.5, 141.8, 142.1, 141.9, 142.38],
    marketStory: [
      { time: "09:31", text: "Volume abnormal", mock: true },
      { time: "09:37", text: "Large buying increases (MOCK)", mock: true },
      { time: "09:41", text: "CVD divergence positive (MOCK)", mock: true },
      { time: "10:37", text: "Offer liquidity consumed (MOCK)", mock: true },
    ],
    modules: {
      overview: true,
      price: true,
      orderFlow: false,
      options: false,
      institutional: false,
    },
    unavailableReasons: {
      orderFlow:
        "Aggressor classification requires verified trade feed. Current admitted dataset is bar-only OHLCV.",
      options: "Options data not admitted in Phase 5 boundary.",
      institutional:
        "No entitled disclosure source. Institutional interfaces fail-closed per ADR-WHALE-001.",
    },
  },
  AAPL: {
    symbol: "AAPL",
    price: 227.14,
    changePct: -0.42,
    quality: "PARTIAL",
    epistemicClass: "OBSERVED",
    mock: true,
    alignment: [
      { module: "Order Flow", state: "unavailable", detail: "⊘ UNAVAILABLE" },
      { module: "Options", state: "unavailable", detail: "⊘ UNAVAILABLE" },
      { module: "Institutional", state: "unavailable", detail: "⊘ UNAVAILABLE" },
      { module: "Catalysts", state: "neutral", detail: "— Neutral", mock: true },
      { module: "Model", state: "none", detail: "— (no artifact)" },
    ],
    sparkline: [228.1, 227.8, 227.5, 227.9, 227.2, 227.0, 227.3, 227.1, 227.2, 227.14],
    marketStory: [{ time: "10:15", text: "Relative volume elevated", mock: true }],
    modules: {
      overview: true,
      price: true,
      orderFlow: false,
      options: false,
      institutional: false,
    },
    unavailableReasons: {
      orderFlow: "Aggressor classification requires verified trade feed.",
      options: "Options data not admitted.",
      institutional: "No entitled disclosure source.",
    },
  },
};

/** EXPLORE domain stub — screener placeholder (V0.5). */
export const EXPLORE_DATA = {
  defaultScreen: "unusual-volume",
  savedScreens: [
    { id: "unusual-volume", label: "Unusual volume" },
    { id: "squeeze-watch", label: "Squeeze watch" },
    { id: "large-insider", label: "Large insider" },
  ],
  watchlists: [
    { id: "default", label: "Default" },
    { id: "active-setups", label: "Active setups" },
    { id: "portfolio", label: "Portfolio" },
  ],
  screens: {
    "unusual-volume": {
      title: "Unusual volume",
      results: [
        {
          symbol: "NVDA",
          relVol: "3.4x",
          summary: "✓ vol ✓ flow",
          mock: true,
          matched: [
            { criterion: "Relative volume > 3x", met: true },
            { criterion: "Large buying abnormal", met: true },
            { criterion: "Squeeze criteria not met", met: false },
          ],
          inspect: {
            type: "Screener match",
            epistemicClass: "DERIVED",
            definition: "Volume anomaly with optional flow confirmation on admitted fixture.",
            asOf: AS_OF_DISPLAY,
            derivation: {
              method: "screener_unusual_volume",
              version: "v0.1-mock",
              formula: "match = rel_volume > 3.0 ∧ (large_buy_elevated ∨ flow_unavailable)",
              inputs: [
                { name: "rel_volume", value: "3.4×", quality: "GOOD" },
                { name: "large_buy", value: "elevated", quality: "PARTIAL" },
              ],
            },
            evidence: [
              "Relative volume 3.4× session baseline (MOCK)",
              "Large-buy participation elevated (MOCK)",
              "Squeeze state still WATCH — not a squeeze match",
            ],
            usedBy: [
              { name: "EXPLORE results table", type: "screener", detail: "Row match for unusual volume", route: "#/explore" },
              { name: "Default watchlist", type: "watchlist", detail: "Candidate for monitoring", mock: true },
            ],
            provenance: ["screener_unusual_volume (MOCK)", "→ rel_volume feature", "→ 1m bars fixture"],
            raw: { screen: "unusual-volume", symbol: "NVDA", rel_vol: 3.4, mock: true },
          },
        },
        {
          symbol: "AMD",
          relVol: "2.8x",
          summary: "✓ vol × squeeze",
          mock: true,
          matched: [
            { criterion: "Relative volume > 2.5x", met: true },
            { criterion: "Squeeze criteria", met: false },
          ],
          inspect: {
            type: "Screener match",
            epistemicClass: "DERIVED",
            definition: "Volume elevated but squeeze criteria not met.",
            asOf: AS_OF_DISPLAY,
            evidence: ["Relative volume 2.8× (MOCK)", "Squeeze monitor: no state transition"],
            usedBy: [{ name: "EXPLORE results table", type: "screener", detail: "Row match", route: "#/explore" }],
            provenance: ["screener_unusual_volume (MOCK)", "→ rel_volume feature"],
            raw: { screen: "unusual-volume", symbol: "AMD", rel_vol: 2.8, mock: true },
          },
        },
      ],
    },
    "squeeze-watch": {
      title: "Squeeze watch",
      results: [
        {
          symbol: "NVDA",
          relVol: "3.4x",
          summary: "✓ squeeze CONFIRMED",
          mock: true,
          matched: [
            { criterion: "Squeeze state ≥ CONFIRMED", met: true },
            { criterion: "CVD confirmation", met: true },
          ],
          inspect: {
            type: "Screener match",
            epistemicClass: "INFERRED",
            definition: "Squeeze monitor state at or above CONFIRMED.",
            asOf: AS_OF_DISPLAY,
            evidence: ["State WATCH → CONFIRMED (MOCK)", "CVD crossed threshold (MOCK)"],
            usedBy: [
              { name: "EXPLORE squeeze watch", type: "screener", detail: "CONFIRMED match", route: "#/explore" },
              { name: "NOW attention feed", type: "feature", detail: "Same signal as attention card", route: "#/now" },
            ],
            provenance: ["squeeze_monitor (MOCK)", "→ CVD feature"],
            raw: { screen: "squeeze-watch", symbol: "NVDA", state: "CONFIRMED", mock: true },
          },
        },
      ],
    },
    "large-insider": {
      title: "Large insider",
      results: [],
      unavailable: "Institutional / insider data not entitled. Fail-closed per ADR-WHALE-001.",
    },
  },
};

export const COMMAND_ITEMS = [
  { label: "Go to NOW", action: "nav", target: "#/now" },
  { label: "Go to EXPLORE", action: "nav", target: "#/explore" },
  { label: "Open NVDA cockpit", action: "nav", target: "#/instrument/NVDA" },
  { label: "Open AAPL cockpit", action: "nav", target: "#/instrument/AAPL" },
  { label: "Explain attention (NVDA)", action: "explain", target: "att-nvda-1" },
  { label: "Mobile alert: NVDA (Flow K)", action: "alert", target: "att-nvda-1" },
  { label: "Open NVDA replay 10:37", action: "replay", target: "10:37:00" },
  { label: "Return to LIVE", action: "live", target: "" },
  { label: "Data quality detail", action: "quality", target: "" },
  { label: "Squeeze timeline (NVDA)", action: "timeline", target: "att-nvda-1" },
  { label: "Unusual volume screener", action: "explore", target: "unusual-volume" },
];

export const INSPECTOR_TABS = [
  "SUMMARY",
  "EVIDENCE",
  "DERIVATION",
  "TIMELINE",
  "QUALITY",
  "PROVENANCE",
  "USED BY",
  "RAW",
];
