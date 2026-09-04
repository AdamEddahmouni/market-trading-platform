import { Link } from "react-router-dom";
import type { Mode } from "../mode-session/types";
import { EmptyState } from "./EmptyState";

type Props = {
  mode: Mode;
  laneLabel?: string;
};

function copyForMode(mode: Mode, laneLabel?: string): { title: string; description: string; exploreLabel: string } {
  const lane = laneLabel ? `${laneLabel} ` : "";
  if (mode === "LIVE") {
    return {
      title: "Select an instrument",
      description: `Live observational mode does not default to a replay fixture. Search and subscribe from Explore to open the ${lane}workspace.`,
      exploreLabel: "Go to Explore",
    };
  }
  if (mode === "PAPER") {
    return {
      title: "Select an instrument",
      description: `Open a symbol from Paper Command, Discover, or Explore to review ${lane}evidence in Workspace.`,
      exploreLabel: "Browse Explore",
    };
  }
  return {
    title: "Select an instrument",
    description: `Demo replay uses admitted fixtures. Open Explore or Workspace overview to choose a symbol for ${lane}inspection.`,
    exploreLabel: "Go to Explore",
  };
}

export function InstrumentSelectionEmpty({ mode, laneLabel }: Props) {
  const copy = copyForMode(mode, laneLabel);
  return (
    <section className="page instrument-selection-empty">
      <EmptyState
        title={copy.title}
        description={copy.description}
        action={
          <Link className="button-link" to="/explore">
            {copy.exploreLabel}
          </Link>
        }
      />
      <p className="muted instrument-selection-hint">
        <Link to="/workspace">Workspace overview</Link>
        {" · "}
        <Link to="/discover">Discover</Link>
      </p>
    </section>
  );
}
