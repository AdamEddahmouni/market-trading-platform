import { useState } from "react";
import type { ScreenerUniverse } from "../../../api/screener";
import type { NewsMatch, NewsStory, ProviderStatus, StorySentiment } from "../../../api/screenerNews";
import { RemedyHint } from "../setup/Remedy";
import { LOCAL_SUFFIX, LOCAL_ZONE } from "../localZone";

const zoneOf = (universe: ScreenerUniverse) => universe === "CRYPTO" ? LOCAL_ZONE : "America/New_York";
const suffixOf = (universe: ScreenerUniverse) => universe === "CRYPTO" ? LOCAL_SUFFIX : "ET";
const formatters = new Map<string, Intl.DateTimeFormat>();
function formatter(zone: string, withDay: boolean) {
  const key = `${zone}|${withDay}`;
  let item = formatters.get(key);
  if (!item) {
    item = new Intl.DateTimeFormat("en-US", { timeZone: zone, hour: "2-digit", minute: "2-digit", hour12: false,
      ...(withDay ? { weekday: "short" as const } : {}) });
    formatters.set(key, item);
  }
  return item;
}
/** HH:MM on the universe clock (Crypto on the machine's own clock, US markets ET). */
export const newsClock = (iso: string | null | undefined, universe: ScreenerUniverse) =>
  iso ? `${formatter(zoneOf(universe), false).format(new Date(iso))} ${suffixOf(universe)}` : "—";
/** Weekday + HH:MM: a 72h window spans days. */
export const newsDayTime = (iso: string | null | undefined, universe: ScreenerUniverse) =>
  iso ? `${formatter(zoneOf(universe), true).format(new Date(iso))} ${suffixOf(universe)}` : "—";

export const humanize = (code: string | null | undefined) => code ? code.replace(/_/g, " ").toLowerCase() : "";

export const PROVIDER_STATE_TEXT: Record<string, string> = {
  CURRENT: "current", STALE: "stale", DELAYED: "delayed", PENDING: "pending", NOT_CONFIGURED: "not configured",
  LIVE_DISABLED: "live disabled", RATE_LIMITED: "rate limited", AUTH_FAILED: "auth failed", ERROR: "error",
  NOT_APPLICABLE: "not applicable", UNAVAILABLE: "unavailable", LOADED: "loaded",
};
export const stateText = (state: string) => PROVIDER_STATE_TEXT[state] ?? humanize(state);

const TERM_TEXT: Record<string, string> = {
  DEVELOPER: "Developer plan", FREE: "free plan", DEVELOPMENT_ONLY: "development and testing only",
  DELAYED_24H: "articles delayed 24 h", LOCAL_MODEL: "local model",
};
/** Plain-language plan terms (cost, quota, timing, use restriction) stated by the server for a provider. */
export function termsText(provider: ProviderStatus): string | null {
  const t = provider.terms;
  if (!t) return null;
  const parts = [t.plan, t.runtime, t.restriction, t.timing].filter((item): item is string => Boolean(item))
    .map((item) => TERM_TEXT[item] ?? humanize(item));
  if (t.quota) parts.push(t.quota);
  if (t.cost_usd === 0) parts.push("$0");
  return parts.length ? parts.join(" · ") : null;
}

/** Providers that are expected to contribute but are not current. */
export const degradedProviders = (providers: ProviderStatus[]) =>
  providers.filter((item) => item.state !== "CURRENT" && item.state !== "NOT_APPLICABLE");

/** True while the local sentiment model is loading for any loaded page, so the view can re-poll until it is scored. */
export const isModelLoading = (pages: ReadonlyArray<{ sentiment_model?: { reason: string | null }; stories: NewsStory[] }>) =>
  pages.some((page) => page.sentiment_model?.reason === "MODEL_LOADING" || page.stories.some((story) => story.sentiment.reason === "MODEL_LOADING"));

/** One fix per distinct cause among degraded providers (two providers blocked by one flag show one step). */
export function ProviderFixes({ providers, skip }: { providers: ProviderStatus[]; skip?: string | null }) {
  const seen = new Set<string>(skip ? [skip] : []);
  const fixes = providers.flatMap((provider) => {
    const remedy = provider.remedy;
    if (!remedy || seen.has(remedy.reason)) return [];
    seen.add(remedy.reason);
    return [{ provider, remedy }];
  });
  if (!fixes.length) return null;
  // Spans with list roles: this renders inside panel messages, which are paragraphs.
  return <span className="news-fixes" role="list" aria-label="How to fix">{fixes.map(({ provider, remedy }) =>
    <span role="listitem" key={remedy.reason}><span className="news-fix-provider">{provider.label}:</span> <RemedyHint remedy={remedy} compact /></span>)}</span>;
}

export function StoryTime({ story, universe }: { story: NewsStory; universe: ScreenerUniverse }) {
  if (!story.published_at) {
    return <span className="news-time unknown" title={`Publication time unknown; first retrieved ${story.first_retrieved_at}`}>
      time unknown · retrieved {newsClock(story.first_retrieved_at, universe)}</span>;
  }
  const inferred = story.published_time_quality === "INFERRED_LOW_CONFIDENCE";
  return <time className="news-time" dateTime={story.published_at}
    title={`${inferred ? "Publication time inferred (low confidence)" : "Published"} ${story.published_at}${story.latest_published_at && story.latest_published_at !== story.published_at ? ` · latest member ${story.latest_published_at}` : ""}`}>
    {newsDayTime(story.published_at, universe)}{inferred ? " (inferred)" : ""}</time>;
}

