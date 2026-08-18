import { Link } from "react-router-dom";

export type WorkspaceModuleId =
  | "overview"
  | "institutional-flow"
  | "disclosure"
  | "squeeze"
  | "order-flow"
  | "order-book"
  | "futures"
  | "catalyst"
  | "fund-etf"
  | "options"
  | "large-transactions";

type Props = {
  instrumentId: string;
  active: WorkspaceModuleId;
  squeezeQuery?: string;
};

const LINKS: { id: WorkspaceModuleId; label: string; suffix: string }[] = [
  { id: "overview", label: "Overview", suffix: "" },
  { id: "institutional-flow", label: "Institutional Flow", suffix: "/institutional-flow" },
  { id: "disclosure", label: "Disclosure", suffix: "/disclosure" },
  { id: "squeeze", label: "Short Squeeze", suffix: "/squeeze" },
  { id: "order-flow", label: "Order Flow", suffix: "/order-flow" },
  { id: "order-book", label: "Order Book", suffix: "/order-book" },
  { id: "futures", label: "Futures", suffix: "/futures" },
  { id: "catalyst", label: "Catalyst", suffix: "/catalyst" },
  { id: "fund-etf", label: "Fund / ETF", suffix: "/fund-etf" },
  { id: "options", label: "Options", suffix: "/options" },
  { id: "large-transactions", label: "Large Transactions", suffix: "/large-transactions" },
];

export function WorkspaceModuleNav({ instrumentId, active, squeezeQuery = "" }: Props) {
  return (
    <nav className="workspace-module-nav" aria-label="Workspace modules">
      {LINKS.map((link) => {
        const suffix = link.id === "squeeze" ? `${link.suffix}${squeezeQuery}` : link.suffix;
        return (
          <Link
            key={link.id}
            className={active === link.id ? "active" : undefined}
            to={`/workspace/${instrumentId}${suffix}`}
          >
            {link.label}
          </Link>
        );
      })}
    </nav>
  );
}
