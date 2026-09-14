import type { Mode } from "../mode-session/types";

type Props = {
  mode: Mode;
};

const modeCopy: Record<Mode, string> = {
  DEMO: "Demo · historical research",
  PAPER: "Paper · internal simulation",
  LIVE: "Live · observation only",
};

export function ImpExecutionPosture({ mode }: Props) {
  return (
    <div className="imp-execution-posture" aria-label="Execution posture">
      <span className="imp-posture-mode">{modeCopy[mode]}</span>
      <span className="imp-posture-lock" title="Broker execution remains disabled in this UI build">
        Live execution off
      </span>
    </div>
  );
}
