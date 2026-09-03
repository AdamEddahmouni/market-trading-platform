import type { AttentionItem } from "../../api/client";

export function topAttentionItem(items: AttentionItem[]): AttentionItem | undefined {
  return items.reduce<AttentionItem | undefined>((current, item) => {
    if (!current || item.priority_rank < current.priority_rank) return item;
    return current;
  }, undefined);
}

type Props = {
  items: AttentionItem[];
  canAdvance: boolean;
  replayPending: boolean;
  onExplain: (item: AttentionItem) => void;
  onInspect: (item: AttentionItem) => void;
  onOpenWorkspace: (item: AttentionItem) => void;
  onAdvance: () => void;
};

export function DemoInspectNext({
  items,
  canAdvance,
  replayPending,
  onExplain,
  onInspect,
  onOpenWorkspace,
  onAdvance,
}: Props) {
  const top = topAttentionItem(items);
  return (
    <section className="demo-now-panel demo-inspect-panel" aria-labelledby="demo-inspect-title">
      <div className="demo-panel-heading">
        <div>
          <p className="demo-eyebrow">Guided research path</p>
          <h2 id="demo-inspect-title">Inspect next</h2>
        </div>
      </div>
      {top ? (
        <ol className="demo-step-list">
          <li>
            <span>01</span>
            <button type="button" onClick={() => onExplain(top)} aria-label={`Explain ${top.headline}`}>
              Understand why this item matters
            </button>
          </li>
          <li>
            <span>02</span>
            {top.instrument_id ? (
              <button
                type="button"
                onClick={() => onOpenWorkspace(top)}
                aria-label={`Open ${top.instrument_id} workspace`}
              >
                Open the instrument workspace
              </button>
            ) : (
              <button type="button" onClick={() => onInspect(top)}>
                Inspect supporting evidence
              </button>
            )}
          </li>
          <li>
            <span>03</span>
            <button
              className="primary"
              type="button"
              disabled={!canAdvance || replayPending}
              onClick={onAdvance}
            >
              Advance one event
            </button>
          </li>
        </ol>
      ) : (
        <div className="demo-empty-path">
          <p>No item requires inspection at the current event.</p>
          <button
            className="primary"
            type="button"
            disabled={!canAdvance || replayPending}
            onClick={onAdvance}
          >
            Advance one event
          </button>
        </div>
      )}
    </section>
  );
}
