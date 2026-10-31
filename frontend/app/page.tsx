'use client';

import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import DisclaimerModal from '@/components/DisclaimerModal';
import InjuryForm from '@/components/InjuryForm';
import { createSession, createSessionFromSuggested, generatePlan, getSuggestedPlan, saveProfile } from '@/lib/api';
import { EXERCISE_LABELS, errorMessage } from '@/lib/format';
import { acknowledgeDisclaimer, getUserId, isDisclaimerAcknowledged, setCurrentSessionId } from '@/lib/storage';
import type { SuggestedPlan, UserProfile } from '@/lib/types';

export default function OnboardingPage() {
  const router = useRouter();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [suggested, setSuggested] = useState<SuggestedPlan | null>(null);
  // null until read from storage, so the modal doesn't flash for users who already acknowledged
  const [acknowledged, setAcknowledged] = useState<boolean | null>(null);

  useEffect(() => {
    setAcknowledged(isDisclaimerAcknowledged());
  }, []);

  useEffect(() => {
    // A missing backend shouldn't block the form, so ignore failures here
    getSuggestedPlan(getUserId()).then(setSuggested, () => setSuggested(null));
  }, []);

  async function applySuggestedPlan() {
    setSubmitting(true);
    setError(null);
    try {
      const { session_id } = await createSessionFromSuggested(getUserId());
      setCurrentSessionId(session_id);
      router.push('/plan');
    } catch (err) {
      setError(`Could not load your adjusted plan: ${errorMessage(err)}`);
      setSubmitting(false);
    }
  }

  async function handleSubmit(profile: UserProfile) {
    setSubmitting(true);
    setError(null);
    try {
      const { session_id } = await createSession(getUserId());
      setCurrentSessionId(session_id);
      await saveProfile(session_id, profile, true);
      await generatePlan(session_id);
      router.push('/plan');
    } catch (err) {
      setError(`Could not create your plan: ${errorMessage(err)}`);
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto max-w-lg">
      {acknowledged === false && (
        <DisclaimerModal
          onAcknowledge={() => {
            acknowledgeDisclaimer();
            setAcknowledged(true);
          }}
        />
      )}
      <h1 className="text-2xl font-semibold">Tell us about your recovery</h1>
      <p className="mt-2 text-slate-600">
        We&apos;ll build a personalized exercise plan, then track your form through your webcam as you
        exercise.
      </p>
      {suggested && (
        <section className="mt-6 rounded-lg border border-teal-200 bg-teal-50 p-5">
          <h2 className="font-semibold text-teal-900">Use your adjusted plan from last session?</h2>
          <p className="mt-1 text-sm text-teal-900">
            {suggested.plan.exercises
              .map((e) => `${EXERCISE_LABELS[e.name]} ${e.sets} × ${e.reps_per_set}`)
              .join(' · ')}
          </p>
          <button
            onClick={applySuggestedPlan}
            disabled={submitting}
            className="mt-3 rounded-md bg-teal-700 px-4 py-2 text-sm font-medium text-white hover:bg-teal-800 disabled:bg-slate-300"
          >
            Use adjusted plan
          </button>
          <p className="mt-3 text-xs text-teal-800">Or fill in the form below for a new plan.</p>
        </section>
      )}
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
