import type { Mode } from "./types";

export type ModeMetadata = {
  id: Mode;
  label: string;
  descriptor: string;
  launchCopy: string;
  cssToken: string;
  navHint?: string;
};

export const MODE_METADATA: Record<Mode, ModeMetadata> = {
  DEMO: {
    id: "DEMO",
    label: "Demo",
    descriptor: "Historical replay",
    launchCopy: "Explore historical market conditions with replay data and no execution.",
    cssToken: "demo",
    navHint: "Frozen bridges",
  },
  PAPER: {
    id: "PAPER",
    label: "Paper",
    descriptor: "Simulated execution",
    launchCopy: "Practice decisions and place simulated orders against market data.",
    cssToken: "paper",
    navHint: "Candidate discovery",
  },
  LIVE: {
    id: "LIVE",
    label: "Live",
    descriptor: "Read-only market data",
    launchCopy: "Watch current market data. Order execution remains locked by default.",
    cssToken: "live",
    navHint: "Live scanner",
  },
};

export const MODE_LAUNCH_ORDER: Mode[] = ["DEMO", "PAPER", "LIVE"];

export function modeMetadata(mode: Mode): ModeMetadata {
  return MODE_METADATA[mode];
}
