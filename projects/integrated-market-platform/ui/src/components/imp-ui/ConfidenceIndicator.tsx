import type { SemanticTone } from "../../state/semanticState";
import { SEMANTIC_TONE_ICON } from "../../state/semanticState";

type Props = {
  /** Backend confidence in [0, 1]. Missing confidence renders nothing. */
  value?: number | null;
  className?: string;
};

export type ConfidenceBand = "low" | "medium" | "high";

export function confidenceBand(value: number): ConfidenceBand {
  if (value < 0.33) return "low";
  if (value < 0.66) return "medium";
  return "high";
}

const BAND_LABEL: Record<ConfidenceBand, string> = {
  low: "Low confidence",
  medium: "Medium confidence",
  high: "High confidence",
};

const BAND_TONE: Record<ConfidenceBand, SemanticTone> = {
  low: "caution",
  medium: "neutral",
  high: "live",
};

/**
 * Bands, not false precision: Low / Medium / High with the numeric value in
 * the tooltip. The UI never computes confidence from scratch — pass backend
 * confidence fields only.
 */
export function ConfidenceIndicator({ value, className }: Props) {
  if (value == null || !Number.isFinite(value)) return null;
  const clamped = Math.min(1, Math.max(0, value));
  const band = confidenceBand(clamped);
  const tone = BAND_TONE[band];
  const classes = ["imp-ui-confidence", className].filter(Boolean).join(" ");
  return (
    <span
      className={classes}
      data-tone={tone}
      data-band={band}
      data-testid="imp-ui-confidence"
      title={`Confidence ${(clamped * 100).toFixed(0)}%`}
    >
      <span aria-hidden="true">{SEMANTIC_TONE_ICON[tone]}</span> {BAND_LABEL[band]}
    </span>
  );
}
