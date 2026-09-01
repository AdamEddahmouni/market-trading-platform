import type { Mode } from "../mode-session/types";
import { ADMITTED_ORDER_FLOW_INSTRUMENT_ID } from "../../api/schemas";
import { WorkspaceModuleModeShell } from "../workspace-module-shared/WorkspaceModuleModeShell";
import { useWorkspaceInstrumentId } from "../workspace-module-shared/useWorkspaceInstrumentId";
import { workspaceModuleModeDescription } from "../workspace-module-shared/workspaceModuleModeDescription";
import {
  ORDER_BOOK_MODULE_DESCRIPTION,
  OrderBookWorkspaceObservability,
} from "./OrderBookWorkspaceObservability";

type Props = {
  mode: Mode;
  onExplain?: (ref: string) => void;
  onInspect?: (ref: string) => void;
};

export function ModeOrderBookWorkspaceRoute({ mode, ...props }: Props) {
  const instrumentId = useWorkspaceInstrumentId(ADMITTED_ORDER_FLOW_INSTRUMENT_ID);

  return (
    <WorkspaceModuleModeShell
      mode={mode}
      instrumentId={instrumentId}
      active="order-book"
      pageClassName="order-book-workspace-page"
      moduleTitle="Order Book Workspace"
      description={workspaceModuleModeDescription(
        ORDER_BOOK_MODULE_DESCRIPTION,
        mode,
        "order-book",
      )}
    >
      <OrderBookWorkspaceObservability mode={mode} {...props} />
    </WorkspaceModuleModeShell>
  );
}
