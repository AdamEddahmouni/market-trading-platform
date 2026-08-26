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
});
