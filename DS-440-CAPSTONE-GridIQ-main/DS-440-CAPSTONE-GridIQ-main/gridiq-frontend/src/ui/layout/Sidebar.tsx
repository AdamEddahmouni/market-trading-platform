import { NavLink } from "react-router-dom";
import { LayoutDashboard, MessageSquare, PlayCircle, Settings } from "lucide-react";
import { cn } from "../../lib/utils";

const nav = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/chat", label: "Chat", icon: MessageSquare },
  { to: "/playbook", label: "Playbook", icon: PlayCircle },
  { to: "/settings", label: "Settings", icon: Settings },
];

export function Sidebar() {
  return (
    <div className="sticky top-4 rounded-2xl border border-white/50 bg-stadium-concrete/95 p-4 shadow-panel backdrop-blur-sm">
      <div className="text-lg font-semibold tracking-tight text-slate-900">GridIQ</div>
      <p className="mt-0.5 text-[11px] leading-snug text-slate-500">Stadium night & turf</p>
      <div className="mt-3 space-y-1">
        {nav.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-2 rounded-xl px-3 py-2 text-sm font-medium transition-colors",
                isActive
                  ? "bg-stadium-turf/15 text-stadium-turf"
                  : "text-slate-700 hover:bg-white/60",
              )
            }
          >
            <item.icon size={18} />
            {item.label}
          </NavLink>
        ))}
      </div>
      <div className="mt-4 border-t border-white/40 pt-3 text-[11px] leading-snug text-slate-500">
        Schedules &amp; scores from{" "}
        <a href="https://github.com/nflverse" target="_blank" rel="noreferrer" className="font-medium">
          nflverse
        </a>
        .
      </div>
    </div>
  );
}
