import { useState, type FormEvent } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { describeSaveError, PROVIDER_CONFIG_QUERY_KEY, saveProviderSettings } from "../../../api/providerConfig";
import { postSynthesisEngine, type SynthesisEngine } from "../../../api/screenerNews";
import { SETUP_QUERY_KEY } from "../../../api/screenerSetup";
import { fetchSetupAi, SETUP_AI_QUERY_KEY, type SetupAi } from "../../../api/setupAi";
import { EngineSwitchConfirm, type PendingEngine } from "../ai/EngineSwitch";
import "./setup.css";

/*
 * Which AI decides, for the whole machine: the free local model or one paid model under hard dollar caps.
 * Paid can be chosen only once both caps are above $0; the server refuses it otherwise. Switching asks first,
 * and is refused while automatic passes are running. Nothing here calls a model.
 */

const dollars = (value: number | null | undefined, digits = 2) => value == null ? "–" : `$${value.toFixed(digits)}`;
const perDecision = (value: number | null | undefined) => value == null ? null
  : value < 0.01 ? `about ${(value * 100).toFixed(2)}¢ per decision` : `about ${dollars(value, 3)} per decision`;
const seconds = (ms: number | null | undefined) => ms == null ? null : `${(ms / 1000).toFixed(1)} s`;

function measured(data: SetupAi, model: string | null) {
  return data.benchmark?.runs.find((run) => run.model === model && !run.skipped) ?? null;
}

function lockText(data: SetupAi) {
  if (!data.engine_lock.locked) return null;
  return data.engine_lock.reason === "REEVALUATION_LOOP_RUNNING"
    ? "Locked while Paper's automatic passes are running. Pause them to switch."
    : `Locked: the state of automatic passes could not be read${data.engine_lock.reason ? ` (${data.engine_lock.reason})` : ""}.`;
}

/** The two dollar caps, saved to IMP's private provider file. $0 keeps paid AI off. */
function CapsForm({ data }: { data: SetupAi }) {
  const client = useQueryClient();
  const [daily, setDaily] = useState("");
  const [monthly, setMonthly] = useState("");
  const [status, setStatus] = useState<{ kind: "idle" | "saving" | "saved" | "error"; text: string }>({ kind: "idle", text: "" });
  const settings = data.caps.settings;
  const fixed = !settings.IMP_PAID_AI_DAILY_USD.editable || !settings.IMP_PAID_AI_MONTHLY_USD.editable;
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const values: Record<string, string> = {};
    if (daily.trim()) values.IMP_PAID_AI_DAILY_USD = daily.trim();
    if (monthly.trim()) values.IMP_PAID_AI_MONTHLY_USD = monthly.trim();
    if (!Object.keys(values).length) { setStatus({ kind: "error", text: describeSaveError(new Error("NO_CHANGES")) }); return; }
    setStatus({ kind: "saving", text: "" });
    try {
      await saveProviderSettings("paid_ai", values);
      setDaily(""); setMonthly("");
      setStatus({ kind: "saved", text: "Saved. The caps apply to the next paid call." });
      void client.invalidateQueries({ queryKey: SETUP_AI_QUERY_KEY });
      void client.invalidateQueries({ queryKey: PROVIDER_CONFIG_QUERY_KEY });
    } catch (error) {
      setStatus({ kind: "error", text: describeSaveError(error) });
    }
  };
  return <form className="setup-ai-caps" onSubmit={(event) => void submit(event)} aria-label="Paid AI dollar caps" autoComplete="off">
    <p>Spending caps (US dollars, at each model's list price): <strong>{dollars(data.caps.daily_usd)} a day</strong>,{" "}
      <strong>{dollars(data.caps.monthly_usd)} a month</strong>.{data.caps.set ? "" : " Paid AI stays off until both are above $0."}</p>
    {fixed ? <p className="setup-config-source">The caps are set by the API's environment; change them there.</p> : <div className="setup-ai-cap-fields">
      <label>Daily cap <input className="screener-control" inputMode="decimal" placeholder={data.caps.daily_usd ? String(data.caps.daily_usd) : "e.g. 1.50"}
        value={daily} disabled={status.kind === "saving"} onChange={(event) => setDaily(event.target.value)} /></label>
      <label>Monthly cap <input className="screener-control" inputMode="decimal" placeholder={data.caps.monthly_usd ? String(data.caps.monthly_usd) : "e.g. 20"}
        value={monthly} disabled={status.kind === "saving"} onChange={(event) => setMonthly(event.target.value)} /></label>
      <button type="submit" className="screener-control setup-connect-button" disabled={status.kind === "saving"}>
        {status.kind === "saving" ? "Saving…" : "Save caps"}</button>
    </div>}
    <span role="status" className={`setup-config-status ${status.kind}`}>{status.text}</span>
  </form>;
}

