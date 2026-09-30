import { useState } from "react";
import type { ScreenerUniverse } from "../../../api/screener";
import type { SentimentTimelineBucket } from "../../../api/screenerNews";
import { newsDayTime } from "./newsFormat";

const TONES = ["positive", "neutral", "negative", "unscored"] as const;
type Tone = (typeof TONES)[number];
type Bar = Record<Tone, number> & { start: string };
const SPANS = [{ id: "24h", hours: 24, bin: 1 }, { id: "72h", hours: 72, bin: 3 }] as const;
const BAR_W = 5, GAP = 1, HEIGHT = 22;

function bin(timeline: SentimentTimelineBucket[], hours: number, size: number): Bar[] {
  const slice = timeline.slice(-hours);
  const bars: Bar[] = [];
  for (let index = 0; index < slice.length; index += size) {
    const group = slice.slice(index, index + size);
    const bar: Bar = { start: group[0].start, positive: 0, neutral: 0, negative: 0, unscored: 0 };
    for (const bucket of group) for (const tone of TONES) bar[tone] += bucket[tone];
    bars.push(bar);
  }
  return bars;
}

const total = (bar: Record<Tone, number>) => TONES.reduce((sum, tone) => sum + bar[tone], 0);

/**
 * Stories by headline tone over time for one instrument (DERIVED, local FinBERT). The text
 * totals carry the meaning; bar colour is a secondary cue, and a table backs it for assistive tech.
 */
export function SentimentSparkline({ timeline, untimed = 0, universe, symbol }:
  { timeline: SentimentTimelineBucket[]; untimed?: number; universe: ScreenerUniverse; symbol: string }) {
  const [spanId, setSpanId] = useState<(typeof SPANS)[number]["id"]>("72h");
  const span = SPANS.find((item) => item.id === spanId) ?? SPANS[1];
  const bars = bin(timeline, span.hours, span.bin);
  const sums = bars.reduce((acc, bar) => { for (const tone of TONES) acc[tone] += bar[tone]; return acc; },
    { positive: 0, neutral: 0, negative: 0, unscored: 0 } as Record<Tone, number>);
  const peak = Math.max(1, ...bars.map(total));
  const summary = `${sums.positive} positive · ${sums.neutral} neutral · ${sums.negative} negative · ${sums.unscored} unscored`;
  const width = bars.length * (BAR_W + GAP);
  return <div className="news-spark" role="group" aria-label={`${symbol} stories by headline tone, last ${span.id}`}>
    <div className="news-spark-head">
      <span className="news-spark-title">Tone over time</span>
      <span className="news-spark-spans">{SPANS.map((item) => <button key={item.id} type="button" aria-pressed={item.id === span.id}
        onClick={() => setSpanId(item.id)}>{item.id}</button>)}</span>
    </div>
    <svg className="news-spark-svg" width={width} height={HEIGHT} viewBox={`0 0 ${width} ${HEIGHT}`} aria-hidden="true">
      {bars.map((bar, index) => {
        let y = HEIGHT;
        return <g key={bar.start}><title>{`${newsDayTime(bar.start, universe)} · ${TONES.map((tone) => `${bar[tone]} ${tone}`).join(" · ")}`}</title>
          <rect className="news-spark-slot" x={index * (BAR_W + GAP)} y={0} width={BAR_W} height={HEIGHT} />
          {TONES.map((tone) => {
            if (!bar[tone]) return null;
            const h = Math.max(1, (bar[tone] / peak) * HEIGHT);
            y -= h;
            return <rect key={tone} className={`news-spark-${tone}`} x={index * (BAR_W + GAP)} y={y} width={BAR_W} height={h} />;
          })}</g>;
      })}
    </svg>
    <p className="news-meta">{summary}{untimed ? ` · ${untimed} without a publication time not shown` : ""} · stories by headline language, not a forecast</p>
    <table className="sr-only"><caption>{symbol} stories by headline tone per {span.bin === 1 ? "hour" : `${span.bin} hours`}</caption>
      <thead><tr><th scope="col">From</th>{TONES.map((tone) => <th key={tone} scope="col">{tone}</th>)}</tr></thead>
      <tbody>{bars.filter((bar) => total(bar) > 0).map((bar) => <tr key={bar.start}><th scope="row">{newsDayTime(bar.start, universe)}</th>
        {TONES.map((tone) => <td key={tone}>{bar[tone]}</td>)}</tr>)}</tbody></table>
  </div>;
}
