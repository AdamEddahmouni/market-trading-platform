import {
  assertMonotonicBarIdentity,
  type ImpBarProvenance,
  type ImpBarRecord,
} from "./impBarIdentity";

/** Instrument overview bar row with canonical BAR_OHLCV_1M identity (UI API). */
export type WorkspaceCanonicalBar = {
  time: string;
  open: string;
  high: string;
  low: string;
  close: string;
  volume: number;
  epistemic_class: string;
  bar_id?: string;
  source_time_ns?: number;
  available_time_ns?: number;
  provenance?: ImpBarProvenance;
};

function hasCanonicalIdentity(row: WorkspaceCanonicalBar): boolean {
  return (
    typeof row.bar_id === "string" &&
    row.bar_id.length > 0 &&
    typeof row.source_time_ns === "number" &&
    typeof row.available_time_ns === "number" &&
    row.provenance?.event_type === "BAR_OHLCV_1M" &&
    typeof row.provenance.normalized_event_id === "string"
  );
}

/**
 * Map admitted replay instrument overview rows to ImpBarRecord.
 * Returns null when canonical identity is incomplete (shadow chart stays off).
 */
export function mapWorkspaceBarsToImpRecords(
  instrumentId: string,
  rows: WorkspaceCanonicalBar[],
  dataKind: ImpBarRecord["data_kind"] = "REPLAY",
): ImpBarRecord[] | null {
  if (rows.length === 0) return [];
  if (!rows.every(hasCanonicalIdentity)) return null;

  const bars: ImpBarRecord[] = rows.map((row) => {
    const provenance = row.provenance as ImpBarProvenance;
    return {
      bar_id: row.bar_id as string,
      instrument_id: instrumentId,
      timeframe: "1m",
      source_time_ns: row.source_time_ns as number,
      available_time_ns: row.available_time_ns as number,
      ohlcv: {
        open: Number(row.open),
        high: Number(row.high),
        low: Number(row.low),
        close: Number(row.close),
        volume: row.volume,
      },
      data_kind: dataKind,
      provenance: {
        event_type: "BAR_OHLCV_1M",
        normalized_event_id: provenance.normalized_event_id,
        raw_reference: provenance.raw_reference,
        ingest_run_id: provenance.ingest_run_id,
        source_instance_id: provenance.source_instance_id,
      },
    };
  });

  assertMonotonicBarIdentity(bars);
  return bars;
}

/** Fingerprint for skipping redundant Vela `setMarket` when identity unchanged. */
export function impBarSeriesFingerprint(bars: ImpBarRecord[]): string {
  if (bars.length === 0) return "empty";
  const last = bars[bars.length - 1];
  return `${bars.length}:${last.bar_id}:${last.ohlcv.close}:${last.available_time_ns}`;
}
