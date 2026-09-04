import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useInstrumentCapabilitiesQuery, useProviderHealthQuery, useSubscribeMutation, useSymbolSearchQuery } from "../../api/hooks";

export function LiveObservationalPanel() {
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState("");
  const navigate = useNavigate();
  const searchQuery = useSymbolSearchQuery(query, query.length >= 1);
  const capabilitiesQuery = useInstrumentCapabilitiesQuery(selected, selected.length > 0);
  const healthQuery = useProviderHealthQuery();
  const subscribeMutation = useSubscribeMutation();

  const health = healthQuery.data;
  const isLive = health?.available === true;

  if (!isLive) {
    return (
      <section className="live-panel capability-panel unavailable">
        <h2>LIVE OBSERVATIONAL</h2>
        <p>{health?.reason ?? "Set IMP_LIVE_OBSERVATIONAL=1 to enable Moomoo observational mode."}</p>
      </section>
    );
  }

  return (
    <section className="live-panel">
      <h2>LIVE OBSERVATIONAL · MOOMOO</h2>
      <p className="live-health-summary">
        {String(health.lifecycle?.connection_state ?? "UNKNOWN")} · quota{" "}
        {health.quota?.active_count ?? 0}/{health.quota?.max_quota ?? "?"}
      </p>
      <label className="live-search-label">
        Symbol search
        <input
          className="live-search-input"
          value={query}
          onChange={(event) => setQuery(event.target.value.toUpperCase())}
          placeholder="Search a symbol"
        />
      </label>
      {searchQuery.data?.results?.length ? (
        <ul className="live-search-results">
          {searchQuery.data.results.map((row) => (
            <li key={row.instrument_id}>
              <button
                type="button"
                onClick={() => {
                  setSelected(row.instrument_id);
                  void fetch("/operator/recent", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ instrument_id: row.instrument_id, source: "EXPLORE" }),
                  });
                }}
              >
                {row.instrument_id}
              </button>
            </li>
          ))}
        </ul>
      ) : null}
      <h3>{selected} capabilities</h3>
      {capabilitiesQuery.isLoading ? <p>Loading capabilities…</p> : null}
      <ul className="capability-badge-list">
        {(capabilitiesQuery.data?.capabilities ?? []).map((cap) => (
          <li key={cap.capability_id} className={`capability-badge ${cap.state.toLowerCase()}`}>
            <strong>{cap.capability_id}</strong>
            <span>{cap.state}</span>
            {cap.data_provider ? <span>{cap.data_provider}</span> : null}
            {cap.reason ? <span>{cap.reason}</span> : null}
          </li>
        ))}
      </ul>
      <div className="live-actions">
        <button
          type="button"
          disabled={subscribeMutation.isPending || !selected}
          onClick={() =>
            subscribeMutation.mutate(
              { instrumentId: selected, capabilities: ["BASIC_QUOTE", "TRADES", "ORDER_BOOK"] },
              {
                onSuccess: () => {
                  void fetch("/operator/recent", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ instrument_id: selected, source: "EXPLORE" }),
                  });
                  void fetch("/operator/workspace", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                      layout: {
                        layout_schema_version: 1,
                        open_panels: ["live-market"],
                        panel_order: ["live-market"],
                        selected_instrument: selected,
                      },
                      name: "Active",
                    }),
                  });
                  navigate(`/workspace/${selected}`);
                },
              },
            )
          }
        >
          Subscribe &amp; open workspace
        </button>
        <Link to={selected ? `/workspace/${selected}` : "/workspace"}>Open workspace</Link>
      </div>
    </section>
  );
}
