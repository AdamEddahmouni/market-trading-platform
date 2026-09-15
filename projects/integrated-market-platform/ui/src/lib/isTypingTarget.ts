const TYPING_TAGS = new Set(["INPUT", "TEXTAREA", "SELECT"]);

function isContentEditable(target: HTMLElement): boolean {
  if (target.isContentEditable) return true;
  const value = target.getAttribute("contenteditable");
  return value === "" || value === "true";
}

export function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  if (isContentEditable(target)) return true;
  if (TYPING_TAGS.has(target.tagName)) return true;
  return Boolean(target.closest("[contenteditable='true'], [contenteditable=''], [role='combobox']"));
}
