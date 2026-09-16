import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import type { SemanticTone } from "../../state/semanticState";
import { SEMANTIC_TONE_ICON } from "../../state/semanticState";

type Props = {
  tone: SemanticTone;
  /** 3-question rule, Q1: what happened (one human sentence). */
  children: ReactNode;
  /** 3-question rule, Q2: what it affects. */
  affects?: ReactNode;
  /** 3-question rule, Q3: what to do — link or explicit action node. */
  action?: { label: string; href: string };
  className?: string;
};

/**
 * Severity-graded banner with the 3-question content contract:
 * what happened / what it affects / what to do.
 * `role="alert"` only for critical; other tones use `role="status"`.
 */
export function AttentionBanner({ tone, children, affects, action, className }: Props) {
  const classes = ["imp-ui-attention-banner", className].filter(Boolean).join(" ");
  return (
    <div
      className={classes}
      data-tone={tone}
      data-testid="imp-ui-attention-banner"
      role={tone === "critical" ? "alert" : "status"}
    >
      <span className="imp-ui-attention-banner-icon" aria-hidden="true">
        {SEMANTIC_TONE_ICON[tone]}
      </span>
      <div className="imp-ui-attention-banner-body">
        <p className="imp-ui-attention-banner-what">{children}</p>
        {affects ? <p className="imp-ui-attention-banner-affects">{affects}</p> : null}
      </div>
      {action ? (
        <Link className="imp-ui-attention-banner-action" to={action.href}>
          {action.label}
        </Link>
      ) : null}
    </div>
  );
}
