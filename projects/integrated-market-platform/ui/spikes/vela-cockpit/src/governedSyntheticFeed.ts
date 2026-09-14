import {
  assertMonotonicBarIdentity,
  type ImpBarRecord,
  type ImpOhlcv,
  type ImpTimeframe,
  toVelaSeries,
} from "./impBarIdentity";

const MS_PER_BAR: Record<ImpTimeframe, number> = {
  "1m": 60_000,
  "5m": 300_000,
  "15m": 900_000,
  "1h": 3_600_000,
};

function makeBar(
  instrumentId: string,
  timeframe: ImpTimeframe,
  openMs: number,
  seed: number,
): ImpBarRecord {
  const base = 180 + (seed % 17);
  const drift = (seed % 7) * 0.15;
  const open = base + drift;
  const close = open + ((seed % 5) - 2) * 0.35;
  const high = Math.max(open, close) + 0.25 + (seed % 3) * 0.05;
  const low = Math.min(open, close) - 0.25 - (seed % 2) * 0.05;
  const ohlcv: ImpOhlcv = {
    open,
    high,
    low,
    close,
    volume: 8_000 + (seed % 40) * 250,
  };
  return {
    bar_id: `${instrumentId}:${timeframe}:${openMs}`,
    instrument_id: instrumentId,
    timeframe,
    source_time_ns: openMs * 1_000_000,
    ohlcv,
    data_kind: "SYNTHETIC_GOVERNED",
  };
}

export type GovernedFeedState = {
  instrumentId: string;
  timeframe: ImpTimeframe;
  bars: ImpBarRecord[];
  tickCount: number;
};

export function createGovernedFeed(
  instrumentId: string,
  timeframe: ImpTimeframe,
  barCount: number,
): GovernedFeedState {
  const step = MS_PER_BAR[timeframe];
  const endMs = Date.UTC(2026, 8, 14, 20, 0, 0);
  const bars: ImpBarRecord[] = [];
  for (let i = barCount - 1; i >= 0; i--) {
    const openMs = endMs - i * step;
    bars.push(makeBar(instrumentId, timeframe, openMs, barCount - i));
  }
  assertMonotonicBarIdentity(bars);
  return { instrumentId, timeframe, bars, tickCount: 0 };
}

export function velaSeriesFromFeed(state: GovernedFeedState) {
  return toVelaSeries(state.bars);
}

/** Prepends older governed history (simulated left backfill). */
export function backfillOlderBars(state: GovernedFeedState, count: number): GovernedFeedState {
  const step = MS_PER_BAR[state.timeframe];
  const firstOpenMs = Math.floor(state.bars[0].source_time_ns / 1_000_000);
  const older: ImpBarRecord[] = [];
  for (let i = count; i >= 1; i--) {
    const openMs = firstOpenMs - i * step;
    older.push(makeBar(state.instrumentId, state.timeframe, openMs, 1000 + i));
  }
  const bars = [...older, ...state.bars];
  assertMonotonicBarIdentity(bars);
  return { ...state, bars };
}

/** Live tick: update forming bar or roll a new bar closed. */
export function applyIncrementalTick(state: GovernedFeedState, rollEvery: number): GovernedFeedState {
  const step = MS_PER_BAR[state.timeframe];
  const tickCount = state.tickCount + 1;
  const bars = state.bars.map((b) => ({ ...b, ohlcv: { ...b.ohlcv } }));
  const last = bars[bars.length - 1];
  const bump = (tickCount % 3) * 0.08 - 0.08;
  last.ohlcv.close += bump;
  last.ohlcv.high = Math.max(last.ohlcv.high, last.ohlcv.close);
  last.ohlcv.low = Math.min(last.ohlcv.low, last.ohlcv.close);
  last.ohlcv.volume += 120;

  if (tickCount % rollEvery === 0) {
    const lastOpenMs = Math.floor(last.source_time_ns / 1_000_000);
    const nextOpenMs = lastOpenMs + step;
    bars.push(makeBar(state.instrumentId, state.timeframe, nextOpenMs, tickCount));
  }

  assertMonotonicBarIdentity(bars);
  return { ...state, bars, tickCount };
}
