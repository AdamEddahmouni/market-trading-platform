import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { OperatorActionDescriptor } from "../../state/operatorAction";
import { OperatorActionButton } from "./OperatorActionButton";

function action(overrides: Partial<OperatorActionDescriptor> = {}): OperatorActionDescriptor {
  return {
    id: "platform.example",
    domain: "platform.lifecycle",
    title: "Restart platform",
    availability: "AVAILABLE",
    consequence: "local_workstation",
    ...overrides,
  };
}

describe("OperatorActionButton", () => {
  it("runs an available action from the button", () => {
    const onActivate = vi.fn();
    render(<OperatorActionButton action={action()} onActivate={onActivate} />);
    const button = screen.getByRole("button", { name: "Restart platform" });
    fireEvent.click(button);
    expect(onActivate).toHaveBeenCalledTimes(1);
    expect(button.tagName).toBe("BUTTON");
  });

  it("explains a blocked action and does not run it", () => {
    const onActivate = vi.fn();
    render(
      <OperatorActionButton
        action={action({
          availability: "BLOCKED",
          reason: { code: "UPDATE_NOT_AVAILABLE", detail: "A fast-forward update must be available." },
        })}
        onActivate={onActivate}
      />,
    );
    const button = screen.getByRole("button", { name: "Restart platform" });
    expect(button).toBeDisabled();
    expect(button).toHaveAccessibleDescription(/fast-forward update must be available/);
    expect(screen.getByText("UPDATE_NOT_AVAILABLE")).toBeInTheDocument();
    fireEvent.click(button);
    expect(onActivate).not.toHaveBeenCalled();
  });

  it("explains unavailable and read-only actions, including a missing reason", () => {
    const { rerender } = render(
      <OperatorActionButton
        action={action({ availability: "UNAVAILABLE" })}
        onActivate={vi.fn()}
      />,
    );
    expect(screen.getByText(/No reason was reported/)).toBeInTheDocument();
    rerender(
      <OperatorActionButton
        action={action({
          availability: "READ_ONLY",
          reason: { code: "MODE_READ_ONLY", detail: "Demo replay does not change this workstation." },
        })}
        onActivate={vi.fn()}
      />,
    );
    expect(screen.getByText(/Demo replay does not change this workstation/)).toBeInTheDocument();
    expect(screen.getByText("MODE_READ_ONLY")).toBeInTheDocument();
  });

  it("confirms, cancels, and restores focus", () => {
    const onActivate = vi.fn();
    render(
      <OperatorActionButton
        action={action({
          confirmation: {
            title: "Confirm platform restart",
            confirmLabel: "Confirm restart",
            cancelLabel: "Cancel",
            facts: [{ label: "Target", value: "This workstation" }],
          },
        })}
        onActivate={onActivate}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Restart platform" }));
    const confirm = screen.getByRole("button", { name: "Confirm restart" });
    expect(confirm).toHaveFocus();
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onActivate).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Restart platform" })).toHaveFocus();
  });

  it("cancels confirmation with Escape", () => {
    const onActivate = vi.fn();
    render(
      <OperatorActionButton
        action={action({
          confirmation: {
            title: "Confirm platform restart",
            confirmLabel: "Confirm restart",
            cancelLabel: "Cancel",
            facts: [{ label: "Target", value: "This workstation" }],
          },
        })}
        onActivate={onActivate}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Restart platform" }));
    fireEvent.keyDown(screen.getByRole("group", { name: "Confirm platform restart" }), { key: "Escape" });
    expect(onActivate).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Restart platform" })).toHaveFocus();
  });

  it("runs once after confirmation and ignores a second click while pending", async () => {
    let resolveRun: (() => void) | undefined;
    const onActivate = vi.fn(
      () =>
        new Promise<void>((resolve) => {
          resolveRun = resolve;
        }),
    );
    const { rerender } = render(
      <OperatorActionButton
        action={action({
          confirmation: {
            title: "Confirm update",
            confirmLabel: "Confirm apply and restart",
            cancelLabel: "Cancel",
            facts: [{ label: "Target", value: "This workstation" }],
          },
        })}
        onActivate={onActivate}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Restart platform" }));
    const confirm = screen.getByRole("button", { name: "Confirm apply and restart" });
    fireEvent.click(confirm);
    fireEvent.click(confirm);
    expect(onActivate).toHaveBeenCalledTimes(1);
    rerender(
      <OperatorActionButton
        action={action()}
        pending
        onActivate={onActivate}
        result={{ kind: "RESULT_UNVERIFIED", message: "restart queued." }}
      />,
    );
    const pendingButton = screen.getByRole("button", { name: "Working…" });
    expect(pendingButton).toHaveAttribute("aria-busy", "true");
    fireEvent.click(pendingButton);
    expect(onActivate).toHaveBeenCalledTimes(1);
    resolveRun?.();
  });

  it("shows request failure and a retry affordance on the same control", () => {
    const onActivate = vi.fn();
    render(
      <OperatorActionButton
        action={action({ title: "Check for updates" })}
        onActivate={onActivate}
        result={{ kind: "REQUEST_FAILED", message: "Could not queue check update." }}
      />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent(/Could not queue check update/);
    fireEvent.click(screen.getByRole("button", { name: "Check for updates" }));
    expect(onActivate).toHaveBeenCalledTimes(1);
  });
});
