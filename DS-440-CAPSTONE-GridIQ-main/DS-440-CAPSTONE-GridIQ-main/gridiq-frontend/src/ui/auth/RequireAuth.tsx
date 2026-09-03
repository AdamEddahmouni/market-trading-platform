import { useAuth } from "../../stores/auth";
import type { PropsWithChildren } from "react";
import { Navigate } from "react-router-dom";

export function RequireAuth({ children }: PropsWithChildren) {
  const { user, isLoading } = useAuth();
  if (isLoading) return <div className="text-sm text-gray-600">Loading…</div>;
  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
}
