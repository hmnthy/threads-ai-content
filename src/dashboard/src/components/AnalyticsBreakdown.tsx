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

export function AnalyticsBreakdown() {
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
      <div className="rounded-xl border border-border-hairline bg-bg-card p-6 text-negative">
        Could not reach the API at the configured base URL. Is `uvicorn src.main:app` running? ({error})
      </div>
    );
  }

  if (data === null) {
    return (
      <div className="rounded-xl border border-border-hairline bg-bg-card p-6 text-text-secondary">
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

      <div className="rounded-xl border border-border-hairline bg-bg-card p-5">
        <div className="mb-4 flex flex-wrap gap-2">
          {METRIC_TABS.map((tab) => (
            <button
              key={tab.key}
              type="button"
              onClick={() => setActiveMetric(tab.key)}
              className={`rounded-full px-3 py-1.5 text-sm font-medium transition-colors ${
                activeMetric === tab.key
                  ? "bg-amber-600 text-white"
                  : "text-text-secondary hover:bg-bg-surface hover:text-text-primary"
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
        <div key={stat.label} className="rounded-xl border border-border-hairline bg-bg-card p-5">
          <div className="text-xs font-medium text-text-muted">{stat.label}</div>
          <div className="mt-1 font-mono text-[28px] font-bold tabular-nums text-text-primary">
            {stat.value}
          </div>
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
          <tr className="text-left text-[11px] font-semibold text-text-muted">
            <th className="pb-2 pr-4 font-medium">Post</th>
            <th className="pb-2 pr-4 font-medium">Posted at (UTC)</th>
            <th className="pb-2 font-medium">Value</th>
          </tr>
        </thead>
        <tbody>
          {entries.map((entry) => {
            const value = entry.metrics[field];
            const width = maxValue > 0 ? Math.max((value / maxValue) * 100, 2) : 0;
            return (
              <tr key={entry.id} className="border-t border-border-hairline hover:bg-bg-surface">
                <td className="max-w-[420px] py-2 pr-4 text-text-primary">
                  {truncate(entry.text ?? "(no text)", 90)}
                </td>
                <td className="py-2 pr-4 font-mono whitespace-nowrap text-text-secondary">
                  {entry.timestamp.replace("T", " ").slice(0, 16)}
                </td>
                <td className="py-2">
                  <div className="flex items-center gap-2">
                    <div className="h-1.5 w-24 overflow-hidden rounded-full bg-bg-surface">
                      <div className="h-full rounded-full bg-amber-fill" style={{ width: `${width}%` }} />
                    </div>
                    <span className="font-mono tabular-nums text-text-primary">{formatPercent(value)}</span>
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

// Median là số headline (chống outlier — Narrative Layering Principle, xem
// docs/claude/data-model.md), mean/n đi kèm trong tooltip thay vì bị bỏ, đúng
// nguyên tắc "2 con số nên đi cùng nhau" đã chốt ở Layer 2. Bucket
// insufficient_data (n < MIN_N_PER_BUCKET) vẫn hiện số nhưng nhạt màu hơn — không
// tuyên bố "giờ tốt nhất" từ 1-2 bài.
function TimezoneCharts({ tz }: { tz: TimezoneEngagement }) {
  const hourData = useMemo(
    () =>
      Array.from({ length: 24 }, (_, hour) => {
        const bucket = tz.by_hour.find((b) => b.hour === hour)?.stats;
        return {
          hour,
          median: bucket?.median ?? 0,
          mean: bucket?.mean ?? 0,
          n: bucket?.n ?? 0,
          insufficient: bucket?.insufficient_data ?? true,
        };
      }),
    [tz],
  );
  const weekdayData = useMemo(
    () =>
      Array.from({ length: 7 }, (_, weekday) => {
        const bucket = tz.by_weekday.find((b) => b.weekday === weekday)?.stats;
        return {
          weekday: WEEKDAY_LABELS[weekday],
          median: bucket?.median ?? 0,
          mean: bucket?.mean ?? 0,
          n: bucket?.n ?? 0,
          insufficient: bucket?.insufficient_data ?? true,
        };
      }),
    [tz],
  );

  function formatBucketTooltip(
    _value: unknown,
    _name: unknown,
    item: { payload?: { median: number; mean: number; n: number; insufficient: boolean } },
  ): [string, string] {
    const { median, mean, n, insufficient } = item.payload ?? {
      median: 0,
      mean: 0,
      n: 0,
      insufficient: true,
    };
    return [
      `median ${median.toFixed(2)}% · mean ${mean.toFixed(2)}% · n=${n}${insufficient ? " (insufficient data)" : ""}`,
      "Engagement rate",
    ];
  }

  return (
    <div className="rounded-xl border border-border-hairline bg-bg-card p-5">
      <h3 className="text-[13px] font-medium text-text-secondary">{tz.timezone}</h3>
      <p className="mb-4 text-[11px] text-text-muted">
        Median engagement rate by local post hour / weekday — mean shown in tooltip
      </p>

      <div className="h-[180px]">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={hourData} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--rule)" vertical={false} />
            <XAxis dataKey="hour" stroke="var(--text-muted)" fontSize={11} tickLine={false} />
            <YAxis stroke="var(--text-muted)" fontSize={11} tickLine={false} width={36} />
            <Tooltip
              contentStyle={{
                background: "var(--bg-card)",
                border: "1px solid var(--border-hairline)",
                fontSize: 12,
              }}
              formatter={formatBucketTooltip}
              labelFormatter={(hour) => `Hour ${hour}`}
            />
            <Bar dataKey="median" fill="var(--amber-600)" radius={[3, 3, 0, 0]} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="mt-4 h-[160px]">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={weekdayData} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--rule)" vertical={false} />
            <XAxis dataKey="weekday" stroke="var(--text-muted)" fontSize={11} tickLine={false} />
            <YAxis stroke="var(--text-muted)" fontSize={11} tickLine={false} width={36} />
            <Tooltip
              contentStyle={{
                background: "var(--bg-card)",
                border: "1px solid var(--border-hairline)",
                fontSize: 12,
              }}
              formatter={formatBucketTooltip}
            />
            <Bar dataKey="median" fill="var(--amber-700)" radius={[3, 3, 0, 0]} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
