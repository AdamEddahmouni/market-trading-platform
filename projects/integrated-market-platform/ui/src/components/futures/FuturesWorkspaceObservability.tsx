import { lazy, Suspense } from "react";
import { useFuturesProductQuery, useWorkspaceFuturesQuery } from "../../api/hooks";
import type { Mode } from "../mode-session/types";
import { deriveLaneQueryState } from "../workspace-module-shared/laneQueryState";
import { ModeAwareWorkspaceLane } from "../workspace-module-shared/ModeAwareWorkspaceLane";
import { useWorkspaceInstrumentId } from "../workspace-module-shared/useWorkspaceInstrumentId";
import { FuturesProductSurface } from "./FuturesProductSurface";
import { FuturesWorkspacePanel } from "./FuturesWorkspacePanel";

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

export function FuturesWorkspaceObservability({ mode, onExplain, onInspect }: Props) {
  const instrumentId = useWorkspaceInstrumentId();
  const futuresQuery = useWorkspaceFuturesQuery(instrumentId);
  const productQuery = useFuturesProductQuery(instrumentId, mode);
  const queryState = deriveLaneQueryState(futuresQuery, "futures");

  return (
    <>
      <Suspense fallback={null}>
        <CanonicalInstrumentSelector label="Canonical instrument selector" />
      </Suspense>
      <ModeAwareWorkspaceLane
        mode={mode}
        moduleId="futures"
        instrumentId={instrumentId}
        queryState={queryState}
        data={futuresQuery.data}
      >
        <FuturesProductSurface
          mode={mode}
          instrumentId={instrumentId}
          product={productQuery.data ?? null}
          loading={productQuery.isLoading}
          paperActionsPermitted={mode === "PAPER"}
        />
        <FuturesWorkspacePanel
          instrumentId={instrumentId}
          futures={futuresQuery.data ?? null}
          loading={futuresQuery.isLoading}
          onExplain={onExplain}
          onInspect={onInspect}
        />
      </ModeAwareWorkspaceLane>
    </>
  );
}

export const FUTURES_MODULE_DESCRIPTION =
  "ES CME depth snapshots from the admitted synthetic fixture. Imbalance signals are depth-derived, not CFTC positioning.";
