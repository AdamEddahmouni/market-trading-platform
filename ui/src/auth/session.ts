const STORAGE_KEY = "imp.session_token";

let memoryToken: string | null = null;

export function getSessionToken(): string | null {
  if (memoryToken) return memoryToken;
  try {
    const stored = sessionStorage.getItem(STORAGE_KEY);
    memoryToken = stored || null;
    return memoryToken;
  } catch {
    return null;
  }
}

export function setSessionToken(token: string | null): void {
  memoryToken = token;
  try {
    if (token) {
      sessionStorage.setItem(STORAGE_KEY, token);
    } else {
      sessionStorage.removeItem(STORAGE_KEY);
    }
  } catch {
    // sessionStorage unavailable — memory-only token still works for this tab.
  }
}

export function authHeaders(): Record<string, string> {
  const token = getSessionToken();
  if (!token) return {};
  return { Authorization: `Bearer ${token}` };
}
