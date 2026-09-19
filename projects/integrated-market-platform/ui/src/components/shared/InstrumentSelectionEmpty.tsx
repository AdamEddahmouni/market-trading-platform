import { lazy, Suspense } from "react";
import { Link } from "react-router-dom";
import type { Mode } from "../mode-session/types";
import { EmptyState } from "./EmptyState";

const CanonicalInstrumentSelector = lazy(() =>
  import("../instrument-selector/CanonicalInstrumentSelector").then((module) => ({
    default: module.CanonicalInstrumentSelector,
  })),
);

type Props = {
  mode: Mode;
  laneLabel?: string;
};

function copyForMode(mode: Mode, laneLabel?: string): { title: string; description: string; exploreLabel: string } {
  const lane = laneLabel ? `${laneLabel} ` : "";
  if (mode === "LIVE") {
    return {
      title: "Select an instrument",
      description: `Live observational mode does not default to a replay fixture. Search Radar screeners and subscribe to open the ${lane}workspace.`,
      exploreLabel: "Open Radar screeners",
    };
  }
  if (mode === "PAPER") {
    return {
      title: "Select an instrument",
      description: `Open a symbol from Paper Command or Radar to review ${lane}evidence in Workspace.`,
      exploreLabel: "Browse Radar",
    };
  }
  return {
    title: "Select an instrument",
    description: `Demo replay uses admitted fixtures. Open Radar or Workspace overview to choose a symbol for ${lane}inspection.`,
    exploreLabel: "Open Radar",
  };
}

export function InstrumentSelectionEmpty({ mode, laneLabel }: Props) {
  const copy = copyForMode(mode, laneLabel);
  return (
    <section className="page instrument-selection-empty">
      <Suspense fallback={null}>
        <CanonicalInstrumentSelector label="Search instruments" />
      </Suspense>
      <EmptyState
        title={copy.title}
        description={copy.description}
        action={
          <Link className="button-link" to="/radar/screeners">
            {copy.exploreLabel}
          </Link>
        }
      />
      <p className="muted instrument-selection-hint">
        <Link to="/workspace">Workspace overview</Link>
        {" · "}
        <Link to="/radar">Radar</Link>
      </p>
    </section>
  );
}
