import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { OperatorSettingsPage } from "./OperatorSettingsPage";

const operatorState = {
  persistence_enabled: true,
  state_dir: "/tmp/imp",
  schema_version: 3,
  watchlists: [{ watchlist_id: "wl-1", name: "Default", items: [{ instrument_id: "BIYA" }] }],
  recent_instruments: [{ instrument_id: "BIYA" }],
  sessions: [{ session_id: "sess-1234567890", status: "OPEN", created_at: 1 }],
  captures: [{ capture_id: "cap-1", status: "AVAILABLE", provider: "INTERNAL" }],
};

const startupState = {
  opend: { operator_message: "Provider ready." },
  restore: "CLEAN",
  crash_recovery: "NONE",
  execution_deferred: false,
};

describe("OperatorSettingsPage", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation(async (input: RequestInfo) => {
        const url = typeof input === "string" ? input : input.url;
        if (url.endsWith("/state/startup")) {
          return { ok: true, json: async () => startupState };
        }
        if (url.endsWith("/operator/state")) {
          return { ok: true, json: async () => operatorState };
        }
        if (url.endsWith("/operator/watchlist")) {
          return { ok: true, json: async () => ({ ok: true }) };
        }
        return { ok: true, json: async () => ({}) };
      }),
    );
  });

  it("shows read-only restriction and hides mutations in Demo mode", async () => {
    render(<OperatorSettingsPage mode="DEMO" />);

    expect(await screen.findByRole("heading", { name: "Settings" })).toBeInTheDocument();
    expect(screen.getByRole("note")).toHaveTextContent(/read-only in DEMO mode/i);
    expect(screen.queryByRole("button", { name: "Add to watchlist" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Reindex captures" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Replay" })).not.toBeInTheDocument();
    expect(screen.getAllByText("BIYA").length).toBeGreaterThan(0);
  });

  it("shows read-only restriction and hides mutations in Live mode", async () => {
    render(<OperatorSettingsPage mode="LIVE" />);

    expect(await screen.findByRole("heading", { name: "Settings" })).toBeInTheDocument();
    expect(screen.getByRole("note")).toHaveTextContent(/read-only in LIVE mode/i);
    expect(screen.queryByRole("button", { name: "Add to watchlist" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Reindex captures" })).not.toBeInTheDocument();
  });

  it("enables operator mutations in Paper mode", async () => {
    render(<OperatorSettingsPage mode="PAPER" />);

    expect(await screen.findByRole("heading", { name: "Settings" })).toBeInTheDocument();
    expect(screen.queryByRole("note")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Add to watchlist" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reindex captures" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Replay" })).toBeInTheDocument();
  });

  it("posts watchlist updates only in Paper mode", async () => {
    const fetchMock = vi.mocked(globalThis.fetch);
    render(<OperatorSettingsPage mode="PAPER" />);
    await screen.findByRole("button", { name: "Add to watchlist" });

    fireEvent.click(screen.getByRole("button", { name: "Add to watchlist" }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/operator/watchlist",
        expect.objectContaining({ method: "POST" }),
      );
    });
  });
});
