import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ExitPlatformButton } from "./ExitPlatformButton";

function respond(body: unknown, ok = true) {
  return Promise.resolve(new Response(JSON.stringify(body), { status: ok ? 202 : 500, headers: { "Content-Type": "application/json" } }));
}

describe("ExitPlatformButton", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("asks once, posts stop, then shows the stopped notice", async () => {
    const fetchMock = vi.fn((_path: string, _init?: RequestInit) => respond({ operation_id: "op-stop", status: "QUEUED" }));
    vi.stubGlobal("fetch", fetchMock);
    render(<ExitPlatformButton />);

    fireEvent.click(screen.getByRole("button", { name: "Exit" }));
    expect(fetchMock).not.toHaveBeenCalled();
    expect(screen.getByText("Stop the platform?")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Stop" }));

    await waitFor(() => expect(screen.getByRole("alertdialog", { name: "Platform stopped" })).toBeInTheDocument());
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [path, init] = fetchMock.mock.calls[0];
    expect(path).toBe("/operator/lifecycle/actions");
    expect(JSON.parse(String(init?.body))).toEqual({ action: "stop" });
  });

  it("cancel leaves the platform running", () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    render(<ExitPlatformButton />);
    fireEvent.click(screen.getByRole("button", { name: "Exit" }));
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.getByRole("button", { name: "Exit" })).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("offers a retry when the stop request fails", async () => {
    vi.stubGlobal("fetch", vi.fn(() => respond({ error: "down" }, false)));
    render(<ExitPlatformButton />);
    fireEvent.click(screen.getByRole("button", { name: "Exit" }));
    fireEvent.click(screen.getByRole("button", { name: "Stop" }));
    await waitFor(() => expect(screen.getByText("Stop failed. Retry?")).toBeInTheDocument());
  });
});
