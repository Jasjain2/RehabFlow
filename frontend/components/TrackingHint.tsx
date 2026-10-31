import type { ExerciseName, TrackingIssue } from '@/lib/types';

const KEY_JOINTS: Record<ExerciseName, string> = {
  squat: 'hips, knees and feet',
  push_up: 'shoulders, elbows and wrists',
};

/** Overlaid on the camera when a frame can't be counted, saying how to fix the framing. */
export default function TrackingHint({ issue, exercise }: { issue: TrackingIssue; exercise: ExerciseName }) {
  const message =
    issue === 'no_person'
      ? "Can't see you. Step back until your whole body is in the frame."
      : `Can't see your ${KEY_JOINTS[exercise]}. Step back, stand side-on, and keep them in the frame. Reps aren't counted until they're visible.`;
  return (
    <p role="status" className="absolute inset-x-3 bottom-3 rounded-md bg-amber-400/95 px-3 py-2 text-sm font-medium text-amber-950">
      {message}
    </p>
  );
}
