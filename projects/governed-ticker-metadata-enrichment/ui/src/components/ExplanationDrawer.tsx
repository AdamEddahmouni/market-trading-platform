type Props = {
  payload: Record<string, unknown> | null;
  onClose: () => void;
};

export function ExplanationDrawer({ payload, onClose }: Props) {
  if (!payload) return null;
  const explanation = payload.explanation as Record<string, string> | undefined;
  return (
    <aside className="drawer explanation-drawer" aria-label="Explanation">
      <header>
        <h2>Explanation</h2>
        <button type="button" onClick={onClose}>
          Esc
        </button>
      </header>
      {explanation ? (
        <div className="drawer-body">
          <p className="meaning">{explanation.meaning}</p>
          <p>{explanation.why}</p>
          <p className="alignment">{explanation.alignment_summary}</p>
        </div>
      ) : (
        <p className="drawer-body">No explanation available.</p>
      )}
    </aside>
  );
}
