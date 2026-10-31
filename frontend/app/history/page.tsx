'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import ProgressChart from '@/components/ProgressChart';
import { getHistory } from '@/lib/api';
import { EXERCISE_LABELS, errorMessage, scoreColor } from '@/lib/format';
import { getUserId } from '@/lib/storage';
import type { HistoryEntry } from '@/lib/types';

export default function HistoryPage() {
  const [entries, setEntries] = useState<HistoryEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getHistory(getUserId()).then(setEntries, (err) => setError(errorMessage(err)));
  }, []);

  if (error) return <p className="text-red-700">Could not load your history: {error}</p>;
  if (!entries) return <p className="text-slate-600">Loading your progress…</p>;

  if (entries.length === 0) {
    return (
      <div className="mx-auto max-w-md rounded-lg border border-slate-200 bg-white p-6 text-center">
        <p className="text-slate-700">No completed sessions yet.</p>
        <Link href="/" className="mt-4 inline-block font-medium text-teal-700 hover:underline">
          Start your first session
        </Link>
      </div>
    );
  }

  const newestFirst = [...entries].sort((a, b) => b.created_at.localeCompare(a.created_at));

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Your progress</h1>

      {entries.length > 1 && (
        <section className="rounded-lg border border-slate-200 bg-white p-5">
          <h2 className="mb-3 font-medium">Average form score per session</h2>
          <ProgressChart entries={entries} />
        </section>
      )}

      <section className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
        <table className="w-full text-left text-sm tabular-nums">
          <thead className="text-slate-500">
            <tr>
              <th className="px-4 py-2 font-medium">Date</th>
              <th className="px-4 py-2 font-medium">Exercises</th>
              <th className="px-4 py-2 font-medium">Reps</th>
              <th className="px-4 py-2 font-medium">Avg score</th>
            </tr>
          </thead>
          <tbody>
            {newestFirst.map((e) => (
              <tr key={e.session_id} className="border-t border-slate-100">
                <td className="px-4 py-2">{new Date(e.created_at).toLocaleDateString()}</td>
                <td className="px-4 py-2">{e.exercises.map((x) => EXERCISE_LABELS[x]).join(', ')}</td>
                <td className="px-4 py-2">{e.total_reps}</td>
                <td className={`px-4 py-2 font-medium ${scoreColor(e.avg_form_score)}`}>
                  {Math.round(e.avg_form_score)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
