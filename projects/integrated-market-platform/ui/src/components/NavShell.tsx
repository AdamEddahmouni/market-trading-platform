import { NavLink } from "react-router-dom";
import type { Mode } from "./mode-session/types";

type NavLinkDef = {
  to: string;
  label: string;
  end?: boolean;
  modeHint?: Partial<Record<Mode, string>>;
  operatorOnly?: boolean;
};

/**
 * Primary IA (UIR-01): operator mental model, not service structure.
 * Routes and labels stay in lockstep with App.tsx (FRONTEND_GUIDE rule).
 */
const primaryLinks: NavLinkDef[] = [
  {
    to: "/",
    label: "Command",
    end: true,
    modeHint: {
      DEMO: "Replay desk",
      PAPER: "Decision desk",
      LIVE: "Observation desk",
    },
  },
  {
    to: "/radar",
    label: "Radar",
    modeHint: {
      DEMO: "Replay discovery",
      PAPER: "Candidate discovery",
      LIVE: "Live monitor",
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
    to: "/portfolio",
    label: "Portfolio",
    modeHint: {
      DEMO: "Read-only",
      PAPER: "Orders history",
      LIVE: "Broker-observed",
    },
  },
  {
    to: "/research",
    label: "Research",
    modeHint: {
      DEMO: "Replay-bound evidence",
      PAPER: "Evidence & validation",
      LIVE: "Read-only evidence",
    },
  },
  {
    to: "/control",
    label: "Control",
    modeHint: {
      DEMO: "Platform operations",
      PAPER: "Platform operations",
      LIVE: "Platform operations",
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
};

function accessibleLabel(link: NavLinkDef, mode?: Mode): string | undefined {
  if (!mode || !link.modeHint?.[mode]) return undefined;
  return `${link.label} — ${link.modeHint[mode]}`;
}

function NavItem({ link, mode }: { link: NavLinkDef; mode?: Mode }) {
  const ariaLabel = accessibleLabel(link, mode);
  return (
    <NavLink
      to={link.to}
      className={({ isActive }) => {
        const classes = ["nav-link"];
        if (isActive) classes.push("active");
        if (link.operatorOnly) classes.push("nav-link-operator");
        return classes.join(" ");
      }}
      end={link.end ?? false}
      aria-label={ariaLabel}
    >
      {link.label}
      {mode && link.modeHint?.[mode] ? (
        <span className="nav-mode-hint">{link.modeHint[mode]}</span>
      ) : null}
    </NavLink>
  );
}

export function NavShell({ mode }: Props) {
  return (
    <nav className="nav-shell nav-shell-sidebar" aria-label="Primary">
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
