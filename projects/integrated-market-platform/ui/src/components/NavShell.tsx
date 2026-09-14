import { NavLink } from "react-router-dom";
import type { Mode } from "./mode-session/types";

type NavLinkDef = {
  to: string;
  label: string;
  gated?: boolean;
  emphasis?: "radar";
  modeHint?: Partial<Record<Mode, string>>;
  operatorOnly?: boolean;
};

const primaryLinks: NavLinkDef[] = [
  { to: "/", label: "Overview" },
  {
    to: "/explore",
    label: "Markets",
    modeHint: {
      DEMO: "Frozen bridges",
      PAPER: "Candidate discovery",
      LIVE: "Live scanner",
    },
  },
  {
    to: "/discover",
    label: "Opportunity Radar",
    emphasis: "radar",
    modeHint: {
      DEMO: "Observational queue",
      PAPER: "Discovery desk",
      LIVE: "Read-only monitor",
    },
  },
  {
    to: "/signals",
    label: "Signals",
    modeHint: {
      DEMO: "Replay attention",
      PAPER: "Attention queue",
      LIVE: "Live attention",
    },
  },
  {
    to: "/research",
    label: "Research",
    gated: true,
    modeHint: {
      DEMO: "Replay-bound labs",
      PAPER: "Research & model labs",
      LIVE: "Read-only labs",
    },
  },
  {
    to: "/portfolio",
    label: "Portfolio",
    modeHint: {
      DEMO: "Read-only",
      PAPER: "Orders history",
      LIVE: "Broker-observed",
    },
  },
  {
    to: "/workspace",
    label: "Workspace",
    modeHint: {
      DEMO: "Read-only desk",
      PAPER: "Decision desk",
      LIVE: "Observational desk",
    },
  },
  {
    to: "/control",
    label: "Risk",
    modeHint: {
      DEMO: "Operator controls",
      PAPER: "Operator controls",
      LIVE: "Operator controls",
    },
  },
];

const operatorLinks: NavLinkDef[] = [
  {
    to: "/live-canary",
    label: "Live Canary",
    operatorOnly: true,
    modeHint: {
      LIVE: "Safety review",
    },
  },
  { to: "/settings", label: "Settings", operatorOnly: true },
  { to: "/diagnostics/provider", label: "Diagnostics", operatorOnly: true },
];

type Props = {
  mode?: Mode;
  layout?: "horizontal" | "sidebar";
};

function accessibleLabel(link: NavLinkDef, mode?: Mode): string | undefined {
  if (!mode || !link.modeHint?.[mode]) return undefined;
  return `${link.label} — ${link.modeHint[mode]}`;
}

function NavItem({ link, mode }: { link: NavLinkDef; mode?: Mode }) {
  const ariaLabel = accessibleLabel(link, mode);
  const isOverview = link.to === "/" && link.label === "Overview";
  return (
    <NavLink
      to={link.to}
      className={({ isActive }) => {
        const classes = ["nav-link"];
        if (isActive) classes.push("active");
        if (link.emphasis === "radar") classes.push("nav-link-radar");
        if (link.operatorOnly) classes.push("nav-link-operator");
        return classes.join(" ");
      }}
      end={isOverview}
      aria-label={ariaLabel}
    >
      {link.label}
      {link.gated ? <span className="gated-badge">GATED</span> : null}
      {mode && link.modeHint?.[mode] ? (
        <span className="nav-mode-hint">{link.modeHint[mode]}</span>
      ) : null}
    </NavLink>
  );
}

export function NavShell({ mode, layout = "sidebar" }: Props) {
  const navClass = layout === "sidebar" ? "nav-shell nav-shell-sidebar" : "nav-shell";
  return (
    <nav className={navClass} aria-label="Primary">
      <div className="nav-primary-group">
        {primaryLinks.map((link) => (
          <NavItem key={`${link.to}-${link.label}`} link={link} mode={mode} />
        ))}
      </div>
      <div className="nav-operator-group" aria-label="Operator">
        {operatorLinks.map((link) => (
          <NavItem key={link.to} link={link} mode={mode} />
        ))}
      </div>
    </nav>
  );
}
