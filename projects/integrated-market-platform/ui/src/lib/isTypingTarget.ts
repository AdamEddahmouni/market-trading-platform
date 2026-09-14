const TYPING_TAGS = new Set(["INPUT", "TEXTAREA", "SELECT"]);

export function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  if (target.isContentEditable) return true;
  if (TYPING_TAGS.has(target.tagName)) return true;
  return Boolean(target.closest("[contenteditable='true'], [role='combobox']"));
}
