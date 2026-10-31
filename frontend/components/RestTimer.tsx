import type { ExerciseUpdate } from '@/lib/types';

interface Props {
  update: ExerciseUpdate;
  /** Planned rest for this exercise, for the progress bar */
  restSeconds: number;
  onSkip: () => void;
}

/** Countdown between sets. The server ends the rest when it reaches zero; Skip ends it early. */
export default function RestTimer({ update, restSeconds, onSkip }: Props) {
  const remaining = update.rest_seconds_remaining ?? 0;
  const elapsed = restSeconds > 0 ? Math.min(1, 1 - remaining / restSeconds) : 1;
  return (
    <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 rounded-lg bg-slate-900/85 p-6 text-center text-white">
      <p className="text-sm text-slate-300">
        Set {update.set_number} of {update.total_sets} complete
      </p>
      <p aria-live="polite">
        <span className="text-6xl font-semibold tabular-nums">{remaining}</span>
        <span className="ml-2 text-slate-300">seconds of rest remaining</span>
      </p>
      <div className="h-1.5 w-full max-w-xs overflow-hidden rounded-full bg-white/20">
        <div className="h-full rounded-full bg-teal-400" style={{ width: `${elapsed * 100}%` }} />
      </div>
      <div className="min-h-[4.5rem] max-w-md text-sm leading-relaxed">
        {update.set_coaching ? (
          <p>{update.set_coaching}</p>
        ) : (
          <p className="animate-pulse text-slate-400">Analyzing your set…</p>
        )}
      </div>
      <button
        onClick={onSkip}
        className="rounded-md border border-white/40 px-4 py-1.5 text-sm font-medium hover:bg-white/10"
      >
        Skip Rest
      </button>
    </div>
  );
}
