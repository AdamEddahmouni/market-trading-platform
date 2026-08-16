import { NavLink } from "react-router-dom";

const links = [
  { to: "/", label: "NOW" },
  { to: "/explore", label: "EXPLORE" },
  { to: "/workspace", label: "WORKSPACE" },
  { to: "/research", label: "RESEARCH", gated: true },
  { to: "/portfolio", label: "PORTFOLIO", gated: true },
];

export function NavShell() {
  return (
    <nav className="nav-shell" aria-label="Primary">
      {links.map((link) => (
        <NavLink
          key={link.to}
          to={link.to}
          className={({ isActive }) => (isActive ? "nav-link active" : "nav-link")}
          end={link.to === "/"}
        >
          {link.label}
          {link.gated ? <span className="gated-badge">GATED</span> : null}
        </NavLink>
      ))}
    </nav>
  );
}
