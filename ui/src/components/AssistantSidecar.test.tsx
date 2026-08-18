import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { AssistantSidecar } from "./AssistantSidecar";

const status = {
  available: true,
  authority_boundary: "READ_ONLY_NO_EXECUTION",
  citation_required: true,
  default_principal_id: "RESEARCH-UI-001",
  epistemic_class: "RESEARCH_ASSISTANT_GROUNDED",
  logical_id: "assistant.status",
  model_id: "deterministic.v1",
  provider_id: "grounded.evidence",
  store_fingerprint: "abc",
  as_of_context: {
    as_of_time: "2026-07-21T21:01:09.000000000Z",
    instrument_id: "BIYA",
    mode: "REPLAY",
    replay_session_id: "session-1",
    timezone: "America/New_York",
  },
};

describe("AssistantSidecar", () => {
  it("renders quick actions and submits prompts", () => {
    const onSubmit = vi.fn();
    render(
      <MemoryRouter>
        <AssistantSidecar
          open
          status={status}
          messages={[]}
          loading={false}
          conversationId="conv-1"
          selectionRef="explain:quality:system"
          onClose={() => {}}
          onSubmit={onSubmit}
        />
      </MemoryRouter>,
    );
    expect(screen.getByText(/grounded\.evidence/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "What changed?" }));
    expect(onSubmit).toHaveBeenCalledWith("What changed at this replay cursor?");
  });
});
