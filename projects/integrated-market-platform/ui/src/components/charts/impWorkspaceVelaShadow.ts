/** Feature gate for workspace Vela shadow chart (not production default). */

export const IMP_WORKSPACE_VELA_SHADOW_QUERY = "imp_vela_shadow";
export const IMP_WORKSPACE_VELA_SHADOW_STORAGE_KEY = "imp.workspace.velaShadow";

export function readWorkspaceVelaShadowEnabled(): boolean {
  if (typeof window === "undefined") return false;
  const params = new URLSearchParams(window.location.search);
  const query = params.get(IMP_WORKSPACE_VELA_SHADOW_QUERY);
  if (query === "1" || query === "true") return true;
  if (query === "0" || query === "false") return false;
  return window.localStorage.getItem(IMP_WORKSPACE_VELA_SHADOW_STORAGE_KEY) === "true";
}

export function persistWorkspaceVelaShadowEnabled(enabled: boolean): void {
  if (typeof window === "undefined") return;
  if (enabled) {
    window.localStorage.setItem(IMP_WORKSPACE_VELA_SHADOW_STORAGE_KEY, "true");
  } else {
    window.localStorage.removeItem(IMP_WORKSPACE_VELA_SHADOW_STORAGE_KEY);
  }
}
