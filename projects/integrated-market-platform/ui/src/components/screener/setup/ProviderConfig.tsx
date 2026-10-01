import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import { createPortal } from "react-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  describeSaveError,
  fetchProviderConfig,
  PROVIDER_CONFIG_QUERY_KEY,
  saveProviderSettings,
  type ProviderField,
  type ProviderSetup,
  type SaveResult,
} from "../../../api/providerConfig";
import { refreshProviderQueries } from "./refresh";
import "./setup.css";

/*
 * Provider setup. A secret typed here lives only in this form's state until the save request is
 * sent: it is never put in a query cache, storage, or a URL, the server never sends it back, and the
 * field is emptied as soon as the save succeeds or the form closes.
 */

const ACCESS_TEXT: Record<string, string> = {
  FREE: "Free",
  FREE_ACCOUNT: "Free account",
  PAID_API: "Paid API · billed by the provider",
  SUBSCRIPTION: "Your existing subscription",
  PAPER_SANDBOX: "Paper sandbox",
  ACCOUNT: "Your brokerage account",
};
const STATE_TEXT: Record<ProviderSetup["state"], string> = {
  CONFIGURED: "configured",
  PARTIAL: "incomplete",
  NEEDS_SETUP: "needs setup",
  OPTIONAL: "optional",
  EXTERNAL: "outside IMP",
};
const STATE_TONE: Record<ProviderSetup["state"], string> = {
  CONFIGURED: "ready", PARTIAL: "wait", NEEDS_SETUP: "off", OPTIONAL: "off", EXTERNAL: "off",
};
const SOURCE_TEXT: Record<ProviderField["source"], string> = {
  ENVIRONMENT: "Set by the API's environment. Change it there; IMP won't store a value that would be ignored.",
  PRIVATE_FILE: "Stored in IMP's private provider file on this computer.",
  ENV_FILE: "Read from the repository .env file. Saving here takes precedence.",
  PROVIDER_STORE: "Held in this provider's own private store on this computer, saved when it was connected. A value saved here replaces it.",
  NONE: "Not set.",
};
const FREE_ACCESS = new Set(["FREE", "FREE_ACCOUNT"]);

/** Only free providers (or half-entered ones) ask to be set up; paid, subscription, and broker ones are just "not set". */
function wantsSetup(provider: ProviderSetup): boolean {
  return provider.state === "PARTIAL" || (provider.state === "NEEDS_SETUP" && FREE_ACCESS.has(provider.access));
}

function stateLabel(provider: ProviderSetup): string {
  return provider.state === "NEEDS_SETUP" && !wantsSetup(provider) ? "not set" : STATE_TEXT[provider.state];
}

const GROUPS: [string, string][] = [
  ["REGULATORY", "Regulatory and government"], ["NEWS", "News"], ["MARKET_DATA", "Market and reference data"],
  ["AI", "AI synthesis"], ["LOCAL", "Local services"], ["BROKERAGE", "Brokerage"],
];

export function useProviderConfig(enabled = true) {
  return useQuery({
    queryKey: PROVIDER_CONFIG_QUERY_KEY, queryFn: ({ signal }) => fetchProviderConfig(signal),
    enabled, staleTime: 5_000, retry: 1,
  });
}

function appliesText(result: SaveResult, provider: ProviderSetup): string {
  const when = result.applies === "RESTART" ? "Restart the API to apply it." : "It applies to the next request; no restart needed.";
  const note = result.applies === "NEXT_REQUEST" && provider.applies_note ? ` ${provider.applies_note}` : "";
  return `${when}${note}`;
}

type Status =
  | { kind: "idle" } | { kind: "saving" } | { kind: "error"; message: string }
  | { kind: "saved"; text: string };

