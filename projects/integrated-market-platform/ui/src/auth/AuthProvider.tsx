import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { authHeaders, setSessionToken } from "./session";

export type AuthSession = {
  authenticated: boolean;
  enforcement_mode: string;
  role_enforcement_status: string;
  principal_id?: string;
  display_name?: string;
  role?: string;
  permitted_accounts?: string[];
  session_token?: string | null;
};

type AuthContextValue = {
  session: AuthSession | null;
  loading: boolean;
  sessionRequired: boolean;
  login: (principalId: string, secret: string) => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
  permitsCapability: (capability: string) => boolean;
};

const ROLE_CAPABILITIES: Record<string, string[]> = {
  VIEWER: ["state.read", "audit.read", "security.config.read"],
  OPERATOR: [
    "state.read",
    "state.write",
    "paper.order.submit",
    "paper.order.cancel",
    "audit.read",
    "security.config.read",
    "operator.lifecycle.write",
  ],
  ADMIN: [
    "state.read",
    "state.write",
    "paper.order.submit",
    "paper.order.cancel",
    "audit.read",
    "security.config.read",
    "security.config.write",
    "role.manage",
  ],
};

const AuthContext = createContext<AuthContextValue | null>(null);

async function fetchAuthStatus(): Promise<{ session_required: boolean; enforcement_mode: string }> {
  const response = await fetch("/auth/status");
  if (!response.ok) throw new Error("auth status failed");
  return response.json();
}

async function fetchAuthSession(): Promise<AuthSession> {
  const response = await fetch("/auth/session", { headers: authHeaders() });
  if (!response.ok) throw new Error("auth session failed");
  return response.json();
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<AuthSession | null>(null);
  const [loading, setLoading] = useState(true);
  const [sessionRequired, setSessionRequired] = useState(false);

  const refresh = useCallback(async () => {
    const status = await fetchAuthStatus();
    setSessionRequired(status.session_required);
    const payload = await fetchAuthSession();
    setSession(payload);
    if (payload.session_token) {
      setSessionToken(payload.session_token);
    }
  }, []);

  useEffect(() => {
    let active = true;
    void (async () => {
      try {
        await refresh();
      } catch {
        if (active) setSession(null);
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [refresh]);

  const login = useCallback(
    async (principalId: string, secret: string) => {
      const response = await fetch("/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ principal_id: principalId, secret }),
      });
      if (!response.ok) {
        throw new Error("login failed");
      }
      const payload = (await response.json()) as AuthSession;
      if (payload.session_token) {
        setSessionToken(payload.session_token);
      }
      setSession(payload);
      setSessionRequired(true);
    },
    [],
  );

  const logout = useCallback(async () => {
    await fetch("/auth/logout", {
      method: "POST",
      headers: { ...authHeaders(), "Content-Type": "application/json" },
      body: "{}",
    });
    setSessionToken(null);
    setSession(null);
    await refresh();
  }, [refresh]);

  const permitsCapability = useCallback(
    (capability: string) => {
      if (!session?.authenticated) return false;
      if (session.enforcement_mode === "LOOPBACK_TRUST") return true;
      const role = session.role ?? "VIEWER";
      return ROLE_CAPABILITIES[role]?.includes(capability) ?? false;
    },
    [session],
  );

  const value = useMemo(
    () => ({
      session,
      loading,
      sessionRequired,
      login,
      logout,
      refresh,
      permitsCapability,
    }),
    [session, loading, sessionRequired, login, logout, refresh, permitsCapability],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}

export function useOptionalAuth(): AuthContextValue | null {
  return useContext(AuthContext);
}
