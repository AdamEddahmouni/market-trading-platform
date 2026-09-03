import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../stores/auth";
import { Button } from "../ui/primitives/Button";
import { Input } from "../ui/primitives/Input";
import { Card } from "../ui/primitives/Card";

export default function Register() {
  const { register, isLoading } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);

  return (
    <div className="mx-auto max-w-md">
      <Card className="mt-10">
        <div className="text-xl font-semibold">Create account</div>
        <div className="mt-1 text-sm text-gray-600">
          Password must be at least 8 characters (same rule as the API).
        </div>

        <div className="mt-4 space-y-3">
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
              autoComplete="new-password"
            />
          </div>
          <div>
            <div className="mb-1 text-xs font-medium text-gray-700">Confirm password</div>
            <Input
              type="password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              autoComplete="new-password"
            />
          </div>

          {error && <div className="rounded-xl bg-red-50 p-3 text-sm text-red-700">{error}</div>}

          <Button
            disabled={isLoading}
            onClick={async () => {
              setError(null);
              if (!email.trim() || !password) {
                setError("Email and password are required.");
                return;
              }
              if (password.length < 8) {
                setError("Password must be at least 8 characters.");
                return;
              }
              if (password !== confirm) {
                setError("Passwords do not match.");
                return;
              }
              try {
                await register(email.trim(), password);
                navigate("/dashboard", { replace: true });
              } catch (e: unknown) {
                setError(e instanceof Error ? e.message : "Registration failed");
              }
            }}
          >
            {isLoading ? "Creating account…" : "Create account"}
          </Button>

          <div className="pt-1 text-center text-sm text-gray-600">
            Already have an account?{" "}
            <Link to="/login" className="font-medium text-gray-900 underline underline-offset-2">
              Sign in
            </Link>
          </div>
        </div>
      </Card>
    </div>
  );
}