/** One provider's settings: set, replace, or remove registered values only. */
export function ProviderConfigForm({ provider }: { provider: ProviderSetup }) {
  const queryClient = useQueryClient();
  const [values, setValues] = useState<Record<string, string>>({});
  const [confirmRemove, setConfirmRemove] = useState<string | null>(null);
  const [status, setStatus] = useState<Status>({ kind: "idle" });
  const formId = useId();
  const editable = provider.fields.filter((field) => field.editable);
  const gatesOff = provider.live_gates.some((gate) => !gate.enabled);
  const typed = Object.values(values).some((value) => value.trim());

  const send = async (next: Record<string, string>, clear: string[]) => {
    setStatus({ kind: "saving" });
    try {
      const response = await saveProviderSettings(provider.provider, next, clear);
      setValues({});
      setConfirmRemove(null);
      const { result, ...config } = response;
      const done = result.saved.length ? "Saved." : "Removed.";
      const gates = result.gates_enabled.length ? ` ${provider.label} is switched on.` : "";
      const verify = result.saved.length ? " Nothing was called to test it: it is checked the first time IMP uses it." : "";
      setStatus({ kind: "saved", text: `${done}${gates} ${appliesText(result, provider)}${verify}` });
      queryClient.setQueryData(PROVIDER_CONFIG_QUERY_KEY, config);
      void queryClient.invalidateQueries({ queryKey: ["operator", "config"] });
      refreshProviderQueries(queryClient);
    } catch (error) {
      setStatus({ kind: "error", message: describeSaveError(error) });
    }
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!typed) {
      setStatus({ kind: "error", message: describeSaveError(new Error("NO_CHANGES")) });
      return;
    }
    void send(values, []);
  };

  if (!provider.configurable) {
    return <p className="setup-config-external">{provider.external_setup}</p>;
  }
  return <form className="setup-config-form" onSubmit={submit} aria-describedby={`${formId}-status`} autoComplete="off">
    {provider.fields.map((field) => {
      const inputId = `${formId}-${field.key}`;
      const placeholder = field.configured
        ? (field.sensitive ? "•••••••• stored · type a new value to replace" : "Stored · type a new value to replace")
        : field.example ?? (field.sensitive ? "Paste the value" : "");
      return <div key={field.key} className="setup-config-field">
        <label htmlFor={inputId}>{field.label}</label>
        {field.editable
          ? <input id={inputId} name={field.key} className="screener-control" type={field.sensitive ? "password" : "text"}
            autoComplete="off" spellCheck={false} autoCapitalize="off" placeholder={placeholder}
            value={values[field.key] ?? ""} disabled={status.kind === "saving"}
            onChange={(event) => setValues((current) => ({ ...current, [field.key]: event.target.value }))} />
          : <span className="setup-config-readonly" id={inputId}>Set outside IMP</span>}
        <small className="setup-config-source">
          {field.configured ? SOURCE_TEXT[field.source]
            : `${field.required ? "Required." : "Optional."} Saved to IMP's private provider file on this computer.`}
          {field.hint ? ` Current: ${field.hint}.` : ""}
          {field.help ? ` ${field.help}` : ""}
          <span className="setup-config-name"> Setting: {field.key}</span>
        </small>
        {field.removable && (confirmRemove === field.key
          ? <span className="setup-config-remove">Remove the stored {field.label.toLowerCase()}?{" "}
            <button type="button" className="setup-copy" disabled={status.kind === "saving"}
              onClick={() => void send({}, [field.key])}>Remove</button>{" "}
            <button type="button" className="setup-copy" onClick={() => setConfirmRemove(null)}>Keep</button></span>
          : <button type="button" className="setup-copy setup-config-remove-start"
            onClick={() => setConfirmRemove(field.key)}>Remove {field.sensitive ? "key" : "value"}</button>)}
      </div>;
    })}
    <div className="setup-config-actions">
      {editable.length > 0 && <button type="submit" className="screener-control setup-connect-button"
        disabled={status.kind === "saving"}>
        {status.kind === "saving" ? "Saving…" : provider.live_gates.length && gatesOff ? "Save & enable" : "Save"}</button>}
      <span id={`${formId}-status`} role="status" className={`setup-config-status ${status.kind}`}>
        {status.kind === "error" ? status.message : status.kind === "saved" ? status.text : ""}</span>
    </div>
  </form>;
}

function ProviderHeader({ provider, headingId }: { provider: ProviderSetup; headingId: string }) {
  return <header className="setup-config-header">
    <h2 id={headingId}>{provider.label}</h2>
    <span className={`setup-pill ${STATE_TONE[provider.state]}`}>{stateLabel(provider)}</span>
    <span className={`setup-config-access${provider.access === "PAID_API" ? " paid" : ""}`}>
      {ACCESS_TEXT[provider.access] ?? provider.access}</span>
  </header>;
}

/** Everything the operator needs to decide: what it is, what it unlocks, and the form. */
export function ProviderConfigDetail({ provider, headingId }: { provider: ProviderSetup; headingId: string }) {
  return <div className="setup-config-detail">
    <ProviderHeader provider={provider} headingId={headingId} />
    <p className="setup-config-about">{provider.about}</p>
    <div className="setup-config-unlocks"><strong>Unlocks</strong>
      <ul>{provider.unlocks.map((item) => <li key={item}>{item}</li>)}</ul></div>
    {provider.applies === "RESTART" && provider.applies_note &&
      <p className="setup-config-restart">Needs an API restart after saving. {provider.applies_note}</p>}
    <ProviderConfigForm provider={provider} />
  </div>;
}

