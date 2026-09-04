import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { AsOfContext } from "../../api/client";
import { ModeEnvironmentBar } from "./ModeEnvironmentBar";
import type { Mode } from "./types";

function context(overrides: Partial<AsOfContext> = {}): AsOfContext {
  return {
    mode: "REPLAY",
    data_mode: "FIXTURE_REPLAY",
    execution_mode: "NONE",
    execution_authority: "BLOCKED",
    as_of_time: "2026-08-30T12:00:00Z",
    timezone: "America/New_York",
    ...overrides,
  };
}

describe("ModeEnvironmentBar", () => {
  it.each([
    ["DEMO", "Historical research · No execution"],
    ["PAPER", "Internal simulation · Paper authority only"],
    ["LIVE", "Current market observation · Execution locked"],
  ] satisfies Array<[Mode, string]>)("names the %s environment without relying on color", (mode, boundary) => {
    render(
      <ModeEnvironmentBar
        mode={mode}
        context={context()}
        contextState="ready"
        onSwitchMode={() => undefined}
      />,
    );

    const region = screen.getByRole("region", { name: "Session environment" });
    expect(region).toHaveTextContent(mode);
    expect(region).toHaveTextContent(boundary);
    expect(region).toHaveAttribute("data-mode", mode);
  });

  it("uses a native switch control", () => {
    const onSwitchMode = vi.fn();
    render(
      <ModeEnvironmentBar
        mode="DEMO"
        context={context()}
        contextState="ready"
        onSwitchMode={onSwitchMode}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Switch mode" }));
    expect(onSwitchMode).toHaveBeenCalledOnce();
  });

  it("announces context verification politely", () => {
    render(
      <ModeEnvironmentBar
        mode="PAPER"
        contextState="loading"
        onSwitchMode={() => undefined}
      />,
    );

    expect(screen.getByRole("status")).toHaveTextContent("Verifying backend context…");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("alerts when backend context is unavailable", () => {
    render(
      <ModeEnvironmentBar
        mode="LIVE"
        contextState="error"
        onSwitchMode={() => undefined}
      />,
    );

    expect(screen.getByRole("alert")).toHaveTextContent(
      "Backend context unavailable. Execution controls remain locked.",
    );
  });

  it("alerts with selected and actual context when they mismatch", () => {
    render(
      <ModeEnvironmentBar
        mode="PAPER"
        context={context()}
        contextState="ready"
        onSwitchMode={() => undefined}
      />,
    );

    expect(screen.getByRole("alert")).toHaveTextContent("Selected PAPER");
    expect(screen.getByRole("alert")).toHaveTextContent("EXEC NONE");
    expect(screen.getByRole("alert")).toHaveTextContent("AUTH BLOCKED");
    expect(screen.getByRole("alert")).toHaveTextContent(
      "UI mode selection does not change backend authority.",
    );
  });
});
