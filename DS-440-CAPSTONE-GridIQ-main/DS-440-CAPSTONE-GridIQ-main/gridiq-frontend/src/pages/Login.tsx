import axios from "axios";
import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../stores/auth";
import { Button } from "../ui/primitives/Button";
import { Input } from "../ui/primitives/Input";
import { Card } from "../ui/primitives/Card";

export default function Login() {
  const { login, isLoading } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const notice = (location.state as { notice?: string } | null)?.notice;
  const [email, setEmail] = useState("coach@gridiq.dev");
  const [password, setPassword] = useState("password");
  const [error, setError] = useState<string | null>(null);

  return (
    <div className="mx-auto max-w-md">
      <Card className="mt-10">
        <div className="text-xl font-semibold">Sign in</div>
        <div className="mt-1 text-sm text-gray-600">
          Sign in with your backend account, or use Settings → local mocks for offline dev.
        </div>

        <div className="mt-4 space-y-3">
          {notice ? (
            <div className="rounded-xl bg-sky-50 p-3 text-sm text-sky-900">{notice}</div>
          ) : null}
          <div>
            <div className="mb-1 text-xs font-medium text-gray-700">Email</div>
            <Input value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" />
          </div>
          <div>
            <div className="mb-1 text-xs font-medium text-gray-700">Password</div>
            <Input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
            />
          </div>

          {error && <div className="rounded-xl bg-red-50 p-3 text-sm text-red-700">{error}</div>}

          <Button
            disabled={isLoading}
            onClick={async () => {
              setError(null);
              try {
                await login(email, password);
                navigate("/dashboard", { replace: true });
              } catch (e: unknown) {
                if (axios.isAxiosError(e) && e.response?.data) {
                  const detail = (e.response.data as { detail?: unknown }).detail;
                  if (typeof detail === "string") {
                    setError(detail);
                    return;
                  }
                }
                setError(e instanceof Error ? e.message : "Login failed");
              }
            }}
          >
            {isLoading ? "Signing in…" : "Sign in"}
          </Button>

          <div className="pt-1 text-center text-sm text-gray-600">
            No account?{" "}
            <Link to="/register" className="font-medium text-gray-900 underline underline-offset-2">
              Create one
            </Link>
          </div>
        </div>
      </Card>
    </div>
  );
}
