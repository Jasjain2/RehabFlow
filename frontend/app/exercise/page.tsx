'use client';

import { useRouter } from 'next/navigation';
import { useCallback, useEffect, useRef, useState } from 'react';
import CameraFeed from '@/components/CameraFeed';
import FatigueAlert from '@/components/FatigueAlert';
import FormScore from '@/components/FormScore';
import LiveSignals from '@/components/LiveSignals';
import NoSession from '@/components/NoSession';
import RestOverlay from '@/components/RestOverlay';
import { connectExerciseStream, finishSession, getPlan } from '@/lib/api';
import { EXERCISE_LABELS, errorMessage } from '@/lib/format';
import { getCurrentSessionId } from '@/lib/storage';
import type { ExerciseUpdate, FrameMessage, RehabPlan, SkipRestMessage } from '@/lib/types';

const FRAME_INTERVAL_MS = 400;
// Skip a frame rather than queue it when the connection is backed up (~2 frames)
const MAX_BUFFERED_BYTES = 200_000;

type Connection = 'connecting' | 'open' | 'closed';

export default function ExercisePage() {
  const router = useRouter();
  const [sessionId, setSessionId] = useState<string | null | undefined>(undefined);
  const [plan, setPlan] = useState<RehabPlan | null>(null);
  const [update, setUpdate] = useState<ExerciseUpdate | null>(null);
  const [connection, setConnection] = useState<Connection>('connecting');
  const [error, setError] = useState<string | null>(null);
  const [finishing, setFinishing] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const finishingRef = useRef(false);

  useEffect(() => {
    const id = getCurrentSessionId();
    setSessionId(id);
    if (id) getPlan(id).then(setPlan, (err) => setError(errorMessage(err)));
  }, []);

  useEffect(() => {
    if (!sessionId) return;
    const ws = connectExerciseStream(sessionId);
    wsRef.current = ws;
    ws.onopen = () => setConnection('open');
    ws.onmessage = (event) => setUpdate(JSON.parse(event.data) as ExerciseUpdate);
    ws.onclose = (event) => {
      setConnection('closed');
      if (!finishingRef.current && event.code !== 1000) {
        setError(event.reason || 'Lost connection to the server.');
      }
    };
    return () => ws.close(1000);
  }, [sessionId]);

  const sendFrame = useCallback((image: string) => {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN || ws.bufferedAmount > MAX_BUFFERED_BYTES) return;
    const message: FrameMessage = { type: 'frame', image };
    ws.send(JSON.stringify(message));
  }, []);

  const skipRest = useCallback(() => {
    const message: SkipRestMessage = { type: 'skip_rest' };
    wsRef.current?.send(JSON.stringify(message));
  }, []);

  const finish = useCallback(async () => {
    if (!sessionId || finishingRef.current) return;
    finishingRef.current = true;
    setFinishing(true);
    wsRef.current?.close(1000);
    try {
      await finishSession(sessionId);
      router.push('/report');
    } catch (err) {
      setError(`Could not save your session: ${errorMessage(err)}`);
      finishingRef.current = false;
      setFinishing(false);
    }
  }, [sessionId, router]);

  useEffect(() => {
    if (update?.status === 'complete') finish();
  }, [update?.status, finish]);

  if (sessionId === null) return <NoSession />;

  const exerciseIndex = update?.exercise_index ?? 0;
  const currentExercise = plan?.exercises[exerciseIndex];
  const resting = update?.status === 'resting';

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">
            {currentExercise ? EXERCISE_LABELS[currentExercise.name] : 'Exercise session'}
          </h1>
          {plan && (
            <p className="text-sm text-slate-600">
              Exercise {exerciseIndex + 1} of {plan.exercises.length}
            </p>
          )}
        </div>
        <div className="flex items-center gap-3">
          <ConnectionBadge connection={connection} />
          <button
            onClick={finish}
            disabled={finishing}
            className="rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium hover:bg-slate-100 disabled:opacity-50"
          >
            {finishing ? 'Saving…' : 'Finish Session'}
          </button>
        </div>
      </div>

      {error && (
        <p role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-700">
          {error}
        </p>
      )}

      <div className="grid gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <div className="relative">
          <CameraFeed
            intervalMs={FRAME_INTERVAL_MS}
            active={connection === 'open' && !finishing}
            onFrame={sendFrame}
            landmarks={update?.landmarks}
          />
          {resting && <RestOverlay update={update} onSkip={skipRest} />}
        </div>

        <div className="space-y-4">
          <FormScore score={update?.form_score ?? null} />
          <div className="grid grid-cols-2 gap-3 text-center">
            <Stat label="Set" value={update ? `${update.set_number} / ${update.total_sets}` : '–'} />
            <Stat label="Rep" value={update ? `${update.rep_in_set} / ${update.reps_per_set}` : '–'} />
            <Stat label="Phase" value={update?.phase ?? '–'} detail={mlPhaseDetail(update)} />
            <Stat label="Total reps" value={update ? String(update.rep_count) : '–'} />
          </div>
          {update?.fatigue_level === 'building_baseline' && (
            <p className="text-sm text-slate-600">Measuring your baseline form over the first few reps…</p>
          )}
          {update && <FatigueAlert level={update.fatigue_level} drift={update.fatigue_drift} />}
          {update && <LiveSignals update={update} />}
          {currentExercise && currentExercise.coaching_cues.length > 0 && (
            <section className="rounded-lg border border-slate-200 bg-white p-4">
              <h2 className="text-sm font-medium text-slate-700">Coaching cues</h2>
              <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-slate-700">
                {currentExercise.coaching_cues.map((cue) => (
                  <li key={cue}>{cue}</li>
                ))}
              </ul>
            </section>
          )}
        </div>
      </div>
    </div>
  );
}

/** "ML: descending 92%" — the ML phase detector runs alongside the rule-based phase */
function mlPhaseDetail(update: ExerciseUpdate | null): string | undefined {
  if (!update?.ml_phase || update.ml_phase_confidence === null) return undefined;
  return `ML: ${update.ml_phase} ${Math.round(update.ml_phase_confidence * 100)}%`;
}

function Stat({ label, value, detail }: { label: string; value: string; detail?: string }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3">
      <p className="text-xs text-slate-500">{label}</p>
      <p className="mt-0.5 text-lg font-semibold capitalize tabular-nums">{value}</p>
      {detail && <p className="text-xs tabular-nums text-slate-500">{detail}</p>}
    </div>
  );
}

function ConnectionBadge({ connection }: { connection: Connection }) {
  const styles: Record<Connection, string> = {
    connecting: 'bg-slate-100 text-slate-700',
    open: 'bg-emerald-50 text-emerald-800',
    closed: 'bg-red-50 text-red-800',
  };
  const labels: Record<Connection, string> = { connecting: 'Connecting…', open: '● Live', closed: 'Disconnected' };
  return <span className={`rounded-full px-3 py-1 text-xs font-medium ${styles[connection]}`}>{labels[connection]}</span>;
}
