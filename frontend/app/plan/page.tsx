'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import NoSession from '@/components/NoSession';
import PlanCard from '@/components/PlanCard';
import { getPlan } from '@/lib/api';
import { errorMessage } from '@/lib/format';
import { getCurrentSessionId } from '@/lib/storage';
import type { RehabPlan } from '@/lib/types';

export default function PlanPage() {
  const [sessionId, setSessionId] = useState<string | null | undefined>(undefined);
  const [plan, setPlan] = useState<RehabPlan | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const id = getCurrentSessionId();
    setSessionId(id);
    if (id) getPlan(id).then(setPlan, (err) => setError(errorMessage(err)));
  }, []);

  if (sessionId === null) return <NoSession />;
  if (error) return <p className="text-red-700">Could not load your plan: {error}</p>;
  if (!plan) return <p className="text-slate-600">Loading your plan…</p>;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">Your rehab plan</h1>
          <p className="mt-1 text-slate-600">{plan.overall_safety}</p>
        </div>
        <Link
          href="/exercise"
          className="rounded-md bg-teal-700 px-5 py-2.5 font-medium text-white hover:bg-teal-800"
        >
          Start Session
        </Link>
      </div>

      <section className="rounded-lg border border-slate-200 bg-white p-5">
        <h2 className="font-medium">Warm-up</h2>
        <p className="mt-1 text-sm text-slate-700">{plan.warmup}</p>
      </section>

      {plan.exercises.map((exercise, i) => (
        <PlanCard key={`${exercise.name}-${i}`} exercise={exercise} />
      ))}

      <section className="rounded-lg border border-slate-200 bg-white p-5">
        <h2 className="font-medium">Cool-down</h2>
        <p className="mt-1 text-sm text-slate-700">{plan.cooldown}</p>
      </section>
    </div>
  );
}
