import { BarChart3, Camera, LayoutDashboard, ListChecks, ShieldCheck } from "lucide-react";
import { NavLink } from "react-router-dom";

const links = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard },
  { to: "/cameras", label: "Cameras", icon: Camera },
  { to: "/events", label: "Events", icon: ListChecks },
  { to: "/analytics", label: "Analytics", icon: BarChart3 },
];

export default function Sidebar() {
  return (
    <aside className="sticky top-0 flex h-screen w-62 shrink-0 flex-col gap-7 border-r border-line bg-gradient-to-b from-panel/90 to-bg/90 px-4 py-6
      max-md:static max-md:h-auto max-md:w-full max-md:flex-row max-md:items-center max-md:gap-3 max-md:overflow-x-auto max-md:p-3">
      <div className="flex items-center gap-3 px-2">
        <div className="grid size-10 place-items-center rounded-xl bg-gradient-to-br from-brand to-sky2 text-white shadow-lg shadow-brand/45">
          <ShieldCheck size={22} />
        </div>
        <div>
          <div className="text-[17px] font-bold tracking-wide">AegisVision</div>
          <div className="text-xs text-mute max-md:hidden">Video analytics</div>
        </div>
      </div>
      <nav className="flex flex-col gap-1 max-md:flex-row">
        {links.map(({ to, label, icon: Icon }) => (
          <NavLink key={to} to={to} end={to === "/"}
            className={({ isActive }) =>
              `flex items-center gap-3 rounded-xl px-3.5 py-[11px] font-medium transition ${
                isActive
                  ? "bg-gradient-to-r from-brand/30 to-sky2/10 text-white shadow-[inset_3px_0_0_var(--color-brand)]"
                  : "text-mute hover:bg-brand/10 hover:text-ink"}`}>
            <Icon size={18} />
            {label}
          </NavLink>
        ))}
      </nav>
      <div className="mt-auto px-2 text-xs text-mute max-md:hidden">Week 6 · v0.1</div>
    </aside>
  );
}
