import { vi } from "vitest";
import type { DiscoverInspectorActions } from "./discoverInspectorActions";

export function discoverPageTestActions(): DiscoverInspectorActions {
  return {
    onExplain: vi.fn(),
    onInspect: vi.fn(),
    onOpenWorkspace: vi.fn(),
  };
}
