import { Card } from "../ui/primitives/Card";
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../stores/auth";
import { MOCK_AUTH_TOKEN } from "../lib/api/endpoints";

export default function Settings() {
  const navigate = useNavigate();
  const logout = useAuth((s) => s.logout);
  const [useMocks, setUseMocks] = useState(() => localStorage.getItem("gridiq_use_mocks") === "true");
  const [apiBase, setApiBase] = useState(() => localStorage.getItem("gridiq_api_base") || "");
  const mocksPrev = useRef(useMocks);

  useEffect(() => {
    localStorage.setItem("gridiq_use_mocks", useMocks ? "true" : "false");
    if (mocksPrev.current && !useMocks) {
      const t = localStorage.getItem("gridiq_token");
      if (t === MOCK_AUTH_TOKEN) {
        logout();
        navigate("/login", {
          replace: true,
          state: { notice: "Mock mode is off. Sign in again with your real backend account." },
        });
      }
    }
    mocksPrev.current = useMocks;
  }, [useMocks, logout, navigate]);

  useEffect(() => {
    void import("../lib/api/client").then((mod) => mod.setApiBaseUrl(apiBase));
  }, [apiBase]);

  return (
    <div className="space-y-4">
      <div>
        <div className="text-2xl font-semibold">Settings</div>
        <div className="mt-1 text-sm text-gray-600">
          Role gates, profile, preferences, model/provider config, etc.
        </div>
      </div>

      <Card className="space-y-4">
        <div className="space-y-2">
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={useMocks}
              onChange={(e) => setUseMocks(e.target.checked)}
            />
            <span className="text-sm">Use local mocks (no backend)</span>
          </label>
          <div className="text-sm text-gray-600">
            If you signed in while mocks were on, turning mock mode off will ask you to sign in again (mock uses a
            placeholder token, not a real JWT).
          </div>
        </div>

        <div className="space-y-1">
          <label className="text-sm font-medium">API base URL</label>
          <input
            className="w-full rounded border-gray-300 p-2"
            value={apiBase}
            placeholder="http://localhost:8000"
            onChange={(e) => setApiBase(e.target.value)}
          />
          <div className="text-xs text-gray-500">
            Override the base URL that the frontend hits (persists to localStorage).
          </div>
        </div>
      </Card>
    </div>
  );
}
