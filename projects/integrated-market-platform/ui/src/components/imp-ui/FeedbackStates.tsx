import type { ReactNode } from "react";
import { Link } from "react-router-dom";

type EmptyStateProps = {
  title: string;
  /** Why this is empty — mandatory: an empty screen is an invitation to act. */
  reason: string;
  action?: { label: string; href: string };
  children?: ReactNode;
  className?: string;
};

/**
 * The one empty-state idiom. `reason` is required: every empty state explains
 * why it is empty and, when one exists, what unblocks it.
 */
export function EmptyState({ title, reason, action, children, className }: EmptyStateProps) {
  const classes = ["imp-ui-empty-state", className].filter(Boolean).join(" ");
  return (
    <section className={classes} aria-label={title} data-testid="imp-ui-empty-state">
      <h2 className="imp-ui-empty-state-title">{title}</h2>
      <p className="imp-ui-empty-state-reason">{reason}</p>
      {children}
      {action ? (
        <p className="imp-ui-empty-state-action">
          <Link to={action.href}>{action.label}</Link>
        </p>
      ) : null}
    </section>
  );
}

type ErrorStateProps = {
  /** Humanized failure sentence (what happened). */
  title?: string;
  /** What it affects. */
  affects?: string;
  /** Raw `category: reason_code` detail for the technical disclosure. */
  rawDetail?: string;
  onRetry?: () => void;
  className?: string;
};

/**
 * The one error idiom: humanized sentence + affects + retry/action; raw
 * envelope detail stays in the technical disclosure.
 */
export function ErrorState({
  title = "This surface is unavailable right now.",
  affects,
  rawDetail,
  onRetry,
  className,
}: ErrorStateProps) {
  const classes = ["imp-ui-error-state", className].filter(Boolean).join(" ");
  return (
    <div className={classes} role="alert" data-testid="imp-ui-error-state">
      <p className="imp-ui-error-state-title">{title}</p>
      {affects ? <p className="imp-ui-error-state-affects">{affects}</p> : null}
      {onRetry ? (
        <button type="button" className="imp-ui-error-state-retry" onClick={onRetry}>
          Retry
        </button>
      ) : null}
      {rawDetail ? (
        <details className="imp-ui-error-state-detail">
          <summary>Technical details</summary>
          <code>{rawDetail}</code>
        </details>
      ) : null}
    </div>
  );
}
