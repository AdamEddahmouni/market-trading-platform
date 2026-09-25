import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ImpCapabilityStrip } from "./ImpCapabilityStrip";

describe("ImpCapabilityStrip", () => {
  it("renders capability chips and opens provider matrix", () => {
    const onOpen = vi.fn();
    render(
      <ImpCapabilityStrip
        capabilityStates={[{ capability_id: "data.ingest", state: "READY" }]}
        onOpenProviderMatrix={onOpen}
      />,
    );
    expect(screen.getByText("data.ingest")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Provider matrix" }));
    expect(onOpen).toHaveBeenCalled();
  });

  it("separates blocked capabilities from limited capabilities in the summary", () => {
    render(
      <ImpCapabilityStrip
        capabilityStates={[
          { capability_id: "data.ingest", state: "READY" },
          { capability_id: "provider.moomoo", state: "DEGRADED" },
          { capability_id: "provider.tws", state: "UNCONFIGURED" },
        ]}
      />,
    );
    expect(screen.getByText("1 available · 1 limited · 1 blocked")).toBeInTheDocument();
  });
});
