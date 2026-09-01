import { useState } from "react";
import { useAuth } from "./AuthProvider";

export function OperatorLoginGate({ children }: { children: React.ReactNode }) {
  const { session, loading, sessionRequired, login } = useAuth();
  const [principalId, setPrincipalId] = useState("");
  const [secret, setSecret] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (loading) {
    return (
      <main className="mode-session mode-session-startup">
        <section className="mode-progress-surface">
          <p className="mode-session-eyebrow">Operator authentication</p>
          <h1>Checking session</h1>
        </section>
      </main>
    );
  }

  if (!sessionRequired || session?.authenticated) {
    return <>{children}</>;
  }

  const onSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await login(principalId.trim(), secret);
    } catch {
      setError("Sign-in failed. Check principal id and secret.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="mode-session mode-session-startup">
      <section className="mode-progress-surface" aria-labelledby="operator-login-heading">
        <p className="mode-session-eyebrow">Operator authentication</p>
        <h1 id="operator-login-heading">Sign in to continue</h1>
        <p>Multi-user authorization is enforced. Use a configured principal from the operator registry.</p>
        <form onSubmit={onSubmit}>
          <label>
            Principal id
            <input
              name="principal_id"
              value={principalId}
              onChange={(event) => setPrincipalId(event.target.value)}
              autoComplete="username"
              required
            />
          </label>
          <label>
            Secret
            <input
              name="secret"
              type="password"
              value={secret}
              onChange={(event) => setSecret(event.target.value)}
              autoComplete="current-password"
              required
            />
          </label>
          {error ? (
            <p role="alert" className="startup-recovery-banner">
              {error}
            </p>
          ) : null}
          <button type="submit" disabled={submitting}>
            {submitting ? "Signing in…" : "Sign in"}
          </button>
        </form>
      </section>
    </main>
  );
}
