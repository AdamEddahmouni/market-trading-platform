import { type FormEvent } from "react";
import { Link } from "react-router-dom";
import type { AssistantMessage, AssistantStatus } from "../api/schemas";

type Props = {
  open: boolean;
  status: AssistantStatus | undefined;
  messages: AssistantMessage[];
  loading: boolean;
  conversationId: string | null;
  selectionRef?: string | null;
  onClose: () => void;
  onSubmit: (prompt: string) => void;
};

export function AssistantSidecar({
  open,
  status,
  messages,
  loading,
  conversationId,
  selectionRef,
  onClose,
  onSubmit,
}: Props) {
  if (!open) return null;

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = event.currentTarget;
    const input = form.elements.namedItem("prompt") as HTMLInputElement;
    const value = input.value.trim();
    if (!value) return;
    onSubmit(value);
    input.value = "";
  };

  return (
    <aside className="assistant-sidecar" aria-label="AI research assistant">
      <header>
        <div>
          <h2>Research assistant</h2>
          <p className="assistant-meta">
            {status?.as_of_context.instrument_id} @ {status?.as_of_context.mode}
          </p>
        </div>
        <button type="button" onClick={onClose} aria-label="Close assistant">
          Close
        </button>
      </header>
      <p className="assistant-disclaimer">
        Read-only citations. No order, risk, or execution authority.
        {status?.provider_id ? ` Provider: ${status.provider_id}.` : ""}
      </p>
      {selectionRef ? <p className="assistant-selection">Selection: <code>{selectionRef}</code></p> : null}
      <div className="assistant-messages" aria-live="polite">
        {loading && messages.length === 0 ? <p>Loading conversation…</p> : null}
        {messages.map((message) => (
          <article key={message.message_id} className={`assistant-message role-${message.role}`}>
            <header>{message.role}</header>
            <p>{message.content || "—"}</p>
            {message.provenance?.abstained ? (
              <p className="assistant-abstain">
                Abstained: {message.provenance.abstention_reason ?? "no provider"}
              </p>
            ) : null}
            {message.provenance?.citation_refs?.length ? (
              <ul className="assistant-citations">
                {message.provenance.citation_refs.map((ref) => (
                  <li key={ref}><code>{ref}</code></li>
                ))}
              </ul>
            ) : null}
          </article>
        ))}
      </div>
      <form className="assistant-form" onSubmit={handleSubmit}>
        <label className="sr-only" htmlFor="assistant-prompt">Ask about visible context</label>
        <input
          id="assistant-prompt"
          name="prompt"
          type="text"
          placeholder={conversationId ? "Ask about this replay context…" : "Starting session…"}
          disabled={!conversationId || loading}
        />
        <button type="submit" disabled={!conversationId || loading}>Send</button>
      </form>
      <footer className="assistant-footer">
        <Link to="/assistant/history">Conversation history</Link>
      </footer>
    </aside>
  );
}
