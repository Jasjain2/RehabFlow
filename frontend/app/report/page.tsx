'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import NoSession from '@/components/NoSession';
import ReportChart from '@/components/ReportChart';
import { getReport } from '@/lib/api';
import { EXERCISE_LABELS, errorMessage, formatDuration, formatPercent, scoreColor } from '@/lib/format';
import { getCurrentSessionId } from '@/lib/storage';
import type { ExerciseName, RepSummary, SessionReport } from '@/lib/types';

export default function ReportPage() {
  const [sessionId, setSessionId] = useState<string | null | undefined>(undefined);
  const [report, setReport] = useState<SessionReport | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const id = getCurrentSessionId();
    setSessionId(id);
    if (id) getReport(id).then(setReport, (err) => setError(errorMessage(err)));
  }, []);

  if (sessionId === null) return <NoSession />;
  if (error) return <p className="text-red-700">Could not load your report: {error}</p>;
  if (!report) return <p className="text-slate-600">Loading your report…</p>;

  const byExercise = groupByExercise(report.reps);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <h1 className="text-2xl font-semibold">Session report</h1>
        <Link href="/history" className="font-medium text-teal-700 hover:underline">
          View Progress →
        </Link>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Tile label="Reps completed" value={String(report.total_reps)} />
        <Tile
          label="Avg form score"
          value={String(Math.round(report.avg_form_score))}
          valueClass={scoreColor(report.avg_form_score)}
        />
        <Tile label="Max fatigue drift" value={formatPercent(report.max_fatigue_drift)} />
        <Tile label="Duration" value={formatDuration(report.duration_seconds)} />
      </div>

      <section className="flex flex-wrap items-center gap-3 rounded-lg border border-slate-200 bg-white p-5">
        <p className="text-lg font-semibold">+{report.xp_earned} XP</p>
        {report.badges.map((badge) => (
          <span key={badge} className="rounded-full bg-teal-50 px-3 py-1 text-sm font-medium text-teal-800">
            🏅 {badge}
          </span>
        ))}
        {report.fatigue_alerts_count > 0 && (
          <p className="text-sm text-slate-600">
            {report.fatigue_alerts_count} fatigue alert{report.fatigue_alerts_count === 1 ? '' : 's'}
          </p>
        )}
      </section>

      {byExercise.length === 0 && (
        <p className="text-slate-600">No reps were recorded in this session.</p>
      )}
      {byExercise.map(([exercise, reps]) => (
        <section key={exercise} className="rounded-lg border border-slate-200 bg-white p-5">
          <header className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
            <h2 className="text-lg font-semibold">{EXERCISE_LABELS[exercise]}</h2>
            <p className="text-sm text-slate-600">
              {reps.length} reps · avg score{' '}
              <span className="font-medium tabular-nums text-slate-900">{Math.round(average(reps))}</span>
            </p>
          </header>
          <ReportChart reps={reps} />
        </section>
      ))}
    </div>
  );
}

function groupByExercise(reps: RepSummary[]): [ExerciseName, RepSummary[]][] {
  const groups = new Map<ExerciseName, RepSummary[]>();
  for (const rep of reps) groups.set(rep.exercise, [...(groups.get(rep.exercise) ?? []), rep]);
  return [...groups.entries()];
}

function average(reps: RepSummary[]): number {
  return reps.reduce((sum, r) => sum + r.form_score, 0) / reps.length;
}

function Tile({ label, value, valueClass = '' }: { label: string; value: string; valueClass?: string }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <p className="text-xs text-slate-500">{label}</p>
      <p className={`mt-1 text-2xl font-semibold tabular-nums ${valueClass}`}>{value}</p>
    </div>
  );
}
