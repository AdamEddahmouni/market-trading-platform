import { Link } from "react-router-dom";
import type { PaperPortfolioResponse } from "../../api/client";
import { derivePaperExceptions } from "./paperDashboardViewModel";

type Props = { portfolio?: PaperPortfolioResponse; state: "loading" | "ready" | "error" };

export function PaperExceptionsPanel({ portfolio, state }: Props) {
  const exceptions = state === "ready" && portfolio ? derivePaperExceptions(portfolio) : [];
  return (
    <section className="paper-panel paper-exceptions-panel" aria-label="Active exceptions">
      <header><h2>Active exceptions</h2><span>{exceptions.length}</span></header>
      {state === "loading" ? <p role="status">Loading exceptions…</p> : null}
      {state === "error" || !portfolio ? <p className="unavailable">Portfolio exceptions unavailable.</p> : null}
      {state === "ready" && portfolio && exceptions.length === 0 ? <p>No active exceptions</p> : null}
      {exceptions.length > 0 ? <ul>{exceptions.map((item) => <li key={`${item.code}-${item.message}`} data-severity={item.severity}><code>{item.code}</code><strong>{item.message}</strong>{item.detail ? <span>{item.detail}</span> : null}</li>)}</ul> : null}
      <Link to="/portfolio">Open full portfolio</Link>
    </section>
  );
}
