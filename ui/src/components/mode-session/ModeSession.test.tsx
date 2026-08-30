import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ApplicationBootstrap } from "./ApplicationBootstrap";

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

function ReadyTestApplication() {
  return (
    <ApplicationBootstrap
      readinessTask={async () => undefined}
      modeReadinessTask={() => new Promise<void>(() => undefined)}
    >
      {() => <div>Environment ready</div>}
    </ApplicationBootstrap>
  );
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
});
