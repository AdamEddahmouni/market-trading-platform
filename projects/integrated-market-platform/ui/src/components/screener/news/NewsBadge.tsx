import type { NewsActivityRow } from "../../../api/screenerNews";

type Tone = "positive" | "negative" | "neutral" | "mixed" | "unscored";
const GLYPHS: Record<Tone, string> = { positive: "▲", negative: "▼", neutral: "●", mixed: "◆", unscored: "" };

/** Headline tone across scored stories: one clear majority, a split, or nothing scored. */
export function badgeTone(row: NewsActivityRow): Tone {
  const { positive, negative, neutral } = row.tone;
  const scored = positive + negative + neutral;
  if (!scored) return "unscored";
  if (positive > negative && positive >= neutral) return "positive";
  if (negative > positive && negative >= neutral) return "negative";
  // Equal positive and negative that outweigh neutral: a split, not a lean either way.
  if (positive === negative && positive > neutral) return "mixed";
  return "neutral";
}

export function badgeSummary(row: NewsActivityRow) {
  const parts = (["positive", "neutral", "negative"] as const).filter((tone) => row.tone[tone]).map((tone) => `${row.tone[tone]} ${tone}`);
  if (row.unscored) parts.push(`${row.unscored} unscored`);
  return `${row.count} ${row.count === 1 ? "story" : "stories"} in 24h${parts.length ? ` · ${parts.join(", ")}` : ""}`;
}

/**
 * Grid-row news activity: "N stories in 24h · tone". Headline tone is a model label on the
 * headline text, not a price signal. Nothing is shown for a row with no stories.
 */
export function NewsBadge({ row, pending, symbol, onOpen }: { row: NewsActivityRow | undefined; pending: boolean; symbol: string; onOpen: () => void }) {
  if (!row) return pending ? <span className="screener-news-badge pending" aria-hidden="true">·</span> : null;
  const tone = badgeTone(row);
  const summary = badgeSummary(row);
  return <button type="button" className={`screener-news-badge tone-${tone}`} title={`${summary}. Headline tone, not a price signal. Open News & Analysis.`}
    aria-label={`${symbol}: ${summary}. Open News and Analysis`}
    onClick={(event) => { event.stopPropagation(); onOpen(); }} onDoubleClick={(event) => event.stopPropagation()}>
    {row.count > 99 ? "99+" : row.count}{GLYPHS[tone] ? <span aria-hidden="true">{GLYPHS[tone]}</span> : null}
  </button>;
}
