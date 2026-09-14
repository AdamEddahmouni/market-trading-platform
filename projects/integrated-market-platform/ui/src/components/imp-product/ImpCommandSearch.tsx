import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";

const TICKER_PATTERN = /^[A-Z][A-Z0-9.\-]{0,15}$/;

function normalizeQuery(raw: string): string {
  return raw.trim().toUpperCase();
}

export function ImpCommandSearch() {
  const navigate = useNavigate();
  const [query, setQuery] = useState("");

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    const normalized = normalizeQuery(query);
    if (!normalized) return;
    if (TICKER_PATTERN.test(normalized)) {
      navigate(`/workspace/${encodeURIComponent(normalized)}`);
      return;
    }
    navigate(`/explore?q=${encodeURIComponent(normalized)}`);
  };

  return (
    <form className="imp-command-search" onSubmit={onSubmit} role="search">
      <label className="sr-only" htmlFor="imp-command-search-input">
        Search symbols, ideas, research
      </label>
      <input
        id="imp-command-search-input"
        type="search"
        name="q"
        placeholder="Search symbols, ideas, research…"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        autoComplete="off"
        spellCheck={false}
      />
    </form>
  );
}
