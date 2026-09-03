import type { Mode } from "../mode-session/types";

/** Operator mutations (watchlist, captures) are permitted only in Paper mode. */
export function canMutateOperatorSettings(mode: Mode): boolean {
  return mode === "PAPER";
}

export function operatorSettingsRestrictionNote(mode: Mode): string | null {
  if (mode === "DEMO") {
    return "Demo is exploration only. Operator mutations are disabled — switch to Paper mode to manage watchlists and captures.";
  }
  if (mode === "LIVE") {
    return "Live is read-only here. Operator mutations are disabled — use Paper mode for simulation housekeeping.";
  }
  return null;
}
