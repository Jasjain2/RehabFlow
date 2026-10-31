import PlanCard from '@/components/PlanCard';
import type { SessionReport } from '@/lib/types';

/** Post-session LLM analysis: findings, cross-session trend, and the adjusted next plan. */
export default function AiAnalysis({ report }: { report: SessionReport }) {
  if (report.analysis_status === 'pending') {
    return (
      <section className="rounded-lg border border-slate-200 bg-white p-5">
        <h2 className="text-lg font-semibold">AI Analysis</h2>
        <p className="mt-2 animate-pulse text-sm text-slate-600">Analyzing your session…</p>
      </section>
    );
  }
  const analysis = report.ai_session_analysis;
  if (!analysis) return null;
  const trend = report.ai_trend_comparison;

  return (
    <section className="space-y-5 rounded-lg border border-slate-200 bg-white p-5">
      <h2 className="text-lg font-semibold">AI Analysis</h2>

      <div>
        <p className="text-slate-800">{analysis.summary}</p>
        {analysis.findings.length > 0 && (
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-700">
            {analysis.findings.map((f) => (
              <li key={f}>{f}</li>
            ))}
          </ul>
        )}
      </div>

      {trend && (
        <div>
          <h3 className="font-medium">Trend across sessions</h3>
          <p className="mt-1 text-sm text-slate-700">{trend.summary}</p>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-700">
            {trend.trends.map((t) => (
              <li key={t}>{t}</li>
            ))}
          </ul>
          <p className="mt-2 rounded-md bg-teal-50 p-3 text-sm text-teal-900">
            <span className="font-medium">Recommendation:</span> {trend.recommendation}
          </p>
        </div>
      )}

      {report.ai_next_plan && (
        <div>
          <h3 className="font-medium">Suggested plan for next session</h3>
          <p className="mt-1 text-sm text-slate-600">
            You&apos;ll be offered this plan when you start your next session.
          </p>
          <div className="mt-3 space-y-3">
            {report.ai_next_plan.exercises.map((exercise, i) => (
              <PlanCard key={`${exercise.name}-${i}`} exercise={exercise} />
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
