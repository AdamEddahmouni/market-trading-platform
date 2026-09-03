import type { ReactNode } from "react";

type Props = {
  eyebrow?: string;
  title: string;
  subtitle?: ReactNode;
  meta?: ReactNode;
  actions?: ReactNode;
  restriction?: ReactNode;
  className?: string;
};

export function PageHeader({
  eyebrow,
  title,
  subtitle,
  meta,
  actions,
  restriction,
  className,
}: Props) {
  return (
    <header className={className ? `page-header ${className}` : "page-header"}>
      <div className="page-header-main">
        {eyebrow ? <span className="page-header-eyebrow">{eyebrow}</span> : null}
        <h1>{title}</h1>
        {subtitle ? <p className="page-header-subtitle">{subtitle}</p> : null}
        {meta ? <div className="page-header-meta">{meta}</div> : null}
      </div>
      {actions ? <div className="page-header-actions">{actions}</div> : null}
      {restriction ? <div className="page-header-restriction">{restriction}</div> : null}
    </header>
  );
}
