'use client';

import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { TooltipProps } from 'recharts';
import type { HistoryEntry } from '@/lib/types';
import { CHART } from './chartTheme';

interface Point extends HistoryEntry {
  label: string;
}

const dateLabel = (iso: string) => new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });

/** Average form score per session over time. */
export default function ProgressChart({ entries }: { entries: HistoryEntry[] }) {
  const data: Point[] = [...entries]
    .sort((a, b) => a.created_at.localeCompare(b.created_at))
    .map((e) => ({ ...e, label: dateLabel(e.created_at) }));

  return (
    <div className="h-64 w-full">
      <ResponsiveContainer>
        <LineChart data={data} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
          <CartesianGrid stroke={CHART.grid} vertical={false} />
          <XAxis
            dataKey="label"
            tick={{ fill: CHART.axisText, fontSize: 12 }}
            tickLine={false}
            axisLine={{ stroke: CHART.grid }}
          />
          <YAxis
            domain={[0, 100]}
            ticks={[0, 25, 50, 75, 100]}
            tick={{ fill: CHART.axisText, fontSize: 12 }}
            tickLine={false}
            axisLine={false}
            width={36}
          />
          <Tooltip content={<SessionTooltip />} cursor={{ stroke: CHART.grid }} />
          <Line
            type="monotone"
            dataKey="avg_form_score"
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
  );
}

function SessionTooltip({ active, payload }: TooltipProps<number, string>) {
  if (!active || !payload?.length) return null;
  const entry = payload[0].payload as Point;
  return (
    <div className="rounded-md border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm">
      <p className="text-slate-500">{new Date(entry.created_at).toLocaleString()}</p>
      <p className="font-semibold tabular-nums">Avg score {Math.round(entry.avg_form_score)}</p>
      <p className="tabular-nums text-slate-600">{entry.total_reps} reps</p>
    </div>
  );
}
