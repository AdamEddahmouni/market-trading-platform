import type { ScreenerUniverse } from "../../../api/screener";
import type { NewsStory } from "../../../api/screenerNews";

/**
 * Per-viewer News read state, kept in this browser only. "New" means published after the
 * viewer's last visit to the universe's News; the retrieval time is never used because it
 * falls back to the poll time for items without one. Storage may be unavailable (private
 * windows, blocked site data): every access fails soft to "nothing seen".
 */
const PREFIX = "imp.screener.news";
const MAX_READ = 500;

function get(key: string): string | null {
  try { return window.localStorage.getItem(key); } catch { return null; }
}
function set(key: string, value: string) {
  try { window.localStorage.setItem(key, value); } catch { /* storage unavailable */ }
}

export function readLastSeen(universe: ScreenerUniverse): string | null {
  const value = get(`${PREFIX}.lastSeen.${universe}`);
  return value && !Number.isNaN(Date.parse(value)) ? value : null;
}

/** Moves the last-view mark forward only; an older generated_at never rewinds it. */
export function writeLastSeen(universe: ScreenerUniverse, iso: string) {
  const current = readLastSeen(universe);
  if (!current || Date.parse(iso) > Date.parse(current)) set(`${PREFIX}.lastSeen.${universe}`, iso);
}

export function readOpened(universe: ScreenerUniverse): Set<string> {
  try {
    const parsed: unknown = JSON.parse(get(`${PREFIX}.read.${universe}`) ?? "[]");
    return new Set(Array.isArray(parsed) ? parsed.filter((item): item is string => typeof item === "string") : []);
  } catch { return new Set(); }
}

export function writeOpened(universe: ScreenerUniverse, ids: Set<string>) {
  set(`${PREFIX}.read.${universe}`, JSON.stringify([...ids].slice(-MAX_READ)));
}

/** First publication time, as the server's `new_count` uses; unknown publication times are never new. */
export const isNewSince = (story: NewsStory, baseline: string | null) =>
  Boolean(baseline && story.published_at && Date.parse(story.published_at) > Date.parse(baseline));
