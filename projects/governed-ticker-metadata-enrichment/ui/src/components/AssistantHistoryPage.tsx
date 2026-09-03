import { useQuery } from "@tanstack/react-query";
import { api } from "../api/endpoints";
import { queryKeys } from "../api/hooks";

export function AssistantHistoryPage() {
  const conversationsQuery = useQuery({
    queryKey: queryKeys.assistantConversations,
    queryFn: () => api.getAssistantConversations(),
  });

  return (
    <section className="page assistant-history-page">
      <header className="page-header">
        <h1>Assistant history</h1>
        <p>Secondary route — audited research prompts, not primary navigation.</p>
      </header>
      {conversationsQuery.isLoading ? <p>Loading conversations…</p> : null}
      {conversationsQuery.data?.conversations.length === 0 ? (
        <p>No conversations yet. Open the assistant sidecar (press A) to start.</p>
      ) : (
        <ul className="assistant-history-list">
          {conversationsQuery.data?.conversations.map((conversation) => (
            <li key={conversation.conversation_id}>
              <strong>{conversation.title}</strong>
              <span>{conversation.message_count} messages</span>
              <code>{conversation.conversation_id}</code>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
