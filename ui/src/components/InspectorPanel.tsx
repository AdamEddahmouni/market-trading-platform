import { useEffect, useState } from "react";

type Props = {
  payload: Record<string, unknown> | null;
  preferredTab?: string | null;
  onClose: () => void;
};

export function InspectorPanel({ payload, preferredTab, onClose }: Props) {
  const defaultFromPayload =
    payload && typeof payload.default_tab === "string" ? payload.default_tab : "SUMMARY";
  const [tab, setTab] = useState(defaultFromPayload);

  useEffect(() => {
    if (!payload) return;
    const next =
      preferredTab ??
      (typeof payload.default_tab === "string" ? payload.default_tab : "SUMMARY");
    setTab(next);
  }, [payload, preferredTab]);

  if (!payload) return null;
  const tabs = payload.tabs as Record<string, Record<string, unknown>> | undefined;
  const active = tabs?.[tab];
  const tabNames = tabs ? Object.keys(tabs) : ["SUMMARY"];

  return (
    <aside className="inspector-panel" aria-label="Evidence Inspector">
      <header>
        <h2>Evidence Inspector</h2>
        <button type="button" onClick={onClose}>
          Close
        </button>
      </header>
      <div className="inspector-tabs" role="tablist">
        {tabNames.map((name) => (
          <button
            key={name}
            type="button"
            role="tab"
            aria-selected={tab === name}
            className={tab === name ? "active" : ""}
            onClick={() => setTab(name)}
          >
            {name}
          </button>
        ))}
      </div>
      <div className="inspector-body" role="tabpanel">
        {active ? (
          <pre>{JSON.stringify(active, null, 2)}</pre>
        ) : (
          <p>No tab content.</p>
        )}
      </div>
    </aside>
  );
}
