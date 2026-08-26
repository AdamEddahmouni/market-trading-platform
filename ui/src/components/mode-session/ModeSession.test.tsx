import { act, fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ApplicationBootstrap } from "./ApplicationBootstrap";

function deferred<T>() {
  let resolve!: (value: T | PromiseLike<T>) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((promiseResolve, promiseReject) => {
    resolve = promiseResolve;
    reject = promiseReject;
  });
  return { promise, reject, resolve };
}

describe("ApplicationBootstrap", () => {
  it("shows startup readiness before the launcher", async () => {
    const readiness = deferred<void>();

    render(
      <ApplicationBootstrap readinessTask={() => readiness.promise}>
        {() => <div>Selected dashboard</div>}
      </ApplicationBootstrap>,
    );

    expect(screen.getByRole("status")).toHaveTextContent("Connecting to platform");
    expect(
      screen.queryByRole("heading", { name: /choose how you enter/i }),
    ).not.toBeInTheDocument();

    await act(async () => readiness.resolve());

    expect(
      await screen.findByRole("heading", { name: /choose how you enter/i }),
    ).toBeInTheDocument();
  });

  it("retries a failed startup check without reloading", async () => {
    const readinessTask = vi
      .fn<() => Promise<void>>()
      .mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValueOnce(undefined);

    render(
      <ApplicationBootstrap readinessTask={readinessTask}>
        {() => <div>Selected dashboard</div>}
      </ApplicationBootstrap>,
    );

    expect(await screen.findByText(/could not connect to the platform/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));

    expect(
      await screen.findByRole("heading", { name: /choose how you enter/i }),
    ).toBeInTheDocument();
    expect(readinessTask).toHaveBeenCalledTimes(2);
  });

  it.each([
    ["Demo", "DEMO"],
    ["Paper", "PAPER"],
  ] as const)("selects %s directly", async (label, mode) => {
    render(
      <ApplicationBootstrap readinessTask={() => Promise.resolve()}>
        {(selectedMode) => <div>{selectedMode} selected</div>}
      </ApplicationBootstrap>,
    );

    fireEvent.click(await screen.findByRole("button", { name: new RegExp(label, "i") }));

    expect(screen.getByText(`${mode} selected`)).toBeInTheDocument();
  });

  it("requires confirmation for Live and restores focus when canceled", async () => {
    render(
      <ApplicationBootstrap readinessTask={() => Promise.resolve()}>
        {(selectedMode) => <div>{selectedMode} selected</div>}
      </ApplicationBootstrap>,
    );

    const liveTrigger = await screen.findByRole("button", { name: /Live/i });
    fireEvent.click(liveTrigger);

    const dialog = screen.getByRole("dialog", { name: "Enter the live-data environment?" });
    expect(screen.getByText(/Data environment: LIVE/i)).toBeInTheDocument();
    expect(screen.getByText(/Execution authority: LOCKED/i)).toBeInTheDocument();
    expect(screen.queryByText("LIVE selected")).not.toBeInTheDocument();

    fireEvent.keyDown(dialog, { key: "Escape" });

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(liveTrigger).toHaveFocus();
  });

  it("enters Live only after explicit confirmation", async () => {
    render(
      <ApplicationBootstrap readinessTask={() => Promise.resolve()}>
        {(selectedMode) => <div>{selectedMode} selected</div>}
      </ApplicationBootstrap>,
    );

    fireEvent.click(await screen.findByRole("button", { name: /Live/i }));
    fireEvent.click(screen.getByRole("button", { name: "Enter live data" }));

    expect(screen.getByText("LIVE selected")).toBeInTheDocument();
  });

  it("traps focus inside the Live confirmation", async () => {
    render(
      <ApplicationBootstrap readinessTask={() => Promise.resolve()}>
        {() => <div>Selected dashboard</div>}
      </ApplicationBootstrap>,
    );

    fireEvent.click(await screen.findByRole("button", { name: /Live/i }));
    const dialog = screen.getByRole("dialog");
    const goBack = screen.getByRole("button", { name: "Go back" });
    const enter = screen.getByRole("button", { name: "Enter live data" });
    expect(goBack).toHaveFocus();

    fireEvent.keyDown(dialog, { key: "Tab", shiftKey: true });

    expect(enter).toHaveFocus();
  });
});
