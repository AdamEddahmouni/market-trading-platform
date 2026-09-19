import type { SemanticTone } from "../../state/semanticState";
import { SEMANTIC_TONE_ICON } from "../../state/semanticState";

type Props = {
  tone: SemanticTone;
  label: string;
  /** Raw backend value, rendered only for L4 contexts (title + data attr). */
  raw?: string;
  /** Accessible name when the visible label is a terse token (IDLE, Live OFF). */
  accessibleName?: string;
  size?: "sm" | "md";
  className?: string;
};

/**
 * The one state badge: tone + icon + text, never color alone.
 * Design guidance: docs/ui-redesign-v2/semantic-state-system.md §1.
 */
export function StatePill({
  tone,
  label,
  raw,
  accessibleName,
  size = "md",
  className,
}: Props) {
  const classes = ["imp-ui-state-pill", `imp-ui-state-pill--${size}`, className]
    .filter(Boolean)
    .join(" ");
  return (
    <span
      className={classes}
      data-tone={tone}
      data-testid="imp-ui-state-pill"
      aria-label={accessibleName}
      title={raw && raw !== label ? raw : undefined}
    >
      <span className="imp-ui-state-pill-icon" aria-hidden="true">
        {SEMANTIC_TONE_ICON[tone]}
      </span>
      <span className="imp-ui-state-pill-label">{label}</span>
    </span>
  );
}
