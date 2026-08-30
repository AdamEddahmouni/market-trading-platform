import type { AsOfContext } from "../../api/client";
import { evaluateModeContext } from "./modeAuthority";
import type { Mode } from "./types";

type Props = {
  mode: Mode;
  context?: AsOfContext;
  contextState: "loading" | "ready" | "error";
  onSwitchMode: () => void;
};

const boundaries: Record<Mode, string> = {
  DEMO: "Historical research · No execution",
  PAPER: "Internal simulation · Paper authority only",
  LIVE: "Current market observation · Execution locked",
};

export function ModeEnvironmentBar({ mode, context, contextState, onSwitchMode }: Props) {
  const evaluation = evaluateModeContext(mode, context);

  let contextStatus;
  if (contextState === "loading") {
    contextStatus = (
      <p className="mode-environment-status" role="status">
        Verifying backend context…
      </p>
    );
  } else if (contextState === "error" || evaluation.status === "unavailable") {
    contextStatus = (
      <p className="mode-environment-alert" role="alert">
        Backend context unavailable. Execution controls remain locked.
      </p>
    );
  } else if (evaluation.status === "mismatch") {
    contextStatus = (
      <p className="mode-environment-alert" role="alert">
        Selected {mode}; backend reports {evaluation.actualSummary}. UI mode selection does not
        change backend authority.
      </p>
    );
  } else {
    contextStatus = (
      <p className="mode-environment-status">
        Backend aligned · {evaluation.actualSummary}
      </p>
    );
  }

  return (
    <section
      className="mode-environment-bar"
      data-mode={mode}
      aria-label="Session environment"
    >
      <div className="mode-environment-identity">
        <span className="mode-environment-label">Active environment</span>
        <strong>{mode}</strong>
        <span>{boundaries[mode]}</span>
      </div>
      <div className="mode-environment-context">{contextStatus}</div>
      <button type="button" onClick={onSwitchMode}>
        Switch mode
      </button>
    </section>
  );
}
