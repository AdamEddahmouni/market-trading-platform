import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "../../App";
import { ApplicationBootstrap } from "./ApplicationBootstrap";
import { ModePlaceholderDashboard } from "./ModePlaceholderDashboard";

function deferred<T>() {
  let resolve!: (value: T | PromiseLike<T>) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((promiseResolve, promiseReject) => {
    resolve = promiseResolve;
    reject = promiseReject;
  });
  return { promise, reject, resolve };
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("ApplicationBootstrap", () => {
  it("uses platform context as the default startup readiness boundary", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <ApplicationBootstrap>{(mode) => <div>{mode} selected</div>}</ApplicationBootstrap>,
    );

    expect(
      await screen.findByRole("heading", { name: /choose how you enter/i }),
    ).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith("/context", {
      headers: { Accept: "application/json" },
    });
  });

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

  it("tracks completed, active, and pending startup stages", () => {
    const readiness = deferred<void>();
    render(
      <ApplicationBootstrap readinessTask={() => readiness.promise}>
        {() => <div>Selected dashboard</div>}
      </ApplicationBootstrap>,
    );

    expect(screen.getByText("Starting interface").closest("li")).toHaveAttribute(
      "data-state",
      "complete",
    );
    expect(screen.getByText("Connecting to platform").closest("li")).toHaveAttribute(
      "data-state",
      "active",
    );
    expect(screen.getByText("Checking environment readiness").closest("li")).toHaveAttribute(
      "data-state",
      "pending",
    );
    expect(screen.getByText("Ready").closest("li")).toHaveAttribute("data-state", "pending");
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

    expect(await screen.findByText(`${mode} selected`)).toBeInTheDocument();
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

    expect(await screen.findByText("LIVE selected")).toBeInTheDocument();
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

  it("locks background scrolling while the Live confirmation is open", async () => {
    render(
      <ApplicationBootstrap readinessTask={() => Promise.resolve()}>
        {() => <div>Selected dashboard</div>}
      </ApplicationBootstrap>,
    );

    fireEvent.click(await screen.findByRole("button", { name: /Live/i }));
    expect(document.body.style.overflow).toBe("hidden");

    fireEvent.click(screen.getByRole("button", { name: "Go back" }));
    expect(document.body.style.overflow).toBe("");
  });

  it("shows honest mode readiness until the selected environment resolves", async () => {
    const modeReadiness = deferred<void>();
    render(
      <ApplicationBootstrap
        readinessTask={() => Promise.resolve()}
        modeReadinessTask={() => modeReadiness.promise}
      >
        {(selectedMode) => <div>{selectedMode} selected</div>}
      </ApplicationBootstrap>,
    );

    fireEvent.click(await screen.findByRole("button", { name: /Demo/i }));

    expect(screen.getByRole("status")).toHaveTextContent("Preparing Demo");
    expect(screen.queryByText("DEMO selected")).not.toBeInTheDocument();

    await act(async () => modeReadiness.resolve());

    expect(screen.getByText("DEMO selected")).toBeInTheDocument();
  });

  it("retries a failed mode transition without reloading", async () => {
    const modeReadinessTask = vi
      .fn<() => Promise<void>>()
      .mockRejectedValueOnce(new Error("unavailable"))
      .mockResolvedValueOnce(undefined);
    render(
      <ApplicationBootstrap
        readinessTask={() => Promise.resolve()}
        modeReadinessTask={modeReadinessTask}
      >
        {(selectedMode) => <div>{selectedMode} selected</div>}
      </ApplicationBootstrap>,
    );

    fireEvent.click(await screen.findByRole("button", { name: /Paper/i }));
    expect(await screen.findByText(/could not prepare Paper/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Retry" }));

    expect(await screen.findByText("PAPER selected")).toBeInTheDocument();
    expect(modeReadinessTask).toHaveBeenCalledTimes(2);
  });

  it("returns from a failed transition to a fresh mode selection", async () => {
    render(
      <ApplicationBootstrap
        readinessTask={() => Promise.resolve()}
        modeReadinessTask={() => Promise.reject(new Error("unavailable"))}
      >
        {(selectedMode) => <div>{selectedMode} selected</div>}
      </ApplicationBootstrap>,
    );

    fireEvent.click(await screen.findByRole("button", { name: /Demo/i }));
    expect(await screen.findByText(/could not prepare Demo/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Return to mode selection" }));

    expect(
      await screen.findByRole("heading", { name: /choose how you enter/i }),
    ).toBeInTheDocument();
  });

  it.each(["Demo", "Paper", "Live"] as const)(
    "switches from the %s destination to a fresh launcher",
    async (label) => {
      render(
        <ApplicationBootstrap readinessTask={() => Promise.resolve()}>
          {(mode, switchMode) => (
            <ModePlaceholderDashboard mode={mode} onSwitchMode={switchMode} />
          )}
        </ApplicationBootstrap>,
      );

      fireEvent.click(await screen.findByRole("button", { name: new RegExp(label, "i") }));
      if (label === "Live") {
        fireEvent.click(screen.getByRole("button", { name: "Enter live data" }));
      }
      expect(
        await screen.findByRole("heading", { name: `${label} environment ready` }),
      ).toBeInTheDocument();

      fireEvent.click(screen.getByRole("button", { name: "Switch mode" }));

      expect(
        await screen.findByRole("heading", { name: /choose how you enter/i }),
      ).toBeInTheDocument();
    },
  );

  it("requires Live confirmation again after switching modes", async () => {
    render(
      <ApplicationBootstrap readinessTask={() => Promise.resolve()}>
        {(mode, switchMode) => <ModePlaceholderDashboard mode={mode} onSwitchMode={switchMode} />}
      </ApplicationBootstrap>,
    );

    fireEvent.click(await screen.findByRole("button", { name: /Live/i }));
    fireEvent.click(screen.getByRole("button", { name: "Enter live data" }));
    await screen.findByRole("heading", { name: "Live environment ready" });
    fireEvent.click(screen.getByRole("button", { name: "Switch mode" }));
    fireEvent.click(await screen.findByRole("button", { name: /Live/i }));

    expect(
      screen.getByRole("dialog", { name: "Enter the live-data environment?" }),
    ).toBeInTheDocument();
  });

  it("does not remember a selected mode across mounts", async () => {
    const firstMount = render(
      <ApplicationBootstrap readinessTask={() => Promise.resolve()}>
        {(mode) => <div>{mode} selected</div>}
      </ApplicationBootstrap>,
    );
    fireEvent.click(await screen.findByRole("button", { name: /Demo/i }));
    await screen.findByText("DEMO selected");
    firstMount.unmount();

    render(
      <ApplicationBootstrap readinessTask={() => Promise.resolve()}>
        {(mode) => <div>{mode} selected</div>}
      </ApplicationBootstrap>,
    );

    expect(
      await screen.findByRole("heading", { name: /choose how you enter/i }),
    ).toBeInTheDocument();
  });
});

describe("ModePlaceholderDashboard", () => {
  it.each([
    ["DEMO", "Demo environment ready", "Historical replay · No execution"],
    ["PAPER", "Paper environment ready", "Simulated orders · No live execution"],
    ["LIVE", "Live environment ready", "Current market data · Execution authority locked"],
  ] as const)("renders and exits the %s destination", (mode, heading, boundary) => {
    const onSwitchMode = vi.fn();
    render(<ModePlaceholderDashboard mode={mode} onSwitchMode={onSwitchMode} />);

    expect(screen.getByRole("heading", { name: heading })).toBeInTheDocument();
    expect(screen.getByText(boundary)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Switch mode" }));

    expect(onSwitchMode).toHaveBeenCalledOnce();
  });
});

describe("App mode gate", () => {
  it("opens on the launcher instead of the workstation shell", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({}) }),
    );

    render(<App />);

    expect(
      await screen.findByRole("heading", { name: /choose how you enter/i }),
    ).toBeInTheDocument();
    expect(screen.queryByText(/API unavailable/i)).not.toBeInTheDocument();
  });
});
