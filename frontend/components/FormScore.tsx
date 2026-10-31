import { scoreColor } from '@/lib/format';

export default function FormScore({ score }: { score: number | null }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-5 text-center">
      <p className="text-sm font-medium text-slate-600">Form score</p>
      {score === null ? (
        <p className="mt-2 text-sm text-slate-500">Step into view of the camera</p>
      ) : (
        <p className={`mt-1 text-6xl font-semibold tabular-nums ${scoreColor(score)}`}>
          {Math.round(score)}
        </p>
      )}
    </div>
  );
}
