/**
 * Control-page adapters from authoritative lifecycle/provider state onto
 * OperatorActionDescriptor. These functions do not call the network.
 */
import type { OperatorLifecycleStatus, ProviderReadiness } from "../../api/schemas";
import type { OperatorActionDescriptor } from "../../state/operatorAction";

export type LifecycleSnapshot = {
  loading: boolean;
  failed: boolean;
  lifecycle?: OperatorLifecycleStatus;
};

const LOCAL_UNTOUCHED = "Trading authority is unchanged. Live execution remains locked.";

function lifecycleUnavailable(snapshot: LifecycleSnapshot): OperatorActionDescriptor["reason"] {
  if (snapshot.loading) {
    return {
      code: "LIFECYCLE_STATUS_UNAVAILABLE",
      detail: "Platform runtime status is still loading.",
    };
  }
  return {
    code: "LIFECYCLE_STATUS_UNAVAILABLE",
    detail: "Platform runtime status could not be loaded.",
  };
}

export function restartPlatformAction(snapshot: LifecycleSnapshot): OperatorActionDescriptor {
  if (snapshot.loading || snapshot.failed || !snapshot.lifecycle) {
    return {
      id: "platform.restart",
      domain: "platform.lifecycle",
      title: "Restart platform",
      availability: "UNAVAILABLE",
      reason: lifecycleUnavailable(snapshot),
      consequence: "local_workstation",
      target: { label: "This workstation" },
    };
  }
  const runtime = snapshot.lifecycle.status;
  return {
    id: "platform.restart",
    domain: "platform.lifecycle",
    title: "Restart platform",
    description: "Queues a restart of local platform services.",
    availability: "AVAILABLE",
    consequence: "local_workstation",
    target: { label: "This workstation" },
    confirmation: {
      title: "Confirm platform restart",
      confirmLabel: "Confirm restart",
      cancelLabel: "Cancel",
      facts: [
        { label: "What will change", value: "Local platform services are restarted." },
        { label: "Target", value: "This workstation" },
        { label: "Current runtime", value: runtime },
        { label: "Unchanged", value: LOCAL_UNTOUCHED },
      ],
    },
  };
}

export function checkUpdateAction(snapshot: LifecycleSnapshot): OperatorActionDescriptor {
  if (snapshot.loading || snapshot.failed || !snapshot.lifecycle) {
    return {
      id: "platform.check-update",
      domain: "platform.lifecycle",
      title: "Check for updates",
      availability: "UNAVAILABLE",
      reason: lifecycleUnavailable(snapshot),
      consequence: "none",
      target: { label: "This workstation" },
    };
  }
  return {
    id: "platform.check-update",
    domain: "platform.lifecycle",
    title: "Check for updates",
    description: "Queues a fast-forward update check. Nothing is applied.",
    availability: "AVAILABLE",
    consequence: "none",
    target: { label: "This workstation" },
  };
}

export function applyUpdateAction(snapshot: LifecycleSnapshot): OperatorActionDescriptor {
  const base = {
    id: "platform.apply-update",
    domain: "platform.lifecycle",
    title: "Apply fast-forward update",
    consequence: "local_workstation" as const,
    target: { label: "This workstation" },
  };
  if (snapshot.loading || snapshot.failed || !snapshot.lifecycle) {
    return {
      ...base,
      availability: "UNAVAILABLE",
      reason: lifecycleUnavailable(snapshot),
    };
  }
  const update = snapshot.lifecycle.update;
  if (!update?.status) {
    return {
      ...base,
      availability: "UNAVAILABLE",
      reason: {
        code: "UPDATE_STATUS_MISSING",
        detail: "Update status was not included in the platform snapshot.",
      },
    };
  }
  const detail = update.detail?.trim();
  if (update.status === "AVAILABLE") {
    return {
      ...base,
      description: detail || "A fast-forward update is available.",
      availability: "AVAILABLE",
      confirmation: {
        title: "Confirm update",
        confirmLabel: "Confirm apply and restart",
        cancelLabel: "Cancel",
        facts: [
          {
            label: "What will change",
            value: "The local workstation fast-forwards and restarts.",
          },
          { label: "Target", value: "This workstation" },
          { label: "Current update state", value: detail || update.status },
          { label: "Unchanged", value: LOCAL_UNTOUCHED },
        ],
      },
    };
  }
  if (update.status === "CURRENT") {
    return {
      ...base,
      availability: "BLOCKED",
      reason: {
        code: "UPDATE_NOT_AVAILABLE",
        detail: detail || "A fast-forward update must be available.",
      },
    };
  }
  if (update.status === "BLOCKED") {
    return {
      ...base,
      availability: "BLOCKED",
      reason: {
        code: "UPDATE_BLOCKED",
        detail: detail || "The fast-forward update is blocked.",
      },
    };
  }
  if (update.status === "UNAVAILABLE") {
    return {
      ...base,
      availability: "UNAVAILABLE",
      reason: {
        code: "UPDATE_STATUS_UNAVAILABLE",
        detail: detail || "Update status is unavailable.",
      },
    };
  }
  return {
    ...base,
    availability: "UNAVAILABLE",
    reason: {
      code: update.status,
      detail: detail || "Update status is not a known actionable state.",
    },
  };
}

export function providerRefreshAction(provider: ProviderReadiness): OperatorActionDescriptor {
  const label = provider.label ?? provider.provider;
  return {
    id: `platform.provider-refresh.${provider.provider}`,
    domain: "platform.provider",
    title: "Refresh",
    description: `Queues a refresh record for ${label}.`,
    availability: "AVAILABLE",
    consequence: "none",
    target: { label, id: provider.provider },
  };
}

export function reloadControlAction(): OperatorActionDescriptor {
  return {
    id: "platform.reload-status",
    domain: "platform.diagnostics",
    title: "Check again",
    description: "Reloads Control status. This does not restart services.",
    availability: "AVAILABLE",
    consequence: "none",
    target: { label: "This workstation" },
  };
}

/** Credential save stays a form submit. The descriptor never includes field values. */
export function providerConfigSaveAction(label: string): OperatorActionDescriptor {
  return {
    id: `platform.provider-config.${label}`,
    domain: "platform.configuration",
    title: `Save ${label}`,
    description: "Saves credential fields entered in this form.",
    availability: "AVAILABLE",
    consequence: "configuration",
    target: { label },
  };
}
