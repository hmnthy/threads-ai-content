"use client";

import { useEffect, useState } from "react";
import { getAnalyticsOverview, type AnalyticsOverview, type TopPostEntry } from "@/lib/api";
import { DistributionCaption } from "@/components/DistributionCaption";
import { PostingTimeHeatmap } from "@/components/PostingTimeHeatmap";
import { formatPostDateTimeParis } from "@/lib/dates";

type MetricKey = "engagement" | "share" | "conversation";

const METRIC_TABS: { key: MetricKey; label: string; field: keyof TopPostEntry["metrics"] }[] = [
  { key: "engagement", label: "Top by engagement", field: "engagement_rate" },
  { key: "share", label: "Top by share rate", field: "share_rate" },
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
      : activeMetric === "share"
        ? data.top_by_share_rate
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

      <PostingTimeHeatmap timezones={data.timezones} excludedNoViews={data.excluded_no_views} />
    </div>
  );
}

function StatRow({ data }: { data: AnalyticsOverview }) {
  const { engagement } = data;
  const stats = [
    {
      label: "Root posts analyzed",
      value: data.post_count.toLocaleString("en-US"),
      detail:
        data.excluded_no_views > 0
          ? `${data.excluded_no_views} more excluded: no views recorded`
          : "posts with an insight snapshot",
    },
    {
      label: "Median engagement rate",
      value: engagement.n === 0 ? "—" : formatPercent(engagement.median),
      detail: <DistributionCaption stats={engagement} />,
    },
  ];

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
      {stats.map((stat) => (
        <div key={stat.label} className="rounded-xl border border-border-hairline bg-bg-card p-5">
          <div className="text-xs font-medium text-text-muted">{stat.label}</div>
          <div className="mt-1 font-mono text-[28px] font-bold tabular-nums text-text-primary">
            {stat.value}
          </div>
          <div className="mt-1 font-mono text-xs tabular-nums text-text-muted">{stat.detail}</div>
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
    <div className="flex flex-col gap-3">
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="text-left text-[11px] font-semibold text-text-muted">
              <th className="pb-2 pr-3 font-medium">#</th>
              <th className="pb-2 pr-4 font-medium">Post</th>
              <th className="pb-2 pr-4 font-medium">Posted (Paris time)</th>
              <th className="pb-2 pr-4 text-right font-medium">Views</th>
              <th className="pb-2 font-medium">Rate</th>
            </tr>
          </thead>
          <tbody>
            {entries.map((entry, index) => {
              const value = entry.metrics[field];
              const width = maxValue > 0 ? Math.max((value / maxValue) * 100, 2) : 0;
              return (
                <tr key={entry.id} className="border-t border-border-hairline hover:bg-bg-surface">
                  <td className="py-2 pr-3 font-mono tabular-nums text-text-muted">
                    {(index + 1).toString().padStart(2, "0")}
                  </td>
                  <td className="max-w-[420px] py-2 pr-4 text-text-primary">
                    {truncate(entry.text ?? "(no text)", 90)}
                  </td>
                  <td className="py-2 pr-4 font-mono whitespace-nowrap text-text-secondary">
                    {formatPostDateTimeParis(entry.timestamp)}
                  </td>
                  <td className="py-2 pr-4 text-right font-mono tabular-nums text-text-secondary">
                    {entry.metrics.popularity_index.toLocaleString("en-US")}
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
      <p className="text-[13px] leading-snug text-text-muted">
        Ranked by rate, so a post with few views can reach the top by chance — read the Views column
        alongside it.
      </p>
    </div>
  );
}
