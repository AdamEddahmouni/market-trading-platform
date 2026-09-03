import { useNavigate } from "react-router-dom";
import { useAuth } from "../../stores/auth";
import { Button } from "../primitives/Button";

export function Topbar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  return (
    <div className="flex items-center justify-between rounded-2xl border border-white/50 bg-stadium-concrete/95 px-4 py-3 shadow-panel backdrop-blur-sm">
      <div className="min-w-0 text-sm text-slate-600">
        {user ? (
          <>
            Signed in as{" "}
            <span className="font-medium break-all text-slate-900" title={user.email}>
              {user.email}
            </span>
            <span className="ml-2 hidden text-xs text-slate-500 sm:inline">({user.role})</span>
          </>
        ) : (
          "Not signed in"
        )}
      </div>
      <div className="flex items-center gap-2">
        {user && (
          <Button
            variant="ghost"
            onClick={() => {
              logout();
              navigate("/login", { replace: true });
            }}
          >
            Log out
          </Button>
        )}
      </div>
    </div>
  );
}
