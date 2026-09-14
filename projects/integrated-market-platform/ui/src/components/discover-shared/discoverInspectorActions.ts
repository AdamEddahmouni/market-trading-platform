import type { AttentionItem } from "../../api/client";

export type DiscoverInspectorActions = {
  onExplain: (item: AttentionItem) => void;
  onInspect: (item: AttentionItem) => void;
  onOpenWorkspace: (item: AttentionItem) => void;
};
