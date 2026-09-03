import type { PaperRiskContextModel } from "./buildPaperRiskContext";

type Props = {
  model: PaperRiskContextModel;
};

export function PaperRiskContext({ model }: Props) {
  return (
    <section className="panel paper-cockpit-panel" aria-labelledby="paper-risk-context-heading">
      <h2 id="paper-risk-context-heading">Paper risk context</h2>
      {model.phase === "loading" ? <p role="status">Loading portfolio risk…</p> : null}
      {model.phase === "error" || model.phase === "unavailable" ? (
        <p className="paper-cockpit-warning" role="status">
          {model.warnings[0] ?? "Portfolio risk unavailable."}
        </p>
      ) : null}
      {model.phase === "ready" ? (
        <>
          <dl className="paper-cockpit-meta">
            {model.items.map((item) => (
              <div key={item.id} className={item.unavailable ? "unavailable" : undefined}>
                <dt>{item.label}</dt>
                <dd>
                  {item.value}
                  {item.detail ? <span className="muted"> · {item.detail}</span> : null}
                </dd>
              </div>
            ))}
            {model.openOrdersForSymbol > 0 ? (
              <div>
                <dt>Open orders ({model.items.find((i) => i.id === "symbol-position") ? "symbol" : "portfolio"})</dt>
                <dd>{model.openOrdersForSymbol} open for this symbol</dd>
              </div>
            ) : null}
          </dl>
          {model.warnings.map((warning) => (
            <p key={warning} className="paper-cockpit-warning" role="status">
              {warning}
            </p>
          ))}
        </>
      ) : null}
    </section>
  );
}