/** Setup's single place to choose the AI: free local or capped paid. */
export function AiEngineCard({ enabled }: { enabled: boolean }) {
  const client = useQueryClient();
  const query = useQuery({ queryKey: SETUP_AI_QUERY_KEY, queryFn: ({ signal }) => fetchSetupAi(signal),
    enabled, staleTime: 5_000, refetchInterval: enabled ? 30_000 : false, retry: 1 });
  const [pending, setPending] = useState<PendingEngine | null>(null);
  const [paidModel, setPaidModel] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState<string | null>(null);
  const data = query.data;
  if (query.isError && !data) {
    return <p className="setup-summary" role="alert">The AI choice could not be loaded.{" "}
      <button type="button" className="setup-copy" onClick={() => void query.refetch()}>Retry</button></p>;
  }
  if (!data) return <p className="setup-summary">Loading the AI choice…</p>;
  const local = data.engines.find((engine) => engine.runtime === "LOCAL_MODEL");
  const paid = data.engines.filter((engine) => engine.runtime === "PAID_API");
  const paidOptions = paid.flatMap((engine) => engine.models.map((model) => ({ engine, model })));
  const usable = paidOptions.filter((option) => option.engine.state === "AVAILABLE");
  const isPaid = data.resolved_engine !== "local";
  const chosenPaid = paidModel ?? (isPaid ? data.model : null) ?? data.benchmark?.paid_pick ?? usable[0]?.model ?? null;
  const chosenOption = paidOptions.find((option) => option.model === chosenPaid) ?? null;
  const locked = lockText(data);
  const price = data.prices.find((row) => row.model === chosenPaid);
  const localRun = measured(data, local?.models[0] ?? null);
  const paidRun = measured(data, chosenPaid);
  const propose = (engine: SynthesisEngine | undefined, model: string | null) => {
    if (!engine) return;
    setFailed(null); setPending({ engine, model });
  };
  const confirm = async () => {
    if (!pending) return;
    setBusy(true); setFailed(null);
    try {
      await postSynthesisEngine(pending.engine.id, pending.model);
      void client.invalidateQueries({ queryKey: SETUP_AI_QUERY_KEY });
      void client.invalidateQueries({ queryKey: SETUP_QUERY_KEY });
      void client.invalidateQueries({ queryKey: ["screener-news-instrument"] });
      void client.invalidateQueries({ queryKey: ["screener-news-synthesis-preview"] });
    } catch (error) {
      const text = error instanceof Error ? error.message : String(error);
      setFailed(text.includes("PAID_AI_CAP_NOT_SET") ? "Set both dollar caps first." : "Could not switch the AI.");
    } finally {
      setBusy(false); setPending(null);
    }
  };
  const paidBlocked = !data.caps.set ? "Set both dollar caps below to choose paid AI."
    : !chosenOption ? "No paid model is set up: save an API key under Provider settings."
    : chosenOption.engine.state !== "AVAILABLE" ? `${chosenOption.engine.label} is not ready (${chosenOption.engine.reason ?? "unavailable"}).` : null;
  return <section className="setup-ai" aria-label="Which AI decides">
    <h3 className="setup-section-title">Which AI decides</h3>
    <p className="setup-ai-now">Now: <strong>{isPaid ? `Paid · ${data.model ?? "default model"}` : `Free · ${local?.models[0] ?? "local model (not installed)"}`}</strong>
      {data.source === "AUTOMATIC" ? " (automatic always means the free local model)" : ""}</p>
    <div className="setup-ai-options">
      <div className={`setup-ai-option${isPaid ? "" : " chosen"}`}>
        <h4>Free — runs on this PC</h4>
        <p>{local?.models[0] ?? "No local model is installed."}{local?.state !== "AVAILABLE" && local?.reason ? ` · ${local.reason}` : ""}</p>
        {localRun && <p className="setup-config-source">Tested on {localRun.cases} past decisions: {localRun.accepted_pct}% accepted, typically {seconds(localRun.p50_latency_ms)}.</p>}
        {isPaid && <button type="button" className="screener-control setup-connect-button" disabled={busy || Boolean(locked) || !local}
          onClick={() => propose(local, null)}>Use free local</button>}
      </div>
      <div className={`setup-ai-option${isPaid ? " chosen" : ""}`}>
        <h4>Paid — billed per decision</h4>
        <label>Model <select className="screener-control" value={chosenPaid ?? ""} disabled={busy}
          onChange={(event) => setPaidModel(event.target.value || null)}>
          {paidOptions.map(({ engine, model }) => <option key={model} value={model}>
            {engine.label} · {model}{engine.state === "AVAILABLE" ? "" : " (not ready)"}</option>)}
        </select></label>
        {price && <p className="setup-config-source">List price {dollars(price.input_per_mtok)} in / {dollars(price.output_per_mtok)} out per million tokens.
          {paidRun ? ` Measured ${perDecision(paidRun.dollars_per_case)}, ${paidRun.accepted_pct}% accepted.` : ""}</p>}
        <p>Spent {dollars(data.spend.spent_today_usd ?? 0, 4)} today and {dollars(data.spend.spent_month_usd ?? 0, 4)} this month,
          of {dollars(data.caps.daily_usd)} / {dollars(data.caps.monthly_usd)}.</p>
        {paidBlocked ? <p className="setup-ai-blocked">{paidBlocked}</p>
          : (!isPaid || chosenPaid !== data.model) && <button type="button" className="screener-control setup-connect-button"
            disabled={busy || Boolean(locked)} onClick={() => propose(chosenOption?.engine, chosenPaid)}>Use paid {chosenPaid}</button>}
      </div>
    </div>
    {locked && <p className="setup-ai-blocked">{locked}</p>}
    <p className="setup-config-source">Paper uses paid AI only if its own risk policy allows it. To let Paper use paid AI, pause Paper and re-arm it with paid AI allowed.</p>
    {pending && <EngineSwitchConfirm pending={pending} busy={busy} onConfirm={() => void confirm()} onCancel={() => setPending(null)} />}
    {failed && <p className="setup-ai-blocked" role="alert">{failed}</p>}
    <CapsForm data={data} />
  </section>;
}
