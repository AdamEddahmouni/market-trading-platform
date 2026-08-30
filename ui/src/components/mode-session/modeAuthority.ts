import type { AsOfContext } from "../../api/client";
import type { Mode } from "./types";

type ExecutionContext = Pick<
  AsOfContext,
  "data_mode" | "execution_mode" | "execution_authority"
>;

export type ModeContextEvaluation = {
  status: "compatible" | "mismatch" | "unavailable";
  paperActionsPermitted: boolean;
  actualSummary: string;
};

export function hasPaperAuthority(
  context: Partial<ExecutionContext> | undefined,
): boolean {
  return (
    context?.execution_mode === "INTERNAL_SIMULATION" &&
    context.execution_authority === "PAPER_ONLY"
  );
}

export function evaluateModeContext(
  mode: Mode,
  context: AsOfContext | undefined,
): ModeContextEvaluation {
  if (!context) {
    return {
      status: "unavailable",
      paperActionsPermitted: false,
      actualSummary: "Unavailable",
    };
  }

  const noExecution =
    context.execution_mode === "NONE" && context.execution_authority === "BLOCKED";
  const compatible =
    mode === "DEMO"
      ? (context.data_mode === "FIXTURE_REPLAY" ||
          context.data_mode === "HISTORICAL_CAPTURE") &&
        noExecution
      : mode === "PAPER"
        ? hasPaperAuthority(context)
        : (context.data_mode === "LIVE_OBSERVATIONAL" ||
            context.data_mode === "BROKER_DELAYED") &&
          noExecution;

  return {
    status: compatible ? "compatible" : "mismatch",
    paperActionsPermitted: mode === "PAPER" && compatible,
    actualSummary: `DATA ${context.data_mode ?? context.mode} · EXEC ${context.execution_mode ?? "UNKNOWN"} · AUTH ${context.execution_authority ?? "UNKNOWN"}`,
  };
}

export function canUsePaperActions(
  mode: Mode,
  globalPaperPermission: boolean,
  actionContext: Partial<ExecutionContext> | undefined,
): boolean {
  return mode === "PAPER" && globalPaperPermission && hasPaperAuthority(actionContext);
}