const SENTIMENT_TEXT: Record<string, string> = { POSITIVE: "Positive", NEUTRAL: "Neutral", NEGATIVE: "Negative", MIXED: "Mixed" };
export const sentimentWord = (label: string | null | undefined) => label ? SENTIMENT_TEXT[label] ?? humanize(label) : "—";

/** Language tone of one story. Text always carries the state; colour is only a secondary cue. */
export function SentimentCell({ sentiment }: { sentiment: StorySentiment }) {
  if (sentiment.state === "SCORED" && sentiment.label) {
    const p = sentiment.probabilities;
    return <span className={`news-sentiment ${sentiment.label.toLowerCase()}`}
      title={`Headline language classified by ${sentiment.model_id ?? "unknown model"}${sentiment.basis === "IMP_DERIVED_FINBERT" ? " (local model, derived by IMP; not supplied by the source)" : ""}${p ? ` · positive ${p.positive.toFixed(2)} · neutral ${p.neutral.toFixed(2)} · negative ${p.negative.toFixed(2)}` : ""}. Describes language, not a forecast.`}>
      {SENTIMENT_TEXT[sentiment.label]}</span>;
  }
  if (sentiment.state === "NOT_CONFIGURED" || sentiment.state === "UNAVAILABLE") {
    // Dense rows: the status strip names the model state once; each row keeps it for assistive tech and on hover.
    const text = sentiment.state === "NOT_CONFIGURED" ? "model not configured" : "unavailable";
    return <span className="news-sentiment none" title={`Sentiment ${text}`}><span aria-hidden="true">—</span><span className="sr-only">{text}</span></span>;
  }
  const text = sentiment.state === "NOT_SCORED" ? (sentiment.reason === "MODEL_LOADING" ? "model loading" : "not scored")
    : sentiment.state === "ERROR" ? "scoring error" : "—";
  return <span className="news-sentiment none" title={`Sentiment ${humanize(sentiment.state)}`}>{text}</span>;
}

const CONFIDENCE_TAG: Record<string, string> = { CONTEXT: "ctx", AMBIGUOUS: "ambig" };
export function MatchChip({ match, onFilter }: { match: NewsMatch; onFilter?: (match: NewsMatch) => void }) {
  const tag = CONFIDENCE_TAG[match.confidence];
  const title = `${humanize(match.basis)} · ${match.confidence.toLowerCase()} match${match.term ? ` · term "${match.term}"` : ""}`;
  const body = <>{match.symbol}{tag ? <small className="news-chip-tag"> {tag}</small> : null}</>;
  const className = `news-chip ${match.confidence.toLowerCase()}`;
  if (!onFilter || !match.instrument_id) return <span className={className} title={title}>{body}</span>;
  return <button type="button" className={className} title={title} aria-label={`Filter news by ${match.symbol} (${title})`}
    onClick={() => onFilter(match)}>{body}</button>;
}

export function TypeBadge({ type }: { type: NewsStory["source_type"] }) {
  if (type === "NEWS") return null;
  return <span className={`news-type ${type.toLowerCase()}`}>{type === "OFFICIAL_FILING" ? "Official filing" : "Official release"}</span>;
}

export function Headline({ story }: { story: NewsStory }) {
  const title = story.summary ? `${story.headline}\n\n${story.summary}` : story.headline;
  return story.url
    ? <a className="news-headline" href={story.url} target="_blank" rel="noopener noreferrer" title={title}>{story.headline}</a>
    : <span className="news-headline" title={title}>{story.headline}</span>;
}

/**
 * Publisher, plus the syndicated member list when one story came from several sources.
 * Uncontrolled by default; the News feed controls `open` so Enter on a row can toggle it.
 */
export function StorySources({ story, universe, open: controlledOpen, onToggle }:
  { story: NewsStory; universe: ScreenerUniverse; open?: boolean; onToggle?: () => void }) {
  const [localOpen, setLocalOpen] = useState(false);
  const open = controlledOpen ?? localOpen;
  const toggle = onToggle ?? (() => setLocalOpen(!localOpen));
  const primary = story.sources[0];
  return <div className="news-sources">
    <span className="news-publisher" title={primary ? `${primary.publisher} via ${primary.provider_label}` : undefined}>{primary?.publisher ?? "—"}</span>
    {story.source_count > 1 && <button type="button" className="news-cluster" aria-expanded={open} onClick={toggle}>
      1 story · {story.source_count} sources</button>}
    {open && <ul className="news-source-list" aria-label={`Sources for ${story.headline}`}>{story.sources.map((source, index) =>
      <li key={`${source.provider_id}-${source.publisher}-${index}`}>
        <span>{source.publisher}</span><small>{source.provider_label}</small>
        <small>{source.published_at ? newsDayTime(source.published_at, universe) : `time unknown · retrieved ${newsClock(source.retrieved_at, universe)}`}</small>
        {source.url ? <a href={source.url} target="_blank" rel="noopener noreferrer">open</a> : <small>no link</small>}
      </li>)}</ul>}
  </div>;
}

export function ProviderStrip({ providers, label = "News providers" }: { providers: ProviderStatus[]; label?: string }) {
  return <ul className="news-provider-strip" aria-label={label}>{providers.map((provider) =>
    <li key={provider.id} className={`news-provider state-${provider.state.toLowerCase()}`}
      title={[provider.reason ? `Reason: ${provider.reason}` : null, provider.fetched_at ? `Fetched ${provider.fetched_at}` : "Not fetched",
        provider.item_count != null ? `${provider.item_count} items` : null, termsText(provider)].filter(Boolean).join(" · ")}>
      <span>{provider.label}</span> <strong>{stateText(provider.state)}</strong></li>)}</ul>;
}
