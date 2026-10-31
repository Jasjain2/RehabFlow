import type { ExerciseUpdate, PostureCheck } from '@/lib/types';

const POSTURE: Record<PostureCheck, { label: string; className: string }> = {
  good: { label: 'Posture check: Good', className: 'border-emerald-300 bg-emerald-50 text-emerald-900' },
  needs_attention: {
    label: 'Posture check: Needs attention. Check your depth and trunk position.',
    className: 'border-amber-300 bg-amber-50 text-amber-900',
  },
  acceptable_for_rehab_depth: {
    label: 'Posture check: Acceptable for rehab depth',
    className: 'border-slate-200 bg-white text-slate-700',
  },
};

/** ML and symmetry signals shown alongside the rule-based score. */
export default function LiveSignals({ update }: { update: ExerciseUpdate }) {
  const asymmetricJoints = Object.entries(update.asymmetry_details);
  return (
    <div className="space-y-2 text-sm">
      {update.posture_check && (
        <p className={`rounded-lg border px-3 py-2 ${POSTURE[update.posture_check].className}`}>
          {POSTURE[update.posture_check].label}
        </p>
      )}
      {update.asymmetry_detected && asymmetricJoints.length > 0 && (
        <p role="status" className="rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-amber-900">
          ⚠ Asymmetry detected (
          {asymmetricJoints.map(([joint, deg]) => `${joint} ${Math.round(deg)}°`).join(', ')}). You may be favoring
          one side. Try to distribute weight evenly.
        </p>
      )}
      {update.is_anomalous && (
        <p role="status" className="rounded-lg border border-slate-300 bg-slate-100 px-3 py-2 text-slate-700">
          Unusual movement detected. Check your positioning.
        </p>
      )}
    </div>
  );
}
