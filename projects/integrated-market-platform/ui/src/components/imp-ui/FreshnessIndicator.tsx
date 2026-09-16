import { useEffect, useState } from "react";
import type { SemanticTone } from "../../state/semanticState";
import { SEMANTIC_TONE_ICON, humanizeEnum } from "../../state/semanticState";

type Props = {
  /** Backend freshness word (e.g. FRESH/STALE/UNKNOWN/NOT_APPLICABLE) — wins when present. */
  backendLabel?: string | null;
  /** ISO timestamp or epoch ms/ns the data was current as of. */
  asOf?: string | number | null;
  /** Expected update cadence in seconds; drives the fresh/lagging/stale bands. */
  cadenceSeconds?: number;
  /**
   * false for replay/frozen data: it does not decay (semantic-state-system
   * §6), so render "as of {human time}" with the replay tone instead of a
   * wall-clock age band.
   */
  decays?: boolean;
  className?: string;
};

const BAND_TONE: Record<"fresh" | "lagging" | "stale", SemanticTone> = {
  fresh: "live",
  lagging: "caution",
  stale: "caution",
};

const BACKEND_WORD_TONE: Record<string, SemanticTone> = {
  FRESH: "live",
  LIVE: "live",
  CURRENT: "live",
  STALE: "caution",
  DELAYED: "caution",
  UNKNOWN: "neutral",
  UNAVAILABLE: "neutral",
  NOT_APPLICABLE: "neutral",
  SNAPSHOT: "neutral",
  REPLAY: "replay",
};

/** Operator-readable labels for known backend freshness words (never raw enums). */
const BACKEND_WORD_LABEL: Record<string, string> = {
  FRESH: "Fresh",
  LIVE: "Fresh",
  CURRENT: "Fresh",
  STALE: "Stale",
  DELAYED: "Delayed",
  UNKNOWN: "Unknown",
  UNAVAILABLE: "Unavailable",
  NOT_APPLICABLE: "Not applicable",
  SNAPSHOT: "Snapshot",
  REPLAY: "Replay",
};

export function parseAsOfMs(asOf: string | number | null | undefined): number | null {
  if (asOf == null || asOf === "") return null;
  if (typeof asOf === "number") {
    if (!Number.isFinite(asOf) || asOf <= 0) return null;
    // Epoch nanoseconds are ~1e18; milliseconds ~1e12.
    return asOf > 1e15 ? asOf / 1_000_000 : asOf;
  }
  const parsed = Date.parse(asOf);
  return Number.isNaN(parsed) ? null : parsed;
}

export function formatRelativeAge(ms: number, nowMs: number): string {
  const deltaSeconds = Math.max(0, Math.round((nowMs - ms) / 1000));
  if (deltaSeconds < 5) return "just now";
  if (deltaSeconds < 60) return `${deltaSeconds}s ago`;
  const minutes = Math.floor(deltaSeconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

/** Absolute human time for non-decaying (replay/frozen) surfaces. */
export function formatAbsoluteTime(ms: number): string {
  try {
    return new Intl.DateTimeFormat(undefined, {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    }).format(new Date(ms));
  } catch {
    return new Date(ms).toISOString();
  }
}

export function freshnessBand(
  ageMs: number,
  cadenceSeconds: number,
): "fresh" | "lagging" | "stale" {
  const cadenceMs = Math.max(1, cadenceSeconds) * 1000;
  if (ageMs <= cadenceMs * 2.5) return "fresh";
  if (ageMs <= cadenceMs * 10) return "lagging";
  return "stale";
}

/**
 * One freshness presentation: backend word wins when present; otherwise a
 * relative "updated …" label banded by cadence (decaying data) or an
 * absolute "as of …" label (replay/frozen data, `decays={false}`). Tone is
 * always paired with text. Raw timestamps belong in TechnicalDetails.
 */
export function FreshnessIndicator({ backendLabel, asOf, cadenceSeconds = 5, decays = true, className }: Props) {
  const [nowMs, setNowMs] = useState(() => Date.now());

  const asOfMs = parseAsOfMs(asOf);
  const needsTick = decays && !backendLabel && asOfMs != null;

  useEffect(() => {
    if (!needsTick) return;
    const timer = window.setInterval(() => setNowMs(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [needsTick]);

  const classes = ["imp-ui-freshness", className].filter(Boolean).join(" ");

  if (backendLabel) {
    const upper = backendLabel.toUpperCase();
    const tone = BACKEND_WORD_TONE[upper] ?? "neutral";
    const text = BACKEND_WORD_LABEL[upper] ?? humanizeEnum(backendLabel);
    return (
      <span className={classes} data-tone={tone} data-testid="imp-ui-freshness">
        <span aria-hidden="true">{SEMANTIC_TONE_ICON[tone]}</span> {text}
      </span>
    );
  }

  if (asOfMs == null) {
    return (
      <span className={classes} data-tone="neutral" data-testid="imp-ui-freshness">
        <span aria-hidden="true">{SEMANTIC_TONE_ICON.neutral}</span> Freshness unknown
      </span>
    );
  }

  if (!decays) {
    return (
      <span className={classes} data-tone="replay" data-testid="imp-ui-freshness">
        <span aria-hidden="true">{SEMANTIC_TONE_ICON.replay}</span> as of{" "}
        {formatAbsoluteTime(asOfMs)}
      </span>
    );
  }

  const ageMs = Math.max(0, nowMs - asOfMs);
  const band = freshnessBand(ageMs, cadenceSeconds);
  const tone = BAND_TONE[band];
  return (
    <span className={classes} data-tone={tone} data-testid="imp-ui-freshness">
      <span aria-hidden="true">{SEMANTIC_TONE_ICON[tone]}</span> updated{" "}
      {formatRelativeAge(asOfMs, nowMs)}
      {band === "stale" ? " — may be delayed" : ""}
    </span>
  );
}
