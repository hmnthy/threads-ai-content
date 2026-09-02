"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  WEEKDAY_LABELS,
  getAnalyticsOverview,
  type AnalyticsOverview,
  type TimezoneEngagement,
  type TopPostEntry,
} from "@/lib/api";

type MetricKey = "engagement" | "virality" | "conversation";

const METRIC_TABS: { key: MetricKey; label: string; field: keyof TopPostEntry["metrics"] }[] = [
  { key: "engagement", label: "Top by engagement", field: "engagement_rate" },
  { key: "virality", label: "Top by virality", field: "virality_index" },
  { key: "conversation", label: "Top by conversation", field: "conversation_rate" },
];

function truncate(text: string, max: number): string {
  return text.length > max ? `${text.slice(0, max)}…` : text;
}

function formatPercent(value: number): string {
  return `${value.toFixed(2)}%`;
}

export function AnalyticsOverview() {
  const [data, setData] = useState<AnalyticsOverview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeMetric, setActiveMetric] = useState<MetricKey>("engagement");

  useEffect(() => {
    getAnalyticsOverview()
      .then(setData)
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : "Failed to load data from the API.");
      });
  }, []);

  if (error !== null) {
    return (
      <div className="rounded-[10px] border border-bg-border bg-bg-surface p-6 text-negative">
        Could not reach the API at the configured base URL. Is `uvicorn src.main:app` running? ({error})
      </div>
    );
  }

  if (data === null) {
    return (
      <div className="rounded-[10px] border border-bg-border bg-bg-surface p-6 text-text-secondary">
        Loading analytics…
      </div>
    );
  }

  const activeList =
    activeMetric === "engagement"
      ? data.top_by_engagement
      : activeMetric === "virality"
        ? data.top_by_virality
        : data.top_by_conversation;
  const activeField = METRIC_TABS.find((tab) => tab.key === activeMetric)!.field;
  const maxValue = Math.max(...activeList.map((entry) => entry.metrics[activeField]), 0.0001);

  return (
    <div className="flex flex-col gap-4">
      <StatRow data={data} />

      <div className="rounded-[10px] border border-bg-border bg-bg-surface p-5">
        <div className="mb-4 flex flex-wrap gap-2">
          {METRIC_TABS.map((tab) => (
            <button
              key={tab.key}
              type="button"
              onClick={() => setActiveMetric(tab.key)}
              className={`rounded-full px-3 py-1.5 text-sm font-medium transition-colors ${
                activeMetric === tab.key
                  ? "bg-accent-purple text-text-primary"
                  : "text-text-secondary hover:bg-bg-elevated hover:text-text-primary"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
        <TopPostsTable entries={activeList} field={activeField} maxValue={maxValue} />
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        {data.timezones.map((tz) => (
          <TimezoneCharts key={tz.timezone} tz={tz} />
        ))}
      </div>
    </div>
  );
}

function StatRow({ data }: { data: AnalyticsOverview }) {
  const stats = [
    { label: "Root posts analyzed", value: data.post_count.toString() },
    { label: "Average engagement rate", value: formatPercent(data.average_engagement_rate) },
  ];

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
      {stats.map((stat) => (
        <div key={stat.label} className="rounded-[10px] border border-bg-border bg-bg-surface p-5">
          <div className="text-[11px] font-medium uppercase tracking-wide text-text-muted">
            {stat.label}
          </div>
          <div className="mt-1 text-[28px] font-bold tabular-nums text-text-primary">{stat.value}</div>
        </div>
      ))}
    </div>
  );
}

function TopPostsTable({
  entries,
  field,
  maxValue,
}: {
  entries: TopPostEntry[];
  field: keyof TopPostEntry["metrics"];
  maxValue: number;
}) {
  if (entries.length === 0) {
    return <p className="text-sm text-text-secondary">No post has an insight snapshot yet.</p>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="text-left text-[11px] uppercase tracking-wide text-text-muted">
            <th className="pb-2 pr-4 font-medium">Post</th>
            <th className="pb-2 pr-4 font-medium">Posted at (UTC)</th>
            <th className="pb-2 font-medium">Value</th>
          </tr>
        </thead>
        <tbody>
          {entries.map((entry, index) => {
            const value = entry.metrics[field];
            const width = maxValue > 0 ? Math.max((value / maxValue) * 100, 2) : 0;
            return (
              <tr
                key={entry.id}
                className={`border-t border-bg-border hover:bg-bg-elevated ${
                  index % 2 === 1 ? "bg-white/[0.02]" : ""
                }`}
              >
                <td className="max-w-[420px] py-2 pr-4 text-text-primary">
                  {truncate(entry.text ?? "(no text)", 90)}
                </td>
                <td className="py-2 pr-4 whitespace-nowrap text-text-secondary">
                  {entry.timestamp.replace("T", " ").slice(0, 16)}
                </td>
                <td className="py-2">
                  <div className="flex items-center gap-2">
                    <div className="h-1.5 w-24 overflow-hidden rounded-full bg-bg-elevated">
                      <div
                        className="h-full rounded-full bg-gradient-to-r from-accent-purple to-positive"
                        style={{ width: `${width}%` }}
                      />
                    </div>
                    <span className="tabular-nums text-text-primary">{formatPercent(value)}</span>
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function TimezoneCharts({ tz }: { tz: TimezoneEngagement }) {
  const hourData = useMemo(
    () =>
      Array.from({ length: 24 }, (_, hour) => ({
        hour,
        rate: tz.by_hour.find((bucket) => bucket.hour === hour)?.average_engagement_rate ?? 0,
      })),
    [tz],
  );
  const weekdayData = useMemo(
    () =>
      Array.from({ length: 7 }, (_, weekday) => ({
        weekday: WEEKDAY_LABELS[weekday],
        rate: tz.by_weekday.find((bucket) => bucket.weekday === weekday)?.average_engagement_rate ?? 0,
      })),
    [tz],
  );

  return (
    <div className="rounded-[10px] border border-bg-border bg-bg-surface p-5">
      <h3 className="text-[13px] font-medium uppercase tracking-wide text-text-secondary">{tz.timezone}</h3>
      <p className="mb-4 text-[11px] text-text-muted">Average engagement rate by local post hour / weekday</p>

      <div className="h-[180px]">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={hourData} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#2a2a2a" vertical={false} />
            <XAxis dataKey="hour" stroke="#525252" fontSize={11} tickLine={false} />
            <YAxis stroke="#525252" fontSize={11} tickLine={false} width={36} />
            <Tooltip
              contentStyle={{ background: "#141414", border: "1px solid #2a2a2a", fontSize: 12 }}
              formatter={(value) => [`${Number(value).toFixed(2)}%`, "Engagement rate"]}
              labelFormatter={(hour) => `Hour ${hour}`}
            />
            <Bar dataKey="rate" fill="#7c3aed" radius={[3, 3, 0, 0]} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="mt-4 h-[160px]">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={weekdayData} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#2a2a2a" vertical={false} />
            <XAxis dataKey="weekday" stroke="#525252" fontSize={11} tickLine={false} />
            <YAxis stroke="#525252" fontSize={11} tickLine={false} width={36} />
            <Tooltip
              contentStyle={{ background: "#141414", border: "1px solid #2a2a2a", fontSize: 12 }}
              formatter={(value) => [`${Number(value).toFixed(2)}%`, "Engagement rate"]}
            />
            <Bar dataKey="rate" fill="#a78bfa" radius={[3, 3, 0, 0]} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
