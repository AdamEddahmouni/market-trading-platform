import type { ReactNode } from "react";

type Props = {
  title: string;
  description?: string;
  action?: ReactNode;
  className?: string;
};

export function EmptyState({ title, description, action, className }: Props) {
  return (
    <section className={className ? `empty-state ${className}` : "empty-state"} aria-label={title}>
      <h2 className="empty-state-title">{title}</h2>
      {description ? <p className="muted empty-state-description">{description}</p> : null}
      {action ? <div className="empty-state-action">{action}</div> : null}
    </section>
  );
}
