import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { connectProvider, type ConnectResult, type Remedy } from "../../../api/screenerSetup";
import { ConfigureButton } from "./ProviderConfig";
import { refreshProviderQueries } from "./refresh";
import "./setup.css";

export { refreshProviderQueries };

// OpenD needs its login after launch; re-read at these offsets instead of waiting for the next minute poll.
const FOLLOW_UP_MS = [8_000, 20_000, 45_000];

type Status = { state: "pending" } | { state: "done"; result: ConnectResult } | { state: "error" };

/** Explicit operator click: start or connect one allowlisted local provider, then refresh what depends on it. */
export function ConnectButton({ provider, label }: { provider: string; label: string }) {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<Status | null>(null);
  const timers = useRef<number[]>([]);
  const mounted = useRef(true);
  // Set on every mount: StrictMode mounts, cleans up, and mounts again.
  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; timers.current.forEach((id) => window.clearTimeout(id)); };
  }, []);
  const connect = async () => {
    setStatus({ state: "pending" });
    try {
      const result = await connectProvider(provider);
      if (!mounted.current) return;
      setStatus({ state: "done", result });
      refreshProviderQueries(queryClient);
      if (result.state === "STARTING") {
        timers.current.forEach((id) => window.clearTimeout(id));
        timers.current = FOLLOW_UP_MS.map((ms) => window.setTimeout(() => refreshProviderQueries(queryClient), ms));
      }
    } catch {
      if (mounted.current) setStatus({ state: "error" });
    }
  };
  const pending = status?.state === "pending";
  const result = status?.state === "done" ? status.result : null;
  return <span className="setup-connect">
    <button type="button" className="screener-control setup-connect-button" disabled={pending} onClick={() => void connect()}>
      {pending ? "Starting…" : label}</button>
    <span role="status" className="setup-connect-status">
      {status?.state === "error" ? "Request failed. Is the API running?"
        : result?.state === "CONNECTED" ? "Connected. Reloading…"
        : result?.state === "STARTING" ? (result.remedy?.step ?? "Starting. This view refreshes on its own.")
        : result?.state === "FAILED" ? `${result.remedy?.title ?? "Could not start"}${result.remedy ? `. ${result.remedy.step}` : result.reason ? ` · ${result.reason}` : ""}`
        : ""}
    </span>
  </span>;
}

function CopyCommand({ command }: { command: string }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(command);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  };
  return <span className="setup-command"><code>{command}</code>
    <button type="button" className="setup-copy" aria-label={`Copy command: ${command}`} onClick={() => void copy()}>{copied ? "Copied" : "Copy"}</button></span>;
}

// Reason codes a live panel reports when the local OpenD daemon is down.
const OPEND_DOWN = new Set(["OPEND_UNAVAILABLE", "OPEN_D_NOT_RUNNING"]);

/** Start OpenD from wherever a live panel says it is unreachable. Renders nothing for any other reason. */
export function OpenDConnect({ reason }: { reason: string | null | undefined }) {
  return reason && OPEND_DOWN.has(reason) ? <> <ConnectButton provider="opend" label="Start OpenD" /></> : null;
}

/** What a degraded state means and the one step that clears it. The raw reason code stays available on hover. */
export function RemedyHint({ remedy, compact = false }: { remedy: Remedy; compact?: boolean }) {
  const action = remedy.action;
  return <span className={`setup-remedy${compact ? " compact" : ""}`} title={`Reason: ${remedy.reason}`}>
    <strong>{remedy.title}.</strong> <span>{remedy.step}</span>
    {action?.kind === "CONNECT" && <ConnectButton provider={action.provider} label={action.label} />}
    {action?.kind === "COMMAND" && <CopyCommand command={action.command} />}
    {action?.kind === "CONFIGURE" && <ConfigureButton provider={action.provider} label={action.label} />}
  </span>;
}
