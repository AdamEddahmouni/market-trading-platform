import { useCallback, useEffect, useState } from "react";
import { api } from "../api/endpoints";
import type { LifecycleAction } from "../api/schemas";
import { PageHeader } from "./shared/PageHeader";

type Readiness = Awaited<ReturnType<typeof api.getOperatorReadiness>>;
type Lifecycle = Awaited<ReturnType<typeof api.getOperatorLifecycleStatus>>;
type Config = Awaited<ReturnType<typeof api.getOperatorConfig>>;
type ControlState = "loading" | "ready" | "error";

function statusClass(status: string): string {
  return `operator-status operator-status-${status.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
}

export function OperatorControlCenterPage() {
  const [readiness, setReadiness] = useState<Readiness | null>(null);
  const [lifecycle, setLifecycle] = useState<Lifecycle | null>(null);
  const [config, setConfig] = useState<Config | null>(null);
  const [state, setState] = useState<ControlState>("loading");
  const [message, setMessage] = useState<string | null>(null);
  const [busyProvider, setBusyProvider] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setState("loading");
    try {
      const [nextReadiness, nextLifecycle] = await Promise.all([
        api.getOperatorReadiness(),
        api.getOperatorLifecycleStatus(),
      ]);
      const nextConfig = await api.getOperatorConfig();
      setReadiness(nextReadiness);
      setLifecycle(nextLifecycle);
      setConfig(nextConfig);
      setState("ready");
    } catch {
      setState("error");
      setMessage("The control center could not read local platform status.");
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function refreshProvider(provider: string, label: string) {
    setBusyProvider(provider);
    setMessage(null);
    try {
      await api.refreshOperatorProvider(provider);
      setMessage(`Refresh queued for ${label}.`);
      await refresh();
    } catch {
      setMessage(`Refresh could not be queued for ${label}.`);
    } finally {
      setBusyProvider(null);
    }
  }

  const title = state === "loading" ? "Operator center" : "Operator center";
  return (
    <section className="page operator-control-center">
      <PageHeader
        eyebrow="Local platform control"
        title={title}
        subtitle="Set up the workstation, keep providers healthy, and recover quickly when something changes."
        actions={
          <button type="button" onClick={() => void refresh()} disabled={state === "loading"}>
            {state === "loading" ? "Checking…" : "Check again"}
          </button>
        }
      />

      {message ? (
        <p className="operator-control-message" role="status">
          {message}
        </p>
      ) : null}
      {state === "error" ? (
        <section className="operator-panel operator-panel-alert" role="alert">
          <h2>Platform status unavailable</h2>
          <p>Start the local platform, then check again.</p>
        </section>
      ) : null}

      <div className="operator-control-grid">
        <section className="operator-panel operator-hero-panel">
          <div className="operator-panel-kicker">At a glance</div>
          <div className="operator-hero-row">
            <div>
              <p className="operator-big-status">{lifecycle?.status ?? "CHECKING"}</p>
              <p className="operator-muted">Local lifecycle status</p>
            </div>
            <div className={statusClass(readiness?.status ?? "CHECKING")}>
              {readiness?.status ?? "CHECKING"}
            </div>
          </div>
          <div className="operator-actions" aria-label="Platform actions">
            <button type="button" onClick={() => void runLifecycleAction("restart")}>
              Restart platform
            </button>
            <button type="button" onClick={() => void runLifecycleAction("check_update")}>
              Check for updates
            </button>
            <button
              type="button"
              onClick={() => {
                if (window.confirm("Apply the available fast-forward update and restart the local platform?")) {
                  void runLifecycleAction("apply_update");
                }
              }}
              disabled={lifecycle?.update?.status !== "AVAILABLE"}
              title={lifecycle?.update?.detail ?? "A fast-forward update must be available."}
            >
              Apply fast-forward update
            </button>
          </div>
          {lifecycle?.update ? <p className="operator-muted">Updates: {lifecycle.update.detail ?? lifecycle.update.status}</p> : null}
          <nav className="operator-related-links" aria-label="Related operator pages">
            <a href="/settings">Settings</a>
            <a href="/diagnostics/provider">Provider diagnostics</a>
          </nav>
          <p className="operator-muted">
            Live execution remains locked. Lifecycle controls only manage this local workstation.
          </p>
        </section>

        <section className="operator-panel">
          <div className="operator-panel-heading">
            <div>
              <div className="operator-panel-kicker">Project setup</div>
              <h2>Ready to work</h2>
            </div>
            <span className={statusClass(readiness?.status ?? "CHECKING")}>
              {readiness?.status ?? "CHECKING"}
            </span>
          </div>
          <div className="operator-check-list">
            {(readiness?.checks ?? []).map((check) => (
              <div className="operator-check" key={check.id}>
                <span className={statusClass(check.status)} aria-label={check.status}>
                  {check.status === "PASS" ? "✓" : "!"}
                </span>
                <div>
                  <strong>{check.label}</strong>
                  <p>{check.detail}</p>
                  {check.next_action ? <small>{check.next_action}</small> : null}
                </div>
              </div>
            ))}
          </div>
        </section>
      </div>

      <section className="operator-panel">
        <div className="operator-panel-heading">
          <div>
            <div className="operator-panel-kicker">Data connections</div>
            <h2>Provider readiness</h2>
          </div>
          <span className="operator-muted">Each provider reports independently</span>
        </div>
        <div className="operator-provider-grid">
          {(readiness?.providers ?? []).map((provider) => (
            <article className="operator-provider-card" key={provider.provider}>
              <div className="operator-provider-heading">
                <div>
                  <h3>{provider.label ?? provider.provider}</h3>
                  <p>{provider.provider}</p>
                </div>
                <span className={statusClass(provider.transport_state)}>{provider.transport_state}</span>
              </div>
              <dl className="operator-provider-metrics">
                <div>
                  <dt>Credentials</dt>
                  <dd>{provider.credential_state}</dd>
                </div>
                <div>
                  <dt>Gate</dt>
                  <dd>{provider.gate_state}</dd>
                </div>
                <div>
                  <dt>Freshness</dt>
                  <dd>{provider.freshness ?? provider.last_updated ?? "—"}</dd>
                </div>
              </dl>
              <p className="operator-next-action">Next: {provider.next_action}</p>
              <button
                type="button"
                onClick={() => void refreshProvider(provider.provider, provider.label ?? provider.provider)}
                disabled={busyProvider === provider.provider}
                aria-label={`Refresh ${provider.label ?? provider.provider}`}
              >
                {busyProvider === provider.provider ? "Queueing…" : `Refresh ${provider.label ?? provider.provider}`}
              </button>
            </article>
          ))}
          {!readiness?.providers?.length ? (
            <p className="operator-muted">No provider readiness rows are available yet.</p>
          ) : null}
        </div>
      </section>

      <section className="operator-panel">
        <div className="operator-panel-heading">
          <div>
            <div className="operator-panel-kicker">Local configuration</div>
            <h2>Provider credentials</h2>
          </div>
          <span className="operator-muted">Values stay on this workstation</span>
        </div>
        <div className="operator-config-grid">
          {(config?.providers ?? []).map((provider) => (
            <ProviderConfigCard key={provider.provider} provider={provider} onSaved={setConfig} />
          ))}
          {!config?.providers?.length ? (
            <p className="operator-muted">No editable provider configuration is available yet.</p>
          ) : null}
        </div>
      </section>
    </section>
  );

  async function runLifecycleAction(action: LifecycleAction) {
    setMessage(null);
    try {
      await api.runOperatorLifecycleAction(action);
      setMessage(`${action.replace("_", " ")} queued.`);
      await refresh();
    } catch {
      setMessage(`Could not queue ${action.replace("_", " ")}. Start the local platform first.`);
    }
  }
}

function ProviderConfigCard({
  provider,
  onSaved,
}: {
  provider: Config["providers"][number];
  onSaved: (config: Config) => void;
}) {
  const [values, setValues] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function save() {
    setSaving(true);
    setMessage(null);
    try {
      const next = await api.saveOperatorProviderConfig(provider.provider, values);
      onSaved(next);
      setValues({});
      setMessage("Saved. Restart the API if the provider is already running.");
    } catch {
      setMessage("Configuration was not saved. Check the fields and operator permissions.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <article className="operator-config-card">
      <div className="operator-provider-heading">
        <div>
          <h3>{provider.label}</h3>
          <p>{provider.provider}</p>
        </div>
      </div>
      {provider.fields.map((field) => (
        <label className="operator-config-field" key={field.key}>
          <span>{field.label}</span>
          <input
            type={field.sensitive ? "password" : "text"}
            value={values[field.key] ?? ""}
            placeholder={field.configured ? "Configured — leave blank to keep" : "Not configured"}
            autoComplete="off"
            onChange={(event) => setValues((current) => ({ ...current, [field.key]: event.target.value }))}
          />
          <small>{field.configured ? "A value is stored locally." : "No value is stored."}</small>
        </label>
      ))}
      <button type="button" onClick={() => void save()} disabled={saving}>
        {saving ? "Saving…" : `Save ${provider.label}`}
      </button>
      {message ? <p className="operator-config-message" role="status">{message}</p> : null}
    </article>
  );
}
