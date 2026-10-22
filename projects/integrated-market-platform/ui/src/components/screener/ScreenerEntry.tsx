import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../../api/endpoints";
import { queryKeys } from "../../api/hooks";
import { ScreenerPage } from "./ScreenerPage";

/** Current markets have no replay dataset; verify the backend session before mounting any Screener effects. */
export function ScreenerEntry() {
  const context = useQuery({
    queryKey: queryKeys.context,
    queryFn: api.getContext,
    staleTime: 0,
    refetchOnMount: "always",
    refetchInterval: 5_000,
    retry: false,
  });
  const session = context.data?.as_of_context;
  const currentMarket = (session?.data_mode === "LIVE_OBSERVATIONAL" || session?.data_mode === "BROKER_DELAYED")
    && session.mode !== "REPLAY" && !session.controlled_replay && !session.not_live_market_data
    && !context.data?.controlled_replay && !context.data?.not_live_market_data;

  if (!context.isError && context.isFetchedAfterMount && currentMarket) return <ScreenerPage />;

  const checking = !context.isError && (!context.isFetchedAfterMount || context.isPending);
  return <main className="mode-session mode-session-startup">
    <section className="mode-progress-surface" aria-labelledby="screener-session-heading">
      <p className="mode-session-eyebrow">Screener</p>
      <h1 id="screener-session-heading">{context.isError ? "Could not verify the Screener session"
        : checking ? "Checking Screener session" : "Screener unavailable in this session"}</h1>
      <p role={checking ? "status" : undefined}>{context.isError ? "The platform session could not be checked. Retry to verify it."
        : checking ? "Checking the platform session before loading current markets."
        : "The Screener needs a current-market session. Replay data is available in the Demo workstation."}</p>
      {context.isError && <button type="button" onClick={() => { void context.refetch(); }}>Retry session check</button>}
      <Link to="/">Return to workstation</Link>
    </section>
  </main>;
}
