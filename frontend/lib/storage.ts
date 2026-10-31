// Browser-side identity and current-session tracking. There are no user accounts,
// so an anonymous ID in localStorage ties sessions together for the history page.

const USER_ID_KEY = 'rehabflow.userId';
const SESSION_ID_KEY = 'rehabflow.sessionId';
const DISCLAIMER_KEY = 'rehabflow.disclaimerAcknowledged';

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

/** Acknowledged once per browser session, so the disclaimer shows again on each new visit */
export function isDisclaimerAcknowledged(): boolean {
  return safeGet(sessionStorage, DISCLAIMER_KEY) === 'true';
}

export function acknowledgeDisclaimer(): void {
  safeSet(sessionStorage, DISCLAIMER_KEY, 'true');
}
