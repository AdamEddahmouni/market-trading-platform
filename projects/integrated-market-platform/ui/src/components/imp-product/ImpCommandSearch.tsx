import { useEffect, useMemo, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";

export const IMP_COMMAND_SEARCH_INPUT_ID = "imp-command-search-input";

const TICKER_PATTERN = /^[A-Z][A-Z0-9.\-]{0,15}$/;

type CommandDestination = {
  label: string;
  hint: string;
  path: string;
};

const COMMAND_DESTINATIONS: CommandDestination[] = [
  { label: "Workspace", hint: "Resume active work", path: "/workspace" },
  { label: "Radar", hint: "Scan opportunities", path: "/radar" },
  { label: "Portfolio", hint: "Review positions and orders", path: "/portfolio" },
  { label: "Research", hint: "Open evidence and validation", path: "/research" },
  { label: "Lab", hint: "Open experiment workbench", path: "/lab" },
  { label: "Control", hint: "Check platform operations", path: "/control" },
];

function normalizeQuery(raw: string): string {
  return raw.trim().toUpperCase();
}

export function ImpCommandSearch() {
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [focused, setFocused] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);
  const normalized = normalizeQuery(query);
  const destinationMatches = useMemo(
    () => COMMAND_DESTINATIONS.filter((destination) => destination.label.toLowerCase().includes(normalized.toLowerCase())),
    [normalized],
  );
  const suggestions =
    destinationMatches.length > 0
      ? destinationMatches
      : TICKER_PATTERN.test(normalized)
        ? [{ label: `Open ${normalized} in Workspace`, hint: "Open instrument workspace", path: `/workspace/${encodeURIComponent(normalized)}` }]
        : [];

  useEffect(() => {
    setActiveIndex(0);
  }, [normalized]);

  function goTo(path: string) {
    navigate(path);
    setQuery("");
    setFocused(false);
  }

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    if (!normalized) return;
    const destination = COMMAND_DESTINATIONS.find(
      (candidate) => normalizeQuery(candidate.label) === normalized,
    );
    if (destination) {
      goTo(destination.path);
      return;
    }
    if (TICKER_PATTERN.test(normalized)) {
      goTo(`/workspace/${encodeURIComponent(normalized)}`);
      return;
    }
    navigate(`/radar/screeners?q=${encodeURIComponent(normalized)}`);
    setFocused(false);
  };

  return (
    <form className="imp-command-search" onSubmit={onSubmit} role="search">
      <label className="sr-only" htmlFor={IMP_COMMAND_SEARCH_INPUT_ID}>
        Search symbols, ideas, research
      </label>
      <input
        id={IMP_COMMAND_SEARCH_INPUT_ID}
        type="search"
        name="q"
        placeholder="Search symbols, ideas, research…"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        onFocus={() => {
          setFocused(true);
          setActiveIndex(0);
        }}
        onKeyDown={(event) => {
          if (event.key === "ArrowDown" && suggestions.length > 0) {
            event.preventDefault();
            setActiveIndex((index) => Math.min(index + 1, suggestions.length - 1));
            return;
          }
          if (event.key === "ArrowUp" && suggestions.length > 0) {
            event.preventDefault();
            setActiveIndex((index) => Math.max(index - 1, 0));
            return;
          }
          if (event.key === "Enter" && suggestions[activeIndex]) {
            event.preventDefault();
            goTo(suggestions[activeIndex].path);
            return;
          }
          if (event.key === "Escape") {
            setFocused(false);
            event.currentTarget.blur();
          }
        }}
        aria-activedescendant={focused && suggestions[activeIndex] ? `imp-command-option-${activeIndex}` : undefined}
        aria-autocomplete="list"
        aria-controls="imp-command-search-menu"
        aria-expanded={focused && suggestions.length > 0}
        autoComplete="off"
        spellCheck={false}
      />
      {focused && suggestions.length > 0 ? (
        <div id="imp-command-search-menu" className="imp-command-search-menu" role="listbox" aria-label="Command destinations">
          {suggestions.map((destination, index) => (
            <button
              key={destination.path}
              id={`imp-command-option-${index}`}
              type="button"
              role="option"
              aria-selected={activeIndex === index}
              className={activeIndex === index ? "is-active" : undefined}
              onMouseEnter={() => setActiveIndex(index)}
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => goTo(destination.path)}
            >
              <span>{destination.label}</span>
              <small>{destination.hint}</small>
            </button>
          ))}
        </div>
      ) : null}
    </form>
  );
}
