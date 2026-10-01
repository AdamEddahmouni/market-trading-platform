/**
 * Opening the platform lands on the Screener. The Demo/Paper/Live chooser and the older
 * workstation are archived: still in the code and reachable by their own paths, but a fresh
 * visit to "/" (the desktop shortcut, a bookmark, a typed address) no longer starts there.
 * This runs once at page load, so in-app navigation inside the archived workstation is unchanged.
 */
export function startPath(pathname: string, search: string): string | null {
  return pathname === "/" || pathname === "" ? `/screener${search}` : null;
}

export function redirectFreshVisitToScreener(location: Location = window.location, history: History = window.history): void {
  const target = startPath(location.pathname, location.search);
  if (target) history.replaceState(history.state, "", `${target}${location.hash}`);
}
