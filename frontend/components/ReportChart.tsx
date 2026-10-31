'use client';

import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { TooltipProps } from 'recharts';
import { formatPercent } from '@/lib/format';
import type { RepSummary } from '@/lib/types';
import { CHART } from './chartTheme';

// Matches FATIGUE_BASELINE_REPS / FATIGUE_*_DRIFT in backend/config/settings.py
const BASELINE_REPS = 3;
const MODERATE_DRIFT = 0.15;
const HIGH_DRIFT = 0.3;

interface Point extends RepSummary {
  index: number;
}

/** Form score per rep for one exercise, with the fatigue baseline and alert levels marked. */
export default function ReportChart({ reps }: { reps: RepSummary[] }) {
  const data: Point[] = reps.map((rep, i) => ({ ...rep, index: i + 1 }));
  const baselineReps = reps.slice(0, BASELINE_REPS);
  const baseline =
    baselineReps.length === BASELINE_REPS
      ? baselineReps.reduce((sum, r) => sum + r.form_score, 0) / BASELINE_REPS
      : null;

  return (
    <div>
      <div className="h-64 w-full">
        <ResponsiveContainer>
          <LineChart data={data} margin={{ top: 8, right: 96, bottom: 8, left: 0 }}>
            <CartesianGrid stroke={CHART.grid} vertical={false} />
            <XAxis
              dataKey="index"
              tick={{ fill: CHART.axisText, fontSize: 12 }}
              tickLine={false}
              axisLine={{ stroke: CHART.grid }}
              label={{ value: 'Rep', position: 'insideBottomRight', offset: -4, fill: CHART.axisText, fontSize: 12 }}
            />
            <YAxis
              domain={[0, 100]}
              ticks={[0, 25, 50, 75, 100]}
              tick={{ fill: CHART.axisText, fontSize: 12 }}
              tickLine={false}
              axisLine={false}
              width={36}
            />
            {baseline !== null && (
              <>
                <ReferenceLine y={baseline} stroke={CHART.baseline} strokeDasharray="4 4" label={refLabel('Baseline')} />
                <ReferenceLine
                  y={baseline * (1 - MODERATE_DRIFT)}
                  stroke={CHART.warning}
                  strokeDasharray="4 4"
                  label={refLabel(`−${formatPercent(MODERATE_DRIFT)}`)}
                />
                <ReferenceLine
                  y={baseline * (1 - HIGH_DRIFT)}
                  stroke={CHART.critical}
                  strokeDasharray="4 4"
                  label={refLabel(`−${formatPercent(HIGH_DRIFT)} stop`)}
                />
              </>
            )}
            <Tooltip content={<RepTooltip />} cursor={{ stroke: CHART.grid }} />
            <Line
              type="monotone"
              dataKey="form_score"
              stroke={CHART.series}
              strokeWidth={2}
              strokeLinejoin="round"
              strokeLinecap="round"
              dot={{ r: 4, fill: CHART.series, stroke: CHART.surface, strokeWidth: 2 }}
              activeDot={{ r: 6, fill: CHART.series, stroke: CHART.surface, strokeWidth: 2 }}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <details className="mt-2 text-sm">
        <summary className="cursor-pointer text-slate-600 hover:text-slate-900">Show rep data</summary>
        <div className="mt-2 overflow-x-auto">
          <table className="w-full text-left tabular-nums">
            <thead className="text-slate-500">
              <tr>
                <th className="py-1 pr-4 font-medium">Set</th>
                <th className="py-1 pr-4 font-medium">Rep</th>
                <th className="py-1 pr-4 font-medium">Form score</th>
                <th className="py-1 pr-4 font-medium">Drift</th>
                <th className="py-1 font-medium">Fatigue</th>
              </tr>
            </thead>
            <tbody>
              {reps.map((r) => (
                <tr key={`${r.set_number}-${r.rep_number}`} className="border-t border-slate-100">
                  <td className="py-1 pr-4">{r.set_number}</td>
                  <td className="py-1 pr-4">{r.rep_number}</td>
                  <td className="py-1 pr-4">{Math.round(r.form_score)}</td>
                  <td className="py-1 pr-4">{formatPercent(r.fatigue_drift)}</td>
                  <td className="py-1">{r.fatigue_level.replace('_', ' ')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  );
}

function refLabel(value: string) {
  return { value, position: 'right' as const, fill: CHART.axisText, fontSize: 12 };
}

function RepTooltip({ active, payload }: TooltipProps<number, string>) {
  if (!active || !payload?.length) return null;
  const rep = payload[0].payload as Point;
  return (
    <div className="rounded-md border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm">
      <p className="text-slate-500">
        Set {rep.set_number} · Rep {rep.rep_number}
      </p>
      <p className="font-semibold tabular-nums">Score {Math.round(rep.form_score)}</p>
      <p className="tabular-nums text-slate-600">Drift {formatPercent(rep.fatigue_drift)}</p>
    </div>
  );
}
