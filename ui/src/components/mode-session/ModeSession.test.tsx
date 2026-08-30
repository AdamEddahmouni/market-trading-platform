import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ApplicationBootstrap } from "./ApplicationBootstrap";
import { ModePlaceholderDashboard } from "./ModePlaceholderDashboard";
import type { Mode } from "./types";

function deferred<T>() {
  let resolve!: (value: T | PromiseLike<T>) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

type TestApplicationProps = {
  readinessTask: () => Promise<void>;
};

function TestApplication({ readinessTask }: TestApplicationProps) {
  return (
    <ApplicationBootstrap readinessTask={readinessTask}>
      {() => <div>Environment ready</div>}
    </ApplicationBootstrap>
  );
}

type ReadyTestApplicationProps = {
  modeReadinessTask?: (mode: Mode) => Promise<void>;
};

function ReadyTestApplication({
  modeReadinessTask = () => new Promise<void>(() => undefined),
}: ReadyTestApplicationProps = {}) {
  return (
    <ApplicationBootstrap
      readinessTask={async () => undefined}
      modeReadinessTask={modeReadinessTask}
    >
      {(mode, switchMode) => (
        <ModePlaceholderDashboard mode={mode} onSwitchMode={switchMode} />
      )}
    </ApplicationBootstrap>
  );
}

function modeTitle(mode: Mode) {
  return mode === "DEMO" ? "Demo" : mode === "PAPER" ? "Paper" : "Live";
}

async function selectMode(mode: Mode) {
  fireEvent.click(await screen.findByRole("button", { name: new RegExp(modeTitle(mode), "i") }));
  if (mode === "LIVE") {
    fireEvent.click(screen.getByRole("button", { name: "Enter live data" }));
  }
}

describe("Mode session", () => {
  it("shows startup readiness before the launcher", async () => {
    const readiness = deferred<void>();
    render(<TestApplication readinessTask={() => readiness.promise} />);

    expect(screen.getByRole("status")).toHaveTextContent("Connecting to platform");
    expect(
      screen.queryByRole("heading", { name: /choose how you enter/i }),
    ).not.toBeInTheDocument();

    readiness.resolve();

    expect(
      await screen.findByRole("heading", { name: /choose how you enter/i }),
    ).toBeInTheDocument();
  });

  it("retries a failed startup check without reloading", async () => {
    const readinessTask = vi
      .fn()
      .mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValueOnce(undefined);
    render(<TestApplication readinessTask={readinessTask} />);

    expect(await screen.findByText(/could not connect to the platform/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));

    expect(
      await screen.findByRole("heading", { name: /choose how you enter/i }),
    ).toBeInTheDocument();
    expect(readinessTask).toHaveBeenCalledTimes(2);
  });

  it.each(["Demo", "Paper"])("enters the %s transition directly", async (label) => {
    render(<ReadyTestApplication />);

    fireEvent.click(await screen.findByRole("button", { name: new RegExp(label, "i") }));

    expect(await screen.findByRole("status")).toHaveTextContent(
      new RegExp(`Preparing ${label}`, "i"),
    );
  });

  it("requires explicit confirmation for read-only Live and restores focus on cancel", async () => {
    render(<ReadyTestApplication />);

    const live = await screen.findByRole("button", { name: /Live/i });
    fireEvent.click(live);

    const dialog = screen.getByRole("dialog", { name: "Enter the live-data environment?" });
    expect(within(dialog).getByText(/Execution authority: LOCKED/i)).toBeInTheDocument();
    expect(screen.queryByText("Live environment ready")).not.toBeInTheDocument();

    fireEvent.keyDown(dialog, { key: "Escape" });

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(live).toHaveFocus();
  });

  it("traps focus within the Live confirmation", async () => {
    render(<ReadyTestApplication />);
    fireEvent.click(await screen.findByRole("button", { name: /Live/i }));

    const dialog = screen.getByRole("dialog", { name: "Enter the live-data environment?" });
    const goBack = within(dialog).getByRole("button", { name: "Go back" });
    const enterLive = within(dialog).getByRole("button", { name: "Enter live data" });
    expect(goBack).toHaveFocus();

    fireEvent.keyDown(dialog, { key: "Tab", shiftKey: true });
    expect(enterLive).toHaveFocus();
    fireEvent.keyDown(dialog, { key: "Tab" });
    expect(goBack).toHaveFocus();
  });

  it("renders mode cards with explicit non-color labels", async () => {
    render(<ReadyTestApplication />);

    expect(
      await screen.findByRole("button", { name: /Demo.*Historical replay/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Paper.*Simulated execution/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Live.*Read-only market data/i }),
    ).toBeInTheDocument();
  });

  it("announces transition changes politely", async () => {
    render(<ReadyTestApplication />);

    await selectMode("DEMO");

    expect(screen.getByRole("status")).toHaveAttribute("aria-live", "polite");
  });

  it.each(["DEMO", "PAPER", "LIVE"] as const)(
    "shows the %s placeholder and switches mode",
    async (mode) => {
      render(<ReadyTestApplication modeReadinessTask={async () => undefined} />);

      await selectMode(mode);

      expect(
        await screen.findByRole("heading", { name: `${modeTitle(mode)} environment ready` }),
      ).toBeInTheDocument();
      fireEvent.click(screen.getByRole("button", { name: "Switch mode" }));
      expect(
        await screen.findByRole("heading", { name: /choose how you enter/i }),
      ).toBeInTheDocument();
    },
  );

  it("keeps a failed mode visible and supports retry", async () => {
    const modeReadinessTask = vi
      .fn()
      .mockRejectedValueOnce(new Error("unavailable"))
      .mockResolvedValueOnce(undefined);
    render(<ReadyTestApplication modeReadinessTask={modeReadinessTask} />);

    await selectMode("PAPER");

    expect(await screen.findByText(/could not prepare Paper/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(
      await screen.findByRole("heading", { name: "Paper environment ready" }),
    ).toBeInTheDocument();
    expect(modeReadinessTask).toHaveBeenCalledTimes(2);
  });

  it("does not remember a mode across mounts", async () => {
    const first = render(
      <ReadyTestApplication modeReadinessTask={async () => undefined} />,
    );
    await selectMode("DEMO");
    expect(
      await screen.findByRole("heading", { name: "Demo environment ready" }),
    ).toBeInTheDocument();

    first.unmount();
    render(<ReadyTestApplication modeReadinessTask={async () => undefined} />);

    expect(
      await screen.findByRole("heading", { name: /choose how you enter/i }),
    ).toBeInTheDocument();
  });

  it("requires Live confirmation again after switching modes", async () => {
    render(<ReadyTestApplication modeReadinessTask={async () => undefined} />);
    await selectMode("LIVE");
    expect(
      await screen.findByRole("heading", { name: "Live environment ready" }),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Switch mode" }));
    fireEvent.click(await screen.findByRole("button", { name: /Live/i }));

    expect(
      screen.getByRole("dialog", { name: "Enter the live-data environment?" }),
    ).toBeInTheDocument();
  });
});
