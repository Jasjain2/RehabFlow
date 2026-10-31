import type { HistoryEntry, RehabPlan, SessionReport, SuggestedPlan, UserProfile } from './types';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  });
  if (!res.ok) {
    const body = await res.text();
    throw new ApiError(res.status, body || res.statusText);
  }
  return res.json() as Promise<T>;
}

function post<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, { method: 'POST', body: JSON.stringify(body) });
}

export function createSession(userId: string): Promise<{ session_id: string }> {
  return post('/api/session', { user_id: userId });
}

export function saveProfile(sessionId: string, profile: UserProfile): Promise<void> {
  return post('/api/profile', { session_id: sessionId, ...profile });
}

export function generatePlan(sessionId: string): Promise<RehabPlan> {
  return post('/api/plan/generate', { session_id: sessionId });
}

/** The adjusted plan from the user's last session, or null if there isn't one */
export async function getSuggestedPlan(userId: string): Promise<SuggestedPlan | null> {
  try {
    return await request<SuggestedPlan>(`/api/plan/suggested/${userId}`);
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) return null;
    throw err;
  }
}

/** New session reusing the last session's profile and its suggested plan */
export function createSessionFromSuggested(userId: string): Promise<{ session_id: string }> {
  return post('/api/session/from-suggested', { user_id: userId });
}

export function getPlan(sessionId: string): Promise<RehabPlan> {
  return request(`/api/plan/${sessionId}`);
}

export function finishSession(sessionId: string): Promise<SessionReport> {
  return post('/api/exercise/finish', { session_id: sessionId });
}

export function getReport(sessionId: string): Promise<SessionReport> {
  return request(`/api/report/${sessionId}`);
}

export function getHistory(userId: string): Promise<HistoryEntry[]> {
  return request(`/api/history/${userId}`);
}

export function connectExerciseStream(sessionId: string): WebSocket {
  const wsUrl = API_URL.replace(/^http/, 'ws');
  return new WebSocket(`${wsUrl}/api/exercise/stream?session_id=${encodeURIComponent(sessionId)}`);
}
