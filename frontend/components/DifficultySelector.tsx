import type { Difficulty } from '@/lib/types';

const OPTIONS: { value: Difficulty; label: string; description: string }[] = [
  { value: 'conservative', label: 'Conservative', description: 'Fewer reps, longer rest, extra safety guidance' },
  { value: 'moderate', label: 'Moderate', description: 'Balanced volume and rest' },
  { value: 'aggressive', label: 'Aggressive', description: 'More volume, shorter rest' },
];

interface Props {
  value: Difficulty;
  onChange: (value: Difficulty) => void;
}

export default function DifficultySelector({ value, onChange }: Props) {
  return (
    <fieldset>
      <legend className="text-sm font-medium">Difficulty</legend>
      <p className="text-xs text-slate-500">Start conservative unless your physical therapist recommends otherwise.</p>
      <div className="mt-2 space-y-2">
        {OPTIONS.map((option) => (
          <label
            key={option.value}
            className={`flex cursor-pointer items-start gap-3 rounded-md border px-3 py-2 ${
              value === option.value ? 'border-teal-600 bg-teal-50' : 'border-slate-300'
            }`}
          >
            <input
              type="radio"
              name="difficulty"
              value={option.value}
              checked={value === option.value}
              onChange={() => onChange(option.value)}
              className="mt-1 accent-teal-700"
            />
            <span>
              <span className="block text-sm font-medium">{option.label}</span>
              <span className="block text-xs text-slate-600">{option.description}</span>
            </span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}
