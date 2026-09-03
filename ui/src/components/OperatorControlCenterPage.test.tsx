import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { OperatorControlCenterPage } from "./OperatorControlCenterPage";

function response(payload: unknown, ok = true) {
  return Promise.resolve({ ok, json: async () => payload });
}

describe("OperatorControlCenterPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const path = String(input);
        if (path.includes("/operator/lifecycle/status")) {
          return response({ status: "READY", services: [], logs: [] });
        }
        if (path.includes("/operator/readiness")) {
          return response({
            status: "ACTION_REQUIRED",
            checks: [{ id: "python", label: "Python 3.11", status: "PASS", detail: "Ready", required: true }],
            providers: [
              {
                provider: "moomoo_observational",
                label: "Moomoo observational",
                credential_state: "NOT_REQUIRED",
                gate_state: "ENABLED",
                transport_state: "UNAVAILABLE",
                next_action: "Start OpenD",
              },
            ],
          });
        }
        if (path.includes("/operator/config")) {
          return response({ providers: [] });
        }
        return response({});
      }),
    );
  });

  it("shows setup readiness and provider next actions", async () => {
    render(
      <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <OperatorControlCenterPage />
      </MemoryRouter>,
    );

    expect(await screen.findByRole("heading", { name: "Operator center" })).toBeInTheDocument();
    expect(screen.getByText(/Start OpenD/)).toBeInTheDocument();
    expect(screen.getByText("Python 3.11")).toBeInTheDocument();
  });

  it("requests an explicit provider refresh", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      if (String(input).includes("/operator/lifecycle/status")) {
        return response({ status: "READY", services: [], logs: [] });
      }
      if (String(input).includes("/operator/readiness")) {
        return response({
          status: "READY",
          checks: [],
          providers: [
            {
              provider: "finviz",
              label: "Finviz discovery",
              credential_state: "CONFIGURED",
              gate_state: "ENABLED",
              transport_state: "READY",
              next_action: "Ready",
            },
          ],
        });
      }
      if (String(input).includes("/operator/config")) return response({ providers: [] });
      if (String(input).includes("/operator/providers/finviz/refresh")) {
        expect(init?.method).toBe("POST");
        return response({ operation_id: "op-1", status: "QUEUED" });
      }
      return response({});
    });

    render(
      <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <OperatorControlCenterPage />
      </MemoryRouter>,
    );

    fireEvent.click(await screen.findByRole("button", { name: "Refresh Finviz discovery" }));
    await waitFor(() => expect(screen.getByText(/Refresh queued/)).toBeInTheDocument());
  });
});
