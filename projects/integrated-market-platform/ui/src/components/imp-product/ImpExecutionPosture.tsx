import { usePaperPortfolioQuery } from "../../api/hooks";
import { CopyableIdentifier } from "../imp-ui/CopyableIdentifier";
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
  const paperPortfolioQuery = usePaperPortfolioQuery("PAPER", mode === "PAPER");
  const paperAccountId = paperPortfolioQuery.data?.account.paper_account_id;

  return (
    <div className="imp-execution-posture" aria-label="Execution posture">
      <span className="imp-posture-mode">{modeCopy[mode]}</span>
      {mode === "PAPER" && paperAccountId ? (
        <CopyableIdentifier
          value={paperAccountId}
          prefix="Acct"
          className="imp-posture-account"
        />
      ) : null}
      <span className="imp-posture-lock" title="Broker execution remains disabled in this UI build">
        Live off
      </span>
    </div>
  );
}
