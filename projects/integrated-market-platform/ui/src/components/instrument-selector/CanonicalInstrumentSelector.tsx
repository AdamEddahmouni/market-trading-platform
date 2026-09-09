import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useInstrumentSelectorQuery } from "../../api/hooks";
import {
  type CanonicalSelectorResult,
  selectionDisabledReason,
  selectionWorkspaceSuffix,
  workspacePathForInstrument,
} from "../../api/instrumentIdentity";

type Props = {
  label?: string;
  placeholder?: string;
  maxResults?: number;
};

function groupLabel(result: CanonicalSelectorResult): string {
  return `${result.asset_class} · ${result.instrument_kind.replace(/_/g, " ")}`;
}

export function CanonicalInstrumentSelector({
  label = "Instrument search",
  placeholder = "Search canonical instruments",
  maxResults = 25,
}: Props) {
  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(-1);
  const navigate = useNavigate();
  const searchQuery = useInstrumentSelectorQuery(query, query.trim().length >= 1, maxResults);
  const results = useMemo(
    () => (searchQuery.data?.results ?? []) as CanonicalSelectorResult[],
    [searchQuery.data?.results],
  );

  function openResult(result: CanonicalSelectorResult) {
    const suffix = selectionWorkspaceSuffix(result);
    if (suffix === null) return;
    navigate(workspacePathForInstrument(result.instrument_id, suffix || undefined));
  }

  return (
    <section className="instrument-selector" aria-label={label}>
      <label className="instrument-selector-label">
        {label}
        <input
          className="instrument-selector-input"
          value={query}
          onChange={(event) => {
            setQuery(event.target.value);
            setActiveIndex(-1);
          }}
          onKeyDown={(event) => {
            if (event.key === "ArrowDown") {
              event.preventDefault();
              setActiveIndex((current) => Math.min(current + 1, results.length - 1));
            }
            if (event.key === "ArrowUp") {
              event.preventDefault();
              setActiveIndex((current) => Math.max(current - 1, 0));
            }
            if (event.key === "Enter" && activeIndex >= 0 && results[activeIndex]) {
              event.preventDefault();
              openResult(results[activeIndex]);
            }
          }}
          placeholder={placeholder}
        />
      </label>
      {searchQuery.isLoading ? <p role="status">Searching canonical catalog…</p> : null}
      {searchQuery.isError ? <p role="alert">Instrument search unavailable.</p> : null}
      {results.length > 0 ? (
        <ul className="instrument-selector-results" role="listbox">
          {results.map((result, index) => {
            const disabledReason = selectionDisabledReason(result);
            return (
              <li key={result.instrument_id}>
                <button
                  type="button"
                  role="option"
                  aria-selected={index === activeIndex}
                  className={index === activeIndex ? "is-active" : undefined}
                  disabled={disabledReason !== null && !result.execution_eligible}
                  title={disabledReason ?? undefined}
                  onClick={() => openResult(result)}
                >
                  <span className="instrument-selector-primary">{result.display_label}</span>
                  <span className="instrument-selector-meta">{groupLabel(result)}</span>
                  <code>{result.instrument_id}</code>
                  {disabledReason ? <span className="instrument-selector-reason">{disabledReason}</span> : null}
                </button>
              </li>
            );
          })}
        </ul>
      ) : query.trim().length > 0 && !searchQuery.isLoading ? (
        <p className="muted">EMPTY — no canonical matches.</p>
      ) : null}
    </section>
  );
}
