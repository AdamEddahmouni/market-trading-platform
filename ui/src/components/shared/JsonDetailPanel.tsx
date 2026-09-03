import { useId } from "react";
import { flattenJsonDetail, type JsonDetailRow } from "./jsonDetailPresentation";

type Props = {
  title: string;
  value: unknown;
  defaultOpen?: boolean;
  className?: string;
};

function JsonDetailRows({ rows, depth = 0 }: { rows: JsonDetailRow[]; depth?: number }) {
  return (
    <dl className="json-detail-rows" data-depth={depth}>
      {rows.map((row) => (
        <div key={row.key} className="json-detail-row">
          <dt>{row.label}</dt>
          <dd>
            {row.nested && row.nested.length > 0 ? (
              <details className="json-detail-nested">
                <summary>{row.value}</summary>
                <JsonDetailRows rows={row.nested} depth={depth + 1} />
              </details>
            ) : (
              row.value
            )}
          </dd>
        </div>
      ))}
    </dl>
  );
}

export function JsonDetailPanel({ title, value, defaultOpen = false, className }: Props) {
  const panelId = useId();
  const rows = flattenJsonDetail(value);
  if (rows.length === 0) return null;

  return (
    <details className={className ? `json-detail-panel ${className}` : "json-detail-panel"} open={defaultOpen}>
      <summary id={panelId}>{title}</summary>
      <div className="json-detail-body" aria-labelledby={panelId}>
        <JsonDetailRows rows={rows} />
        <details className="json-detail-raw">
          <summary>Raw JSON</summary>
          <pre>{JSON.stringify(value, null, 2)}</pre>
        </details>
      </div>
    </details>
  );
}
