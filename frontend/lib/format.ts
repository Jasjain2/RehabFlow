import type { ExerciseName } from './types';

export const EXERCISE_LABELS: Record<ExerciseName, string> = {
  squat: 'Bodyweight Squat',
  push_up: 'Push-up',
};

export function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return `${m}:${s.toString().padStart(2, '0')}`;
}

export function formatPercent(fraction: number): string {
  return `${Math.round(fraction * 100)}%`;
}

/** Tailwind text color for a 0-100 form score: green > 80, yellow > 60, red otherwise */
export function scoreColor(score: number): string {
  if (score > 80) return 'text-emerald-600';
  if (score > 60) return 'text-amber-500';
  return 'text-red-600';
}

export function errorMessage(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}
