import { formatPercent } from '@/lib/format';
import type { FatigueLevel } from '@/lib/types';

interface Props {
  level: FatigueLevel;
  drift: number;
}

export default function FatigueAlert({ level, drift }: Props) {
  if (level === 'moderate') {
    return (
      <div role="status" className="rounded-lg border border-amber-300 bg-amber-50 p-4 text-amber-900">
        <p className="font-semibold">⚠ Your form is starting to slip</p>
        <p className="mt-1 text-sm">
          Form is {formatPercent(drift)} below your baseline. Slow down and focus on control.
        </p>
      </div>
    );
  }
  if (level === 'high') {
    return (
      <div role="alert" className="rounded-lg border border-red-300 bg-red-50 p-4 text-red-900">
        <p className="font-semibold">⛔ Your form has dropped significantly</p>
        <p className="mt-1 text-sm">
          Form is {formatPercent(drift)} below your baseline. We recommend stopping to prevent
          re-injury.
        </p>
      </div>
    );
  }
  return null;
}
