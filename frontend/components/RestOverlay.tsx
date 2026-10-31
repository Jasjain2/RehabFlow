import type { ExerciseUpdate } from '@/lib/types';

interface Props {
  update: ExerciseUpdate;
  onSkip: () => void;
}

export default function RestOverlay({ update, onSkip }: Props) {
  return (
    <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 rounded-lg bg-slate-900/85 p-6 text-center text-white">
      <p className="text-sm text-slate-300">
        Set {update.set_number} of {update.total_sets} complete
      </p>
      <p className="text-6xl font-semibold tabular-nums">{update.rest_seconds_remaining ?? 0}s</p>
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