/** A modal Setup form for one provider, opened from a Configure button anywhere a degraded state shows. */
export function ProviderConfigDialog({ provider, onClose }: { provider: string; onClose: () => void }) {
  const query = useProviderConfig();
  const headingId = useId();
  const panel = useRef<HTMLDivElement>(null);
  const close = useRef(onClose);
  close.current = onClose;
  useEffect(() => {
    // Escape closes; focus returns to whatever opened the dialog.
    const previous = document.activeElement as HTMLElement | null;
    const onKey = (event: KeyboardEvent) => { if (event.key === "Escape") close.current(); };
    document.addEventListener("keydown", onKey);
    return () => { document.removeEventListener("keydown", onKey); previous?.focus?.(); };
  }, []);
  const entry = query.data?.providers.find((item) => item.provider === provider);
  useEffect(() => {
    panel.current?.querySelector<HTMLElement>("input:not([disabled]), button")?.focus();
  }, [entry?.provider]);
  return createPortal(<div className="setup-config-backdrop" onMouseDown={(event) => {
    if (event.target === event.currentTarget) onClose();
  }}>
    <div ref={panel} className="setup-config-dialog" role="dialog" aria-modal="true" aria-labelledby={headingId}>
      <button type="button" className="setup-config-close" aria-label="Close" onClick={onClose}>×</button>
      {entry ? <ProviderConfigDetail provider={entry} headingId={headingId} />
        : query.isError ? <p id={headingId} role="alert">Provider settings could not be loaded. Is the API running?</p>
        : query.data ? <p id={headingId}>IMP has no setup form for this provider.</p>
        : <p id={headingId}>Loading provider settings…</p>}
    </div>
  </div>, document.body);
}

/** Opens the Setup form for one registered provider. */
export function ConfigureButton({ provider, label }: { provider: string; label: string }) {
  const [open, setOpen] = useState(false);
  return <>
    <button type="button" className="screener-control setup-connect-button" aria-haspopup="dialog"
      onClick={() => setOpen(true)}>{label}</button>
    {open && <ProviderConfigDialog provider={provider} onClose={() => setOpen(false)} />}
  </>;
}

/** Every registered provider, grouped; groups with something to do start open. */
export function ProviderSetupList({ enabled }: { enabled: boolean }) {
  const query = useProviderConfig(enabled);
  const [open, setOpen] = useState<string | null>(null);
  if (query.isError && !query.data) {
    return <p className="setup-summary" role="alert">Provider settings could not be loaded.{" "}
      <button type="button" className="setup-copy" onClick={() => void query.refetch()}>Retry</button></p>;
  }
  if (!query.data) return <p className="setup-summary">Loading provider settings…</p>;
  const providers = query.data.providers;
  return <section className="setup-providers" aria-label="Provider settings">
    <h3 className="setup-section-title">Provider settings</h3>
    {GROUPS.map(([group, title]) => {
      const members = providers.filter((item) => item.group === group);
      if (!members.length) return null;
      const pending = members.filter(wantsSetup).length;
      return <details key={group} className="setup-group" open={pending > 0}>
        <summary>{title}<span className="setup-group-count">{pending ? `${pending} to set up` : "ok"}</span></summary>
        <ul className="setup-list">{members.map((item) => <li key={item.provider} className="setup-row">
          <span className="setup-row-label">{item.label}
            <small className="setup-row-access">{ACCESS_TEXT[item.access] ?? item.access}</small></span>
          <span className={`setup-pill ${STATE_TONE[item.state]}`}>{stateLabel(item)}</span>
          <span className="setup-row-step">{item.configurable
            ? <><span className="setup-row-unlocks">{item.unlocks.join(" · ")}</span>{" "}
              <button type="button" className="screener-control setup-connect-button" aria-haspopup="dialog"
                aria-label={`${item.state === "CONFIGURED" ? "Manage" : "Configure"} ${item.label}`}
                onClick={() => setOpen(item.provider)}>{item.state === "CONFIGURED" ? "Manage" : "Configure"}</button></>
            : <span>{item.external_setup}</span>}</span>
        </li>)}</ul>
      </details>;
    })}
    {open && <ProviderConfigDialog provider={open} onClose={() => setOpen(null)} />}
  </section>;
}
