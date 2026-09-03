# Market Trading Platform — project analysis index

This folder contains seven independent donor/reference projects plus the
canonical platform; it is not one integrated application. These notes capture
the code, data, tools, equations, operational
requirements, and stated limitations found in the supplied projects. They are
descriptive, not investment advice or a claim of predictive performance.

| Project | Primary purpose | Main notes |
|---|---|---|
| `Eric_futuresX-main/futuresX-main` | IBKR/Topstep futures Level-2 UI, data capture, backtests, and paper-trading experiments | [FUTURESX_NOTES.md](FUTURESX_NOTES.md) |
| `internship-project-main/internship-project-main` | Paper news-momentum and options-confirmation agent | [INTERNSHIP_AGENT_NOTES.md](INTERNSHIP_AGENT_NOTES.md) |
| `L1VolumeBubble-main (1)/L1VolumeBubble-main` | TradingView Pine volume-bubble indicator | [L1_VOLUME_BUBBLE_NOTES.md](L1_VOLUME_BUBBLE_NOTES.md) |
| `short-squeeze-project/short-squeeze-core` | Read-only, evidence/provenance-driven short-squeeze research screener | [SHORT_SQUEEZE_NOTES.md](SHORT_SQUEEZE_NOTES.md) |
| `tradingCVDBubble-main (1)/tradingCVDBubble-main` | IBKR/FinViz/MongoDB cumulative-volume-delta and Level-2 dashboard | [CVD_BUBBLE_NOTES.md](CVD_BUBBLE_NOTES.md) |
| `DS-340W-Fantasy-Football-Prediction-main/DS-340W-Fantasy-Football-Prediction-main` | R-based fantasy-football ARIMA/ARIMAX/neural-network research donor | [DS340W_NOTES.md](DS340W_NOTES.md) |
| `DS-440-CAPSTONE-GridIQ-main/DS-440-CAPSTONE-GridIQ-main` | FastAPI/React football analytics and chat reference donor | [GRID_IQ_NOTES.md](GRID_IQ_NOTES.md) |

The governed canonical repository is `integrated-market-platform/`; it is not a
donor and remains the only integration target.

Cross-project fixture map: [docs/DONOR_FIXTURE_MAP.md](docs/DONOR_FIXTURE_MAP.md)

Donor demo launcher: `tools/run_donor_demos.ps1`

## Professor-directed integration brief

The current project direction, supplied screenshot, complete meeting transcript,
low/no-cost broker/data alternatives, and whale/copy-trading research lane are
documented in [PROFESSOR_BRIEF_AND_ROADMAP.md](PROFESSOR_BRIEF_AND_ROADMAP.md)
and [PROFESSOR_MEETING_TRANSCRIPT_20260813.md](PROFESSOR_MEETING_TRANSCRIPT_20260813.md).

## Cross-project map

```text
Market data / broker APIs
  IBKR ─────────────► FuturesX (orders, depth) ───► GUI/backtests
    └───────────────► CVD Bubble (ticks/quotes/L2) ─► MongoDB/Dash
  FinViz ───────────► Internship discovery / CVD consolidated bars
  Options providers ─► Options engine ────────────► paper decision agent
  Provider evidence ─► Short Squeeze screener ────► read-only research UI
  TradingView ───────► L1 volume-bubble indicator
```

## Shared themes and integration cautions

- The projects use incompatible data stores and interfaces: SQLite/CSV in
  FuturesX, JSON state in the internship agent, MongoDB in CVD Bubble, and
  provider artifacts in the short-squeeze screener.
- Several projects can submit paper/live-style broker orders. Do not merge or
  run their execution entry points without an explicit, shared risk layer.
- CVD Bubble is a measurement system; the short-squeeze screener explicitly
  avoids recommendations; the internship agent documents unprofitable paper
  results. None establishes a validated trading edge.
- Credentials belong in private environment/config files. The referenced APIs
  include IBKR, Topstep, Alpaca, Unusual Whales, Claude/Gemini, FinViz, Finnhub,
  NewsAPI, and SEC EDGAR.

## Inspection boundary

Reviewed project source, configuration, documentation, test/research scripts,
and supplied data manifests. Excluded installed dependency trees, Python bytecode,
generated build/release copies, caches, and credential-like generated state: they
duplicate third-party or source material rather than defining the projects.
