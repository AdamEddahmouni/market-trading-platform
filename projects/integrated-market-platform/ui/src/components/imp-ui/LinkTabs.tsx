import { NavLink } from "react-router-dom";

export type LinkTabItem = {
  to: string;
  label: string;
  /** Exact match (NavLink `end`). */
  end?: boolean;
};

type Props = {
  label: string;
  items: LinkTabItem[];
  className?: string;
};

/**
 * Routable tab strip: real links with `aria-current="page"` on the active
 * tab. Used for section tabs that are routes (Radar Opportunities/Screeners,
 * Command Overview/Signals). Keyboard-accessible by construction.
 */
export function LinkTabs({ label, items, className }: Props) {
  const classes = ["imp-ui-link-tabs", className].filter(Boolean).join(" ");
  return (
    <nav className={classes} aria-label={label} data-testid="imp-ui-link-tabs">
      {items.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.end}
          className={({ isActive }) =>
            isActive ? "imp-ui-link-tab imp-ui-link-tab--active" : "imp-ui-link-tab"
          }
        >
          {item.label}
        </NavLink>
      ))}
    </nav>
  );
}
