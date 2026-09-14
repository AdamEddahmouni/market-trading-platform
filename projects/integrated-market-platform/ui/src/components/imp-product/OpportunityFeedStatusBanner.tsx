import { Link } from "react-router-dom";

type Props = {
  state: "loading" | "ready" | "error";
  feedStatus?: string;
  unreadyReason?: string;
  nextAction?: string;
};

function controlHref(nextAction?: string): string {
  if (!nextAction) return "/control";
  if (nextAction.startsWith("/")) return nextAction;
  return "/control";
}

export function OpportunityFeedStatusBanner({
  state,
  feedStatus,
  unreadyReason,
  nextAction,
}: Props) {
  if (state === "loading") {
    return (
      <p className="imp-opportunity-feed-banner" role="status">
        Loading ranked opportunities…
      </p>
    );
  }
  if (state === "error") {
    return (
      <p className="imp-opportunity-feed-banner imp-opportunity-feed-banner-alert" role="alert">
        Opportunity ranking unavailable.
      </p>
    );
  }
  if (state === "ready" && feedStatus === "UNREADY") {
    return (
      <p className="imp-opportunity-feed-banner" role="status">
        Radar unready{unreadyReason ? ` (${unreadyReason})` : ""}.{" "}
        <Link to={controlHref(nextAction)}>Open Control Center</Link>
      </p>
    );
  }
  return null;
}
