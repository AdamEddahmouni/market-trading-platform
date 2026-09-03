import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { canUsePaperActions } from "../mode-session/modeAuthority";
import { createLanePaperOrderDraft, parseLaneProvenance } from "../paper-now/paperOrderDraft";
import { LaneModeContextPanel } from "./LaneModeContextPanel";
import { WorkspaceModuleModeShell } from "./WorkspaceModuleModeShell";

describe("Paper lane authority and draft safety", () => {
  it("exposes provenance-aware lane draft in Paper lane context panel", () => {
    render(
      <MemoryRouter>
        <LaneModeContextPanel
          mode="PAPER"
          moduleId="squeeze"
          instrumentId="BIYA"
          queryState={{
            phase: "ready",
            provenance: {
              lane_id: "squeeze",
              source_kind: "lane_payload",
              source_time: 1_700_000_000_000_000_000,
              retrieved_at: 1_700_000_100_000_000_000,
            },
          }}
          content={{
            headline: "Squeeze simulation readiness",
            summary: "Test",
            sections: [],
          }}
        />
      </MemoryRouter>,
    );

    expect(screen.getByRole("link", { name: "Draft paper order from lane" })).toBeInTheDocument();
    expect(screen.getByText(/Placeholder draft uses BUY × 1 MARKET/i)).toBeInTheDocument();
    expect(screen.getByText(/Provenance: lane:squeeze/i)).toBeInTheDocument();
  });

  it("Paper shell links overview and portfolio without duplicate draft control", () => {
    render(
      <MemoryRouter>
        <WorkspaceModuleModeShell
          mode="PAPER"
          instrumentId="BIYA"
          active="squeeze"
          pageClassName="squeeze-workspace-page"
          moduleTitle="Short Squeeze Workspace"
          description="Test"
        >
          <div>evidence</div>
        </WorkspaceModuleModeShell>
      </MemoryRouter>,
    );

    expect(screen.queryByRole("link", { name: "Draft paper order from lane" })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open workspace overview" })).toBeInTheDocument();
  });

  it("does not expose lane draft link in Demo or Live shells", () => {
    const { rerender } = render(
      <MemoryRouter>
        <WorkspaceModuleModeShell
          mode="DEMO"
          instrumentId="BIYA"
          active="squeeze"
          pageClassName="squeeze-workspace-page"
          moduleTitle="Short Squeeze Workspace"
          description="Test"
        >
          <div>evidence</div>
        </WorkspaceModuleModeShell>
      </MemoryRouter>,
    );
    expect(screen.queryByRole("link", { name: "Draft paper order from lane" })).not.toBeInTheDocument();

    rerender(
      <MemoryRouter>
        <WorkspaceModuleModeShell
          mode="LIVE"
          instrumentId="BIYA"
          active="squeeze"
          pageClassName="squeeze-workspace-page"
          moduleTitle="Short Squeeze Workspace"
          description="Test"
        >
          <div>evidence</div>
        </WorkspaceModuleModeShell>
      </MemoryRouter>,
    );
    expect(screen.queryByRole("link", { name: "Draft paper order from lane" })).not.toBeInTheDocument();
  });

  it("fails closed when paper authority is missing", () => {
    expect(
      canUsePaperActions("PAPER", true, {
        execution_mode: "NONE",
        execution_authority: "BLOCKED",
      }),
    ).toBe(false);
  });

  it("parses lane provenance from draft sourceAttentionId", () => {
    const draft = createLanePaperOrderDraft("BIYA", "order-flow");
    expect(parseLaneProvenance(draft.sourceAttentionId)).toEqual({
      moduleId: "order-flow",
      label: "Order Flow",
      isKnown: true,
    });
  });
});

vi.mock("../../api/hooks", () => ({
  usePaperPortfolioQuery: () => ({ data: undefined }),
}));
