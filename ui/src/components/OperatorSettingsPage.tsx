import { useEffect, useState } from "react";
import type { Mode } from "./mode-session/types";
import {
  canMutateOperatorSettings,
  operatorSettingsRestrictionNote,
} from "./operator-settings/operatorSettingsMode";
import { JsonDetailPanel } from "./shared/JsonDetailPanel";
import { PageHeader } from "./shared/PageHeader";

type OperatorState = {
  persistence_enabled?: boolean;
  state_dir?: string;
  schema_version?: number;
  safety?: Record<string, unknown>;
  watchlists?: Array<{ watchlist_id: string; name: string; items?: Array<{ instrument_id: string }> }>;
  recent_instruments?: Array<{ instrument_id: string }>;
  sessions?: Array<{ session_id: string; status: string; created_at: number }>;
  captures?: Array<{ capture_id: string; status: string; provider?: string }>;
  workspace?: { layout?: Record<string, unknown>; fallback?: boolean } | null;
  preferences?: Record<string, unknown>;
};

type StartupState = {
  opend?: { status?: string; ready_for_live_observational?: boolean; operator_message?: string };
  restore?: string;
  crash_recovery?: string;
  execution_deferred?: boolean;
  previous_session?: { session_id?: string; status?: string } | null;
  safety?: Record<string, unknown>;
};

type Props = {
  mode: Mode;
};

export function OperatorSettingsPage({ mode }: Props) {
  const [startup, setStartup] = useState<StartupState | null>(null);
  const [state, setState] = useState<OperatorState | null>(null);
  const [watchInput, setWatchInput] = useState("AAPL");
  const [error, setError] = useState<string | null>(null);
  const mutationsEnabled = canMutateOperatorSettings(mode);
  const restrictionNote = operatorSettingsRestrictionNote(mode);

  async function refresh() {
    const [boot, operator] = await Promise.all([
      fetch("/state/startup").then((response) => response.json()),
      fetch("/operator/state").then((response) => response.json()),
    ]);
    setStartup(boot);
    setState(operator);
  }

  useEffect(() => {
    void refresh().catch((err: unknown) => setError(String(err)));
  }, []);

  async function addWatch() {
    if (!mutationsEnabled) return;
    const current = state?.watchlists?.[0];
    const existing = (current?.items ?? []).map((item) => item.instrument_id);
    const response = await fetch("/operator/watchlist", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        watchlist_id: current?.watchlist_id,
        instrument_ids: [...new Set([...existing, watchInput.toUpperCase()])],
      }),
    });
    if (!response.ok) {
      setError("Watchlist update failed");
      return;
    }
    await refresh();
  }

  return (
    <section className="page settings-page">
      <PageHeader title="Settings" eyebrow="Operator" subtitle="Persistence, provider readiness, watchlists, and replay controls." />
      {restrictionNote ? (
        <aside className="panel mode-restriction-note" role="note">
          <strong>Operator settings are read-only in {mode} mode.</strong>
          <p>{restrictionNote}</p>
        </aside>
      ) : null}
      {error ? <p className="order-ticket-error">{error}</p> : null}

      <section className="panel">
        <h2>Provider</h2>
        {startup?.opend?.operator_message ? (
          <p>{startup.opend.operator_message}</p>
        ) : (
          <dl className="metric-list">
            <div>
              <dt>OpenD status</dt>
              <dd>{startup?.opend?.status ?? "—"}</dd>
            </div>
            <div>
              <dt>Ready for live observational</dt>
              <dd>{startup?.opend?.ready_for_live_observational ? "Yes" : "No"}</dd>
            </div>
          </dl>
        )}
        {startup?.opend ? <JsonDetailPanel title="OpenD technical details" value={startup.opend} /> : null}
      </section>

      <section className="panel">
        <h2>State</h2>
        <dl className="metric-list">
          <div>
            <dt>Persistence</dt>
            <dd>{state?.persistence_enabled ? "ON" : "OFF"}</dd>
          </div>
          <div>
            <dt>State dir</dt>
            <dd>{state?.state_dir ?? "—"}</dd>
          </div>
          <div>
            <dt>Schema</dt>
            <dd>{state?.schema_version ?? "—"}</dd>
          </div>
          <div>
            <dt>Restore</dt>
            <dd>
              {startup?.restore ?? "—"} · {startup?.crash_recovery ?? "NONE"}
            </dd>
          </div>
          <div>
            <dt>Execution deferred</dt>
            <dd>{startup?.execution_deferred ? "YES" : "NO"}</dd>
          </div>
        </dl>
      </section>

      <section className="panel">
        <h2>Paper</h2>
        <ul>
          {(state?.sessions ?? []).map((session) => (
            <li key={session.session_id}>
              {session.status} · {session.session_id.slice(0, 12)}…
            </li>
          ))}
        </ul>
      </section>

      <section className="panel">
        <h2>Storage</h2>
        <p>Captures remain file-backed. Catalog statuses:</p>
        {mutationsEnabled ? (
          <div className="live-actions">
            <button
              type="button"
              onClick={() => {
                void fetch("/captures")
                  .then((response) => response.json())
                  .then(() => refresh());
              }}
            >
              Reindex captures
            </button>
          </div>
        ) : null}
        <ul>
          {(state?.captures ?? []).slice(0, 12).map((capture) => (
            <li key={capture.capture_id}>
              {capture.capture_id} · {capture.status} · {capture.provider}{" "}
              {mutationsEnabled && capture.status === "AVAILABLE" ? (
                <button
                  type="button"
                  onClick={() => {
                    void fetch("/captures/replay", {
                      method: "POST",
                      headers: { "Content-Type": "application/json" },
                      body: JSON.stringify({ capture_id: capture.capture_id }),
                    })
                      .then((response) => response.json())
                      .then((payload) => {
                        setError(
                          payload.provenance
                            ? `Replay ready: ${payload.provenance}`
                            : payload.error ?? "Replay request failed",
                        );
                      });
                  }}
                >
                  Replay
                </button>
              ) : null}
            </li>
          ))}
        </ul>
      </section>

      <section className="panel">
        <h2>UI</h2>
        <p>Recent instruments</p>
        <ul>
          {(state?.recent_instruments ?? []).map((row) => (
            <li key={row.instrument_id}>{row.instrument_id}</li>
          ))}
        </ul>
        <p>Default watchlist</p>
        {mutationsEnabled ? (
          <div className="live-actions">
            <input value={watchInput} onChange={(event) => setWatchInput(event.target.value.toUpperCase())} />
            <button type="button" onClick={() => void addWatch()}>
              Add to watchlist
            </button>
          </div>
        ) : null}
        <ul>
          {(state?.watchlists?.[0]?.items ?? []).map((item) => (
            <li key={item.instrument_id}>{item.instrument_id}</li>
          ))}
        </ul>
      </section>

      <section className="panel">
        <h2>Safety env (read-only)</h2>
        <JsonDetailPanel title="Safety configuration" value={state?.safety ?? startup?.safety ?? {}} />
      </section>
    </section>
  );
}
