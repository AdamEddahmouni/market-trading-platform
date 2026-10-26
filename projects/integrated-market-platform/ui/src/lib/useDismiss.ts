import { useEffect, useRef, type RefObject } from "react";

/**
 * Closes a non-modal popover on Escape anywhere in the document, or on a pointer press outside it.
 * Escape is taken in the capture phase so the open popover closes first and nothing underneath
 * (grid selection, search box, preview pane) also reacts to the same key. A press on the trigger is
 * ignored so the trigger's own toggle still closes it. `onClose(true)` means focus should return to
 * the trigger (keyboard); `onClose(false)` leaves focus where the user pressed.
 */
export function useDismiss(
  open: boolean,
  popoverRef: RefObject<HTMLElement | null>,
  triggerRef: RefObject<HTMLElement | null>,
  onClose: (restoreFocus: boolean) => void,
) {
  const close = useRef(onClose);
  close.current = onClose;
  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      event.stopPropagation();
      close.current(true);
    };
    const onPointer = (event: PointerEvent) => {
      const target = event.target as Node | null;
      if (!target || popoverRef.current?.contains(target) || triggerRef.current?.contains(target)) return;
      close.current(false);
    };
    document.addEventListener("keydown", onKey, true);
    document.addEventListener("pointerdown", onPointer, true);
    return () => {
      document.removeEventListener("keydown", onKey, true);
      document.removeEventListener("pointerdown", onPointer, true);
    };
  }, [open, popoverRef, triggerRef]);
}
