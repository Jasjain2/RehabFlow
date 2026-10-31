'use client';

import { useState } from 'react';
import DifficultySelector from '@/components/DifficultySelector';
import type { Difficulty, InjuryType, MobilityLevel, UserProfile } from '@/lib/types';

const INJURY_OPTIONS: { value: InjuryType; label: string }[] = [
  { value: 'knee', label: 'Knee' },
  { value: 'shoulder', label: 'Shoulder' },
  { value: 'upper_body', label: 'Upper body' },
  { value: 'lower_body', label: 'Lower body' },
  { value: 'general', label: 'General' },
];

const MOBILITY_OPTIONS: { value: MobilityLevel; label: string }[] = [
  { value: 'limited', label: 'Limited' },
  { value: 'moderate', label: 'Moderate' },
  { value: 'full', label: 'Full' },
];

const MIN_AGE = 10;
const MAX_AGE = 100;

interface Props {
  onSubmit: (profile: UserProfile) => void;
  submitting: boolean;
}

const fieldClass =
  'mt-1 block w-full rounded-md border border-slate-300 bg-white px-3 py-2 focus:border-teal-600 focus:outline-none focus:ring-1 focus:ring-teal-600';

export default function InjuryForm({ onSubmit, submitting }: Props) {
  const [age, setAge] = useState('');
  const [injury, setInjury] = useState<InjuryType | ''>('');
  const [mobility, setMobility] = useState<MobilityLevel | ''>('');
  const [painTolerance, setPainTolerance] = useState(5);
  const [difficulty, setDifficulty] = useState<Difficulty>('conservative');

  const ageNumber = Number(age);
  const ageValid = Number.isInteger(ageNumber) && ageNumber >= MIN_AGE && ageNumber <= MAX_AGE;
  const canSubmit = ageValid && injury !== '' && mobility !== '' && !submitting;

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSubmit) return;
    onSubmit({ age: ageNumber, injury, mobility, pain_tolerance: painTolerance, difficulty });
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-5 rounded-lg border border-slate-200 bg-white p-6">
      <label className="block">
        <span className="text-sm font-medium">Age</span>
        <input
          type="number"
          inputMode="numeric"
          min={MIN_AGE}
          max={MAX_AGE}
          required
          value={age}
          onChange={(e) => setAge(e.target.value)}
          className={fieldClass}
        />
      </label>

      <label className="block">
        <span className="text-sm font-medium">Injury type</span>
        <select
          required
          value={injury}
          onChange={(e) => setInjury(e.target.value as InjuryType)}
          className={fieldClass}
        >
          <option value="" disabled>
            Select an injury type
          </option>
          {INJURY_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </label>

      <label className="block">
        <span className="text-sm font-medium">Mobility level</span>
        <select
          required
          value={mobility}
          onChange={(e) => setMobility(e.target.value as MobilityLevel)}
          className={fieldClass}
        >
          <option value="" disabled>
            Select your mobility level
          </option>
          {MOBILITY_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </label>

      <label className="block">
        <span className="text-sm font-medium">
          Pain tolerance: <span className="tabular-nums">{painTolerance}</span>/10
        </span>
        <input
          type="range"
          min={1}
          max={10}
          step={1}
          value={painTolerance}
          onChange={(e) => setPainTolerance(Number(e.target.value))}
          className="mt-2 block w-full accent-teal-600"
        />
        <span className="mt-1 flex justify-between text-xs text-slate-500">
          <span>Low</span>
          <span>High</span>
        </span>
      </label>

      <DifficultySelector value={difficulty} onChange={setDifficulty} />

      <button
        type="submit"
        disabled={!canSubmit}
        className="w-full rounded-md bg-teal-700 px-4 py-2.5 font-medium text-white hover:bg-teal-800 disabled:cursor-not-allowed disabled:bg-slate-300"
      >
        {submitting ? 'Generating your plan…' : 'Generate my plan'}
      </button>
    </form>
  );
}
