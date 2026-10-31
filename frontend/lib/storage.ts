// Browser-side identity and current-session tracking. There are no user accounts,
// so an anonymous ID in localStorage ties sessions together for the history page.

const USER_ID_KEY = 'rehabflow.userId';
const SESSION_ID_KEY = 'rehabflow.sessionId';

function safeGet(storage: Storage, key: string): string | null {
  try {
    return storage.getItem(key);
  } catch {
    return null;
  }
}

function safeSet(storage: Storage, key: string, value: string): void {
  try {
    storage.setItem(key, value);
  } catch {
    // Storage blocked (private mode); the app still works for the current page
  }
}

export function getUserId(): string {
  let id = safeGet(localStorage, USER_ID_KEY);
  if (!id) {
    id = crypto.randomUUID();
    safeSet(localStorage, USER_ID_KEY, id);
  }
  return id;
}

export function getCurrentSessionId(): string | null {
  return safeGet(sessionStorage, SESSION_ID_KEY);
}

export function setCurrentSessionId(id: string): void {
  safeSet(sessionStorage, SESSION_ID_KEY, id);
}
