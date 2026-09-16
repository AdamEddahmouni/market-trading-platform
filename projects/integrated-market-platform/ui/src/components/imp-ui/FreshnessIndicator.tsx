import { useEffect, useState } from "react";
import type { SemanticTone } from "../../state/semanticState";
import { SEMANTIC_TONE_ICON } from "../../state/semanticState";

type Props = {
  /** Backend freshness word (e.g. FRESH/STALE/UNKNOWN/NOT_APPLICABLE) — wins when present. */
  backendLabel?: string | null;
  /** ISO timestamp or epoch ms/ns the data was current as of. */
  asOf?: string | number | null;
  /** Expected update cadence in seconds; drives the fresh/lagging/stale bands. */
  cadenceSeconds?: number;
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
  UNAVAILABLE: "critical",
  NOT_APPLICABLE: "neutral",
  SNAPSHOT: "neutral",
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
 * relative "updated …" label banded by cadence. Tone is always paired with
 * text. Raw timestamps belong in TechnicalDetails, not here.
 */
export function FreshnessIndicator({ backendLabel, asOf, cadenceSeconds = 5, className }: Props) {
  const [nowMs, setNowMs] = useState(() => Date.now());

  const asOfMs = parseAsOfMs(asOf);
  const needsTick = !backendLabel && asOfMs != null;

  useEffect(() => {
    if (!needsTick) return;
    const timer = window.setInterval(() => setNowMs(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [needsTick]);

  const classes = ["imp-ui-freshness", className].filter(Boolean).join(" ");

  if (backendLabel) {
    const upper = backendLabel.toUpperCase();
    const tone = BACKEND_WORD_TONE[upper] ?? "neutral";
    const text =
      upper === "FRESH" || upper === "LIVE" || upper === "CURRENT"
        ? "Fresh"
        : upper === "NOT_APPLICABLE"
          ? "Not applicable"
          : backendLabel.replace(/_/g, " ").toLowerCase();
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
