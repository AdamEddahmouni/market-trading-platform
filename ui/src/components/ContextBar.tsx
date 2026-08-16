import type { ContextResponse } from "../api/client";

type Props = {
  context: ContextResponse;
  onQualityClick?: () => void;
};

export function ContextBar({ context, onQualityClick }: Props) {
  const { as_of_context, quality_summary, scope_symbols } = context;
  return (
    <header className="context-bar" role="banner">
      <div className="context-segment mode-replay">
        <span className="label">MODE</span>
        <strong>{as_of_context.mode}</strong>
      </div>
      <div className="context-segment">
        <span className="label">AS OF</span>
        <time dateTime={as_of_context.as_of_time}>{as_of_context.as_of_time}</time>
      </div>
      <div className="context-segment">
        <span className="label">SCOPE</span>
        <strong>{scope_symbols?.join(", ") ?? "—"}</strong>
      </div>
      <button type="button" className="context-segment quality-badge" onClick={onQualityClick}>
        <span className="label">QUALITY</span>
        <strong>{quality_summary.state}</strong>
      </button>
    </header>
  );
}
