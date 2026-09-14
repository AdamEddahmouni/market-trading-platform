/**
 * IMP owns bar identity and timestamps. Vela receives a render projection only.
 */

export type ImpTimeframe = "1m" | "5m" | "15m" | "1h";

export type ImpOhlcv = {
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
};

/** Canonical IMP bar record (governed / synthetic for this spike). */
export type ImpBarRecord = {
  bar_id: string;
  instrument_id: string;
  timeframe: ImpTimeframe;
  /** Bar open instant — epoch nanoseconds (IMP source-time semantics). */
  source_time_ns: number;
  ohlcv: ImpOhlcv;
  /** Provenance label for spike honesty (not a security boundary). */
  data_kind: "SYNTHETIC_GOVERNED";
};

export type VelaBar = {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
};

export function impBarOpenMs(bar: ImpBarRecord): number {
  return Math.floor(bar.source_time_ns / 1_000_000);
}

export function toVelaBar(bar: ImpBarRecord): VelaBar {
  return {
    time: impBarOpenMs(bar),
    open: bar.ohlcv.open,
    high: bar.ohlcv.high,
    low: bar.ohlcv.low,
    close: bar.ohlcv.close,
    volume: bar.ohlcv.volume,
  };
}

export function toVelaSeries(bars: ImpBarRecord[]): VelaBar[] {
  return bars.map(toVelaBar);
}

export function assertMonotonicBarIdentity(bars: ImpBarRecord[]): void {
  for (let i = 1; i < bars.length; i++) {
    if (bars[i].source_time_ns <= bars[i - 1].source_time_ns) {
      throw new Error(`IMP bar identity violation: non-monotonic source_time_ns at index ${i}`);
    }
    if (bars[i].bar_id === bars[i - 1].bar_id) {
      throw new Error(`IMP bar identity violation: duplicate bar_id ${bars[i].bar_id}`);
    }
  }
}
