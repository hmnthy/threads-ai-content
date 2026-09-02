"use client";

import dynamic from "next/dynamic";
import { useEffect, useMemo, useState } from "react";
import type { Data, Layout } from "plotly.js";
import { getContentUnits, getTopics, type ContentUnit, type Topic } from "@/lib/api";

// plotly.js touches `window` at import time — must load client-side only, never
// during SSR/build (Next.js would otherwise fail `next build`).
const Plot = dynamic(() => import("react-plotly.js"), { ssr: false });

// Palette xoay vòng cho từng topic — dựa trên --accent-purple/--color-positive/
// --color-negative của design-system.md, mở rộng thêm vài tông để phân biệt nhiều
// cluster hơn 3 màu gốc.
const TOPIC_COLORS = [
  "#7c3aed", // accent-purple
  "#22c55e", // color-positive
  "#f59e0b", // amber
  "#38bdf8", // sky
  "#ec4899", // pink
  "#a78bfa", // accent-purple-soft
  "#ef4444", // color-negative
  "#14b8a6", // teal
];
const UNCLUSTERED_COLOR = "#525252"; // text-muted

const PLOTLY_LAYOUT: Partial<Layout> = {
  paper_bgcolor: "#141414",
  plot_bgcolor: "#141414",
  font: { color: "#a3a3a3", family: "var(--font-inter), system-ui, sans-serif", size: 12 },
  margin: { l: 0, r: 0, t: 0, b: 0 },
  scene: {
    xaxis: { title: { text: "UMAP 1" }, gridcolor: "#2a2a2a", zerolinecolor: "#2a2a2a" },
    yaxis: { title: { text: "UMAP 2" }, gridcolor: "#2a2a2a", zerolinecolor: "#2a2a2a" },
    zaxis: { title: { text: "UMAP 3" }, gridcolor: "#2a2a2a", zerolinecolor: "#2a2a2a" },
    bgcolor: "#141414",
  },
  legend: { font: { color: "#a3a3a3" } },
};

function truncate(text: string, max: number): string {
  return text.length > max ? `${text.slice(0, max)}…` : text;
}

export function TopicExplorer() {
  const [units, setUnits] = useState<ContentUnit[] | null>(null);
  const [topics, setTopics] = useState<Topic[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([getContentUnits(), getTopics()])
      .then(([fetchedUnits, fetchedTopics]) => {
        setUnits(fetchedUnits);
        setTopics(fetchedTopics);
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : "Failed to load data from the API.");
      });
  }, []);

  const plotted = useMemo(() => units?.filter((unit) => unit.umap !== null) ?? [], [units]);
  const withoutEmbedding = useMemo(() => (units?.length ?? 0) - plotted.length, [units, plotted]);

  const traces: Data[] = useMemo(() => {
    const byTopic = new Map<string, ContentUnit[]>();
    for (const unit of plotted) {
      const key = unit.topic?.topic_id ?? "__unclustered__";
      const bucket = byTopic.get(key) ?? [];
      bucket.push(unit);
      byTopic.set(key, bucket);
    }

    const topicLabels = new Map((topics ?? []).map((topic) => [topic.id, topic.label_en]));
    let colorIndex = 0;

    return Array.from(byTopic.entries()).map(([topicId, groupUnits]) => {
      const isUnclustered = topicId === "__unclustered__";
      const color = isUnclustered ? UNCLUSTERED_COLOR : TOPIC_COLORS[colorIndex++ % TOPIC_COLORS.length];

      return {
        type: "scatter3d",
        mode: "markers",
        name: isUnclustered ? "Unclustered" : (topicLabels.get(topicId) ?? topicId),
        x: groupUnits.map((unit) => unit.umap![0]),
        y: groupUnits.map((unit) => unit.umap![1]),
        z: groupUnits.map((unit) => unit.umap![2]),
        text: groupUnits.map((unit) => truncate(unit.full_text, 140)),
        hovertemplate: "%{text}<extra></extra>",
        marker: { size: 5, color, opacity: isUnclustered ? 0.4 : 0.85 },
      } satisfies Data;
    });
  }, [plotted, topics]);

  if (error !== null) {
    return (
      <div className="rounded-[10px] border border-bg-border bg-bg-surface p-6 text-negative">
        Could not reach the API at the configured base URL. Is `uvicorn src.main:app` running? ({error})
      </div>
    );
  }

  if (units === null || topics === null) {
    return (
      <div className="rounded-[10px] border border-bg-border bg-bg-surface p-6 text-text-secondary">
        Loading content units…
      </div>
    );
  }

  if (plotted.length === 0) {
    return (
      <div className="rounded-[10px] border border-bg-border bg-bg-surface p-6 text-text-secondary">
        No content unit has embedding coordinates yet — run the NLP pipeline
        (<code className="text-text-primary">src/nlp/topics.py</code>) to populate UMAP coordinates
        before this scatter can render.
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <StatRow units={units} topics={topics} withoutEmbedding={withoutEmbedding} />
      <div className="h-[70vh] min-h-[480px] rounded-[10px] border border-bg-border bg-bg-surface p-2">
        <Plot
          data={traces}
          layout={PLOTLY_LAYOUT}
          config={{ displaylogo: false, responsive: true }}
          style={{ width: "100%", height: "100%" }}
        />
      </div>
    </div>
  );
}

function StatRow({
  units,
  topics,
  withoutEmbedding,
}: {
  units: ContentUnit[];
  topics: Topic[];
  withoutEmbedding: number;
}) {
  const stats = [
    { label: "Content units", value: units.length },
    { label: "Topics discovered", value: topics.length },
    { label: "Without embedding yet", value: withoutEmbedding },
  ];

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
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
