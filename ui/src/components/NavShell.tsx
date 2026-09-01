import { NavLink } from "react-router-dom";
import type { Mode } from "./mode-session/types";

type NavLinkDef = {
  to: string;
  label: string;
  gated?: boolean;
  modeHint?: Partial<Record<Mode, string>>;
};

const links: NavLinkDef[] = [
  { to: "/", label: "NOW" },
  {
    to: "/explore",
    label: "EXPLORE",
    modeHint: {
      DEMO: "Frozen bridges",
      PAPER: "Candidate discovery",
      LIVE: "Live scanner",
    },
  },
  {
    to: "/discover",
    label: "DISCOVER",
    modeHint: {
      DEMO: "Observational queue",
      PAPER: "Discovery desk",
      LIVE: "Read-only monitor",
    },
  },
  {
    to: "/workspace",
    label: "WORKSPACE",
    modeHint: {
      DEMO: "Read-only",
      PAPER: "Simulation",
      LIVE: "Observational",
    },
  },
  {
    to: "/research",
    label: "RESEARCH",
    gated: true,
    modeHint: {
      DEMO: "Replay-bound",
      PAPER: "Research to sim",
      LIVE: "Read-only",
    },
  },
  {
    to: "/portfolio",
    label: "PORTFOLIO",
    modeHint: {
      DEMO: "Read-only",
      PAPER: "Simulation",
      LIVE: "Broker-observed",
    },
  },
  {
    to: "/live-canary",
    label: "LIVE CANARY",
    modeHint: {
      LIVE: "Safety review",
    },
  },
  { to: "/settings", label: "SETTINGS" },
  { to: "/diagnostics/provider", label: "DIAGNOSTICS" },
];

type Props = {
  mode?: Mode;
};

function accessibleLabel(link: NavLinkDef, mode?: Mode): string | undefined {
  if (!mode || !link.modeHint?.[mode]) return undefined;
  return `${link.label} — ${link.modeHint[mode]}`;
}

export function NavShell({ mode }: Props) {
  return (
    <nav className="nav-shell" aria-label="Primary">
      {links.map((link) => {
        const ariaLabel = accessibleLabel(link, mode);
        return (
          <NavLink
            key={link.to}
            to={link.to}
            className={({ isActive }) => (isActive ? "nav-link active" : "nav-link")}
            end={link.to === "/"}
            aria-label={ariaLabel}
          >
            {link.label}
            {link.gated ? <span className="gated-badge">GATED</span> : null}
            {mode && link.modeHint?.[mode] ? (
              <span className="nav-mode-hint">{link.modeHint[mode]}</span>
            ) : null}
          </NavLink>
        );
      })}
    </nav>
  );
}
