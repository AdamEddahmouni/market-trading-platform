import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  useInstrumentCapabilitiesQuery,
  useSubscribeMutation,
  useSymbolSearchQuery,
} from "../../api/hooks";
import type { ProviderHealthResponse } from "./liveDashboardViewModel";

type Props = {
  health?: ProviderHealthResponse;
  state: "loading" | "ready" | "error";
};

export function LiveSymbolLookup({ health, state }: Props) {
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState("");
  const navigate = useNavigate();
  const searchQuery = useSymbolSearchQuery(query, query.length >= 1 && health?.available === true);
  const capabilitiesQuery = useInstrumentCapabilitiesQuery(selected, selected.length > 0);
  const subscribeMutation = useSubscribeMutation();
  const observationalReady = state === "ready" && health?.available === true;

  return (
    <section className="live-panel live-symbol-panel" aria-label="Symbol lookup">
      <header className="live-panel-heading">
        <div>
          <p className="live-eyebrow">Observational entry</p>
          <h2>Find a symbol</h2>
        </div>
        <Link to="/diagnostics/provider">Provider diagnostics</Link>
      </header>

      {state === "loading" ? <p role="status">Checking observational access…</p> : null}
      {state === "error" || !observationalReady ? (
        <p className="unavailable">{health?.reason ?? "Set IMP_LIVE_OBSERVATIONAL=1 to enable live symbol search."}</p>
      ) : (
        <>
          <label className="live-search-label">
            Symbol search
            <input
              className="live-search-input"
              value={query}
              onChange={(event) => setQuery(event.target.value.toUpperCase())}
              placeholder="Search a symbol"
            />
          </label>
          {searchQuery.isLoading ? <p role="status">Searching symbols…</p> : null}
          {searchQuery.data?.results?.length ? (
            <ul className="live-search-results">
              {searchQuery.data.results.map((row) => (
                <li key={row.instrument_id}>
                  <button type="button" onClick={() => setSelected(row.instrument_id)}>
                    {row.instrument_id}
                  </button>
                </li>
              ))}
            </ul>
          ) : null}
          {selected ? (
            <>
              <h3>{selected} capabilities</h3>
              {capabilitiesQuery.isLoading ? <p role="status">Loading capabilities…</p> : null}
              <ul className="live-capability-list">
                {(capabilitiesQuery.data?.capabilities ?? []).map((capability) => (
                  <li key={capability.capability_id}>
                    <strong>{capability.capability_id}</strong>
                    <span>{capability.state}</span>
                  </li>
                ))}
              </ul>
            </>
          ) : (
            <p className="muted">Select a symbol to inspect live capabilities before opening a workspace.</p>
          )}
          <div className="live-symbol-actions">
            <button
              type="button"
              disabled={!selected || subscribeMutation.isPending}
              onClick={() =>
                subscribeMutation.mutate(
                  { instrumentId: selected, capabilities: ["BASIC_QUOTE", "TRADES", "ORDER_BOOK"] },
                  {
                    onSuccess: () => {
                      void fetch("/operator/recent", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ instrument_id: selected, source: "LIVE_NOW" }),
                      });
                      navigate(`/workspace/${selected}`);
                    },
                  },
                )
              }
            >
              Subscribe and open workspace
            </button>
            <Link to={selected ? `/workspace/${selected}` : "/workspace"}>Open workspace</Link>
          </div>
        </>
      )}
    </section>
  );
}
