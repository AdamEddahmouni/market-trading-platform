import type { ContextResponse } from "../api/client";

type Props = {
  context: ContextResponse;
  onQualityClick?: () => void;
};

function formatDataLabel(context: ContextResponse["as_of_context"]) {
  if (context.data_mode === "LIVE_OBSERVATIONAL") {
    return `LIVE OBSERVATIONAL · ${context.data_provider ?? "MOOMOO"}`;
  }
  return context.data_mode?.replace(/_/g, " ") ?? context.mode;
}

function formatExecutionLabel(context: ContextResponse["as_of_context"]) {
  if (context.execution_mode === "INTERNAL_SIMULATION") {
    return "INTERNAL SIMULATION · PAPER ONLY";
  }
  if (context.execution_mode === "NONE") {
    return "NONE";
  }
  return context.execution_mode?.replace(/_/g, " ") ?? "NONE";
}

export function ContextBar({ context, onQualityClick }: Props) {
  const { as_of_context, quality_summary, scope_symbols } = context;
  const isLive = as_of_context.data_mode === "LIVE_OBSERVATIONAL";
  return (
    <header className="context-bar" role="banner">
      <div className={`context-segment ${isLive ? "mode-live" : "mode-replay"}`}>
        <span className="label">DATA</span>
        <strong title={as_of_context.mode}>{formatDataLabel(as_of_context)}</strong>
      </div>
      <div className="context-segment">
        <span className="label">EXECUTION</span>
        <strong>{formatExecutionLabel(as_of_context)}</strong>
      </div>
      {as_of_context.execution_authority ? (
        <div className="context-segment">
          <span className="label">AUTH</span>
          <strong>{as_of_context.execution_authority}</strong>
        </div>
      ) : null}
      <div className="context-segment">
        <span className="label">{isLive ? "MARKET" : "AS OF"}</span>
        <time dateTime={as_of_context.as_of_time}>{as_of_context.as_of_time}</time>
      </div>
      <div className="context-segment">
        <span className="label">SCOPE</span>
        <strong>
          {isLive
            ? scope_symbols?.length
              ? scope_symbols.join(", ")
              : "SELECT AN INSTRUMENT"
            : (scope_symbols?.join(", ") ?? "—")}
        </strong>
      </div>
      <button type="button" className="context-segment quality-badge" onClick={onQualityClick}>
        <span className="label">{isLive ? "HEALTH" : "QUALITY"}</span>
        <strong>{quality_summary.state}</strong>
        {quality_summary.detail ? <span className="context-detail">{quality_summary.detail}</span> : null}
      </button>
    </header>
  );
}
