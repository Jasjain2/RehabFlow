'use client';

import { useRouter } from 'next/navigation';
import { useState } from 'react';
import InjuryForm from '@/components/InjuryForm';
import { createSession, generatePlan, saveProfile } from '@/lib/api';
import { errorMessage } from '@/lib/format';
import { getUserId, setCurrentSessionId } from '@/lib/storage';
import type { UserProfile } from '@/lib/types';

export default function OnboardingPage() {
  const router = useRouter();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(profile: UserProfile) {
    setSubmitting(true);
    setError(null);
    try {
      const { session_id } = await createSession(getUserId());
      setCurrentSessionId(session_id);
      await saveProfile(session_id, profile);
      await generatePlan(session_id);
      router.push('/plan');
    } catch (err) {
      setError(`Could not create your plan: ${errorMessage(err)}`);
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto max-w-lg">
      <h1 className="text-2xl font-semibold">Tell us about your recovery</h1>
      <p className="mt-2 text-slate-600">
        We&apos;ll build a personalized exercise plan, then track your form through your webcam as you
        exercise.
      </p>
      <div className="mt-6">
        <InjuryForm onSubmit={handleSubmit} submitting={submitting} />
      </div>
      {error && (
        <p role="alert" className="mt-4 rounded-md bg-red-50 p-3 text-sm text-red-700">
          {error}
        </p>
      )}
    </div>
  );
}
