'use client';

import { useState } from 'react';

/** Blocks onboarding until the user acknowledges this isn't medical advice. */
export default function DisclaimerModal({ onAcknowledge }: { onAcknowledge: () => void }) {
  const [checked, setChecked] = useState(false);
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 px-4" role="presentation">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="disclaimer-title"
        className="w-full max-w-md rounded-lg bg-white p-6 shadow-xl"
      >
        <h2 id="disclaimer-title" className="text-lg font-semibold">
          Before you start
        </h2>
        <p className="mt-3 text-sm leading-relaxed text-slate-700">
          RehabFlow is for fitness guidance only and is not a substitute for professional medical advice.
          Consult your doctor or physical therapist before starting any exercise program.
        </p>
        <p className="mt-2 text-sm leading-relaxed text-slate-700">
          Stop immediately if you feel sharp or increasing pain.
        </p>
        <label className="mt-5 flex items-start gap-3 text-sm">
          <input
            type="checkbox"
            checked={checked}
            onChange={(e) => setChecked(e.target.checked)}
            className="mt-0.5 h-4 w-4 accent-teal-700"
          />
          <span>I understand that RehabFlow does not replace advice from a medical professional.</span>
        </label>
        <button
          onClick={onAcknowledge}
          disabled={!checked}
          className="mt-5 w-full rounded-md bg-teal-700 px-4 py-2.5 font-medium text-white hover:bg-teal-800 disabled:cursor-not-allowed disabled:bg-slate-300"
        >
          Continue
        </button>
      </div>
    </div>
  );
}
