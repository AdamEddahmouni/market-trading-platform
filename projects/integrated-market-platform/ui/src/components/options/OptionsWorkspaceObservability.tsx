import { lazy, Suspense } from "react";
import { Link } from "react-router-dom";
import { useOptionsProductQuery, useWorkspaceOptionsQuery } from "../../api/hooks";
import { workspacePathForInstrument } from "../../api/instrumentIdentity";
import {
  ADMITTED_OPTIONS_RESEARCH_INSTRUMENT_ID,
  ADMITTED_REPLAY_INSTRUMENT_ID,
} from "../../api/schemas";
import type { Mode } from "../mode-session/types";
import { deriveLaneQueryState } from "../workspace-module-shared/laneQueryState";
import { ModeAwareWorkspaceLane } from "../workspace-module-shared/ModeAwareWorkspaceLane";
import { useWorkspaceInstrumentId } from "../workspace-module-shared/useWorkspaceInstrumentId";
import { OptionsProductSurface } from "./OptionsProductSurface";
import { OptionsWorkspacePanel } from "./OptionsWorkspacePanel";

const CanonicalInstrumentSelector = lazy(() =>
  import("../instrument-selector/CanonicalInstrumentSelector").then((module) => ({
    default: module.CanonicalInstrumentSelector,
  })),
);

type Props = {
  mode: Mode;
  onExplain?: (ref: string) => void;
  onInspect?: (ref: string) => void;
};

export function OptionsWorkspaceObservability({ mode, onExplain, onInspect }: Props) {
  const instrumentId = useWorkspaceInstrumentId();
  const optionsQuery = useWorkspaceOptionsQuery(instrumentId);
  const productQuery = useOptionsProductQuery(instrumentId, mode);
  const queryState = deriveLaneQueryState(optionsQuery, "options");

  return (
    <>
      <Suspense fallback={null}>
        <CanonicalInstrumentSelector label="Canonical instrument selector" />
      </Suspense>
      <ModeAwareWorkspaceLane
        mode={mode}
        moduleId="options"
        instrumentId={instrumentId}
        queryState={queryState}
        data={optionsQuery.data}
      >
        <OptionsProductSurface
          mode={mode}
          instrumentId={instrumentId}
          product={productQuery.data ?? null}
          loading={productQuery.isLoading}
          paperActionsPermitted={mode === "PAPER"}
        />
        <OptionsWorkspacePanel
          instrumentId={instrumentId}
          options={optionsQuery.data ?? null}
          loading={optionsQuery.isLoading}
          onExplain={onExplain}
          onInspect={onInspect}
        />
      </ModeAwareWorkspaceLane>
    </>
  );
}

export function optionsModuleDescription(instrumentId: string) {
  if (instrumentId === ADMITTED_REPLAY_INSTRUMENT_ID) {
    return `Unusual options activity from the admitted ${ADMITTED_REPLAY_INSTRUMENT_ID} whale fixture. Cooperative O6–O9 + SHARED P4 research uses ${ADMITTED_OPTIONS_RESEARCH_INSTRUMENT_ID}.`;
  }
  return "Cooperative options research snapshots (O6–O9) and cross-lane opportunity fusion (SHARED P4).";
}

export function OptionsModuleHeaderExtra({ instrumentId }: { instrumentId: string }) {
  if (instrumentId !== ADMITTED_REPLAY_INSTRUMENT_ID) return null;
  return (
    <p className="workspace-hint">
      <Link to={workspacePathForInstrument(ADMITTED_OPTIONS_RESEARCH_INSTRUMENT_ID, "options")}>
        Open {ADMITTED_OPTIONS_RESEARCH_INSTRUMENT_ID} cooperative research path
      </Link>
    </p>
  );
}
