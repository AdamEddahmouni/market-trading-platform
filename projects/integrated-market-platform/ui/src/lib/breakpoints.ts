/**
 * The one breakpoint scale (docs/ui-redesign-v2/responsive-contract.md §1).
 * CSS media queries cannot read custom properties, so the scale lives here for
 * JS (matchMedia) and is documented in tokens.css comments.
 */
export const BP_SM = 720;
export const BP_MD = 1024;
export const BP_LG = 1440;

/** Sidebar/drawers are overlay dialogs at or below this width. */
export const OVERLAY_NAV_MAX_PX = BP_MD;
