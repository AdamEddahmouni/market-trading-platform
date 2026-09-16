import { useEffect, useState } from "react";

/**
 * Reactive matchMedia hook. Used for breakpoint-dependent behavior (e.g. the
 * Radar detail sheet) — CSS stays the source of truth for layout; this only
 * switches interaction patterns.
 */
export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(() => window.matchMedia(query).matches);

  useEffect(() => {
    const media = window.matchMedia(query);
    const onChange = () => setMatches(media.matches);
    onChange();
    media.addEventListener("change", onChange);
    return () => media.removeEventListener("change", onChange);
  }, [query]);

  return matches;
}
