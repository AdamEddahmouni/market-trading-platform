import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { fetchJson, postJson } from "../../api/fetchJson";
import { ApiRequestError } from "../../api/errors";
import { Investigation, InvestigationList } from "../../api/workspaceInvestigations";
import { queryKeys, useContextQuery } from "../../api/hooks";
import type { Mode } from "../mode-session/types";

export function InvestigationPanel({ instrumentId, mode }: { instrumentId: string; mode: Mode }) {
  const [params, setParams] = useSearchParams();
  const workId = params.get("work");
  const attentionId = params.get("attention");
  const opportunityId = params.get("opportunity");
  const [note, setNote] = useState("");
  const [baseNote, setBaseNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [conflict, setConflict] = useState(false);
  const lastServer = useRef<{ workspaceId: string; note: string } | null>(null);
  const contextQuery = useContextQuery();
  const list = useQuery({
    queryKey: queryKeys.investigations,
    queryFn: () => fetchJson("/operator/investigations", InvestigationList),
  });
  const detail = useQuery({
    queryKey: queryKeys.investigation(workId),
    queryFn: () => fetchJson(`/operator/investigations/${encodeURIComponent(workId!)}`, Investigation),
    enabled: Boolean(workId),
  });
  const active = detail.data;
  const related = list.data?.investigations.filter((item) => item.instrument_id === instrumentId) ?? [];
  const dataMode = contextQuery.data?.as_of_context.data_mode;
  const paperContext = contextQuery.data?.as_of_context.execution_mode === "INTERNAL_SIMULATION" &&
    contextQuery.data?.as_of_context.execution_authority === "PAPER_ONLY";
  const mayWrite = mode === "PAPER" && Boolean(dataMode) && paperContext;

  useEffect(() => {
    if (!active) return;
    const previous = lastServer.current;
    if (!previous || previous.workspaceId !== active.workspace_id) {
      setNote(active.note);
      setBaseNote(active.note);
      setSaved(false);
    } else if (previous.note !== active.note && note === previous.note) {
      setNote(active.note);
      setBaseNote(active.note);
    }
    lastServer.current = { workspaceId: active.workspace_id, note: active.note };
  }, [active]);

  useEffect(() => {
    if (!attentionId || workId || !mayWrite || !list.data || busy || error) return;
    const existing = list.data.investigations.find((item) =>
      item.instrument_id === instrumentId && item.source_kind === "radar_attention" &&
      item.source_id === attentionId && item.opportunity_id === opportunityId,
    );
    if (existing) setParams({ work: existing.workspace_id }, { replace: true });
    else void create();
    // The server deduplicates a repeated Radar handoff by source identity.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [attentionId, opportunityId, workId, mayWrite, list.data, instrumentId, busy, error, setParams]);

  async function create() {
    setBusy(true); setError(null); setSaved(false); setConflict(false);
    try {
      const row = await postJson("/operator/investigations", {
        title: attentionId ? `${instrumentId} · Radar investigation` : `${instrumentId} investigation`,
        instrument_id: instrumentId,
        source_kind: attentionId ? "radar_attention" : "instrument",
        source_id: attentionId,
        opportunity_id: opportunityId,
      }, Investigation);
      await list.refetch();
      setParams({ work: row.workspace_id }, { replace: Boolean(attentionId) });
    } catch (cause) {
      setError(`${cause instanceof Error ? cause.message : "Could not create the investigation."} Creation was not confirmed. Retry this Radar handoff safely.`);
    } finally { setBusy(false); }
  }

  async function saveNote() {
    if (!active) return;
    setBusy(true); setError(null); setSaved(false); setConflict(false);
    try {
      const persisted = await postJson(`/operator/investigations/${encodeURIComponent(active.workspace_id)}/note`, { note, expected_note: baseNote }, Investigation);
      await Promise.all([detail.refetch(), list.refetch()]);
      setBaseNote(persisted.note);
      setSaved(true);
    } catch (cause) {
      if (cause instanceof ApiRequestError && cause.code === "WORKSPACE_NOTE_CONFLICT") {
        setError("Notes changed in another view. Your draft is still here. Copy it before loading the latest saved note.");
        setConflict(true);
      } else {
        setError(`${cause instanceof Error ? cause.message : "Could not save the note."} Save was not confirmed; your draft remains here.`);
      }
    } finally { setBusy(false); }
  }

  return <section className="workspace-investigation panel" aria-labelledby="investigation-title">
    <div className="workspace-investigation-heading">
      <div><span className="muted">Persistent work</span><h2 id="investigation-title">Investigation · {instrumentId}</h2></div>
      {mayWrite && <button type="button" disabled={busy} onClick={() => void create()}>New investigation</button>}
    </div>
    {attentionId && !workId && (mayWrite
      ? <p role="status">Opening Radar investigation {attentionId}…</p>
      : <p>Radar context is read-only in this mode. Switch to an authorized Paper session to save an investigation.</p>)}
    {!workId && !attentionId && related.length === 0 && !list.isLoading && !list.isError && <p>No saved investigations for this instrument yet.</p>}
    {list.isLoading && <p role="status">Loading saved investigations…</p>}
    {list.isError && <p role="alert">Saved investigations could not load. <button type="button" onClick={() => void list.refetch()}>Retry</button></p>}
    {related.length > 0 && <nav aria-label="Saved investigations for this instrument"><ul>{related.map((item) =>
      <li key={item.workspace_id}><button type="button" aria-current={workId === item.workspace_id ? "page" : undefined} onClick={() => setParams({ work: item.workspace_id })}>{item.title} · {item.source_kind === "radar_attention" ? "Radar" : "Instrument"} · {new Date(item.updated_at / 1_000_000).toLocaleString()}</button></li>
    )}</ul></nav>}
    {workId && detail.isLoading && <p role="status">Loading investigation…</p>}
    {workId && detail.isError && <p role="alert">Investigation could not load. <button type="button" onClick={() => void detail.refetch()}>Retry</button></p>}
    {active && active.instrument_id !== instrumentId && <p role="alert">This investigation belongs to {active.instrument_id}. Open it from the matching instrument workspace.</p>}
    {active && active.instrument_id === instrumentId && <>
      <p><strong>{active.title}</strong> · {active.status} · {active.source_kind === "radar_attention" ? `Radar ${active.source_id}` : "Instrument"}{active.opportunity_id ? ` · Opportunity ${active.opportunity_id}` : ""}</p>
      <label htmlFor="investigation-note">Investigation notes</label>
      <textarea id="investigation-note" value={note} onChange={(event) => { setNote(event.target.value); setSaved(false); }} maxLength={10000} readOnly={!mayWrite || active.status !== "ACTIVE"} disabled={busy} rows={4} />
      {mayWrite && active.status === "ACTIVE" && <button type="button" disabled={busy || note === baseNote} onClick={() => void saveNote()}>Save notes</button>}
      {saved && <p role="status">Notes saved.</p>}
    </>}
    {error && <p role="alert">{error}</p>}
    {conflict && <button type="button" onClick={async () => {
      const latest = await detail.refetch();
      if (latest.data) { setNote(latest.data.note); setBaseNote(latest.data.note); setConflict(false); setError(null); }
    }}>Load latest saved note (replace draft)</button>}
  </section>;
}
