import { Outlet, useLocation, useNavigate } from "react-router-dom";
import { useEffect } from "react";
import { useAuth } from "../../stores/auth";
import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";

export function AppLayout() {
  const { hydrate } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();

  useEffect(() => {
    hydrate();
  }, [hydrate]);

  // If not logged in, allow /login; otherwise keep user in app
  useEffect(() => {
    const token = localStorage.getItem("gridiq_token");
    const publicPaths = ["/login", "/register"];
    if (!token && !publicPaths.includes(location.pathname)) {
      navigate("/login", { replace: true });
    }
  }, [location.pathname, navigate]);

  return (
    <div className="min-h-screen w-full max-w-none text-slate-900">
      <div className="grid w-full max-w-none grid-cols-12 gap-3 px-2 py-3 sm:gap-4 sm:px-4">
        <aside className="col-span-12 md:col-span-3 lg:col-span-2">
          <Sidebar />
        </aside>
        <main className="col-span-12 min-w-0 md:col-span-9 lg:col-span-10">
          <Topbar />
          <div className="mt-4 w-full max-w-none rounded-2xl border border-white/40 bg-stadium-concrete/90 p-3 shadow-panel backdrop-blur-md sm:p-4">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
