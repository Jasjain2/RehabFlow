import { EXERCISE_LABELS } from '@/lib/format';
import type { Exercise } from '@/lib/types';

export default function PlanCard({ exercise }: { exercise: Exercise }) {
  return (
    <article className="rounded-lg border border-slate-200 bg-white p-5">
      <header className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-lg font-semibold">{EXERCISE_LABELS[exercise.name]}</h2>
        <p className="text-sm text-slate-600">
          <span className="font-medium tabular-nums text-slate-900">
            {exercise.sets} × {exercise.reps_per_set}
          </span>{' '}
          · {exercise.rest_seconds}s rest
        </p>
      </header>

      {exercise.coaching_cues.length > 0 && (
        <section className="mt-4">
          <h3 className="text-sm font-medium text-slate-700">Coaching cues</h3>
          <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-slate-700">
            {exercise.coaching_cues.map((cue) => (
              <li key={cue}>{cue}</li>
            ))}
          </ul>
        </section>
      )}

      {exercise.safety_warnings.length > 0 && (
        <section className="mt-4 rounded-md bg-amber-50 p-3">
          <h3 className="text-sm font-medium text-amber-900">Safety</h3>
          <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-amber-900">
            {exercise.safety_warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </section>
      )}
    </article>
  );
}
