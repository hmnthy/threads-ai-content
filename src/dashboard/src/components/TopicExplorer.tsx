"use client";

import dynamic from "next/dynamic";
import { useEffect, useMemo, useState } from "react";
import type { Data, Layout } from "plotly.js";
import { Info } from "@phosphor-icons/react";
import { getContentUnits, getTopics, type ContentUnit, type Topic } from "@/lib/api";

// plotly.js touches `window` at import time — must load client-side only, never
// during SSR/build (Next.js would otherwise fail `next build`).
const Plot = dynamic(() => import("react-plotly.js"), { ssr: false });

// Không tô 9 cluster bằng 9 màu: trên scatter, không bảng màu nào giữ được ≥3 màu
// phân biệt nổi với người mù màu (skill dataviz, "--pairs all"), và design-system.md
// chỉ có amber. Thay vào đó: mọi điểm xám, topic đang chọn tô --amber-600 — danh
// sách topic (horizontal bar, §9 "Phân bổ topic") là khối chính, bản đồ là phụ.
const UNCLUSTERED = "__unclustered__";

interface Palette {
  highlight: string;
  point: string;
  text: string;
  grid: string;
  card: string;
}

// Plotly vẽ bằng WebGL, không đọc được `var(--token)` — đọc giá trị token thật từ CSS
function readPalette(): Palette {
  const css = getComputedStyle(document.documentElement);
  const token = (name: string) => css.getPropertyValue(name).trim();
  return {
    highlight: token("--amber-600"),
    point: token("--text-muted"),
    text: token("--text-secondary"),
    grid: token("--rule"),
    card: token("--bg-card"),
  };
}

function truncate(text: string, max: number): string {
  return text.length > max ? `${text.slice(0, max)}…` : text;
}

interface TopicRow {
  id: string;
  label: string;
  description: string | null;
  n: number;
}

export function TopicExplorer() {
  const [units, setUnits] = useState<ContentUnit[] | null>(null);
  const [topics, setTopics] = useState<Topic[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  // Đọc token 1 lần lúc mount; server render trả null. Chỉ dùng `palette` cho phần render
  // SAU khi có data (traces/layout) — dùng sớm hơn sẽ lệch hydration giữa server và client.
  const [palette] = useState<Palette | null>(() => (typeof window === "undefined" ? null : readPalette()));

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

  const embedded = useMemo(() => units?.filter((unit) => unit.umap !== null) ?? [], [units]);
  const waiting = (units?.length ?? 0) - embedded.length;
  const unclusteredCount = embedded.filter((unit) => unit.topic === null).length;

  // Tử số và mẫu số cùng 1 nguồn: đếm trên chính các bài đã embed (không dùng
  // `topic.post_count` của backend — nó đếm mọi nhãn, kể cả bài chưa có toạ độ UMAP).
  // Chỉ lấy topic `method='cluster'`: số liệu ở đây là kết quả gom cụm.
  const rows: TopicRow[] = useMemo(() => {
    const counts = new Map<string, number>();
    for (const unit of embedded) {
      if (unit.topic !== null) counts.set(unit.topic.topic_id, (counts.get(unit.topic.topic_id) ?? 0) + 1);
    }
    const clustered = (topics ?? [])
      .filter((topic) => topic.method === "cluster")
      .map((topic) => ({
        id: topic.id,
        label: topic.label_en,
        description: topic.description_en,
        n: counts.get(topic.id) ?? 0,
      }))
      .sort((a, b) => b.n - a.n);
    return [...clustered, { id: UNCLUSTERED, label: "Unclustered", description: null, n: unclusteredCount }];
  }, [topics, embedded, unclusteredCount]);
  const clusterCount = rows.length - 1;

  const activeId = selected ?? rows[0]?.id ?? null;

  const traces: Data[] = useMemo(() => {
    if (palette === null) return [];
    const isActive = (unit: ContentUnit) => (unit.topic?.topic_id ?? UNCLUSTERED) === activeId;
    const labelOf = new Map(rows.map((row) => [row.id, row.label]));
    const trace = (subset: ContentUnit[], color: string, size: number, opacity: number, name: string): Data => ({
      type: "scatter3d",
      mode: "markers",
      name,
      x: subset.map((unit) => unit.umap![0]),
      y: subset.map((unit) => unit.umap![1]),
      z: subset.map((unit) => unit.umap![2]),
      text: subset.map(
        (unit) =>
          `${labelOf.get(unit.topic?.topic_id ?? UNCLUSTERED) ?? "Unclustered"}<br>${truncate(unit.text ?? unit.full_text, 110)}`,
      ),
      hovertemplate: "%{text}<extra></extra>",
      marker: { size, color, opacity },
    });
    const others = embedded.filter((unit) => !isActive(unit));
    const active = embedded.filter(isActive);
    return [
      trace(others, palette.point, 3.5, 0.35, "Other topics"),
      trace(active, palette.highlight, 6, 0.95, labelOf.get(activeId ?? "") ?? "Selected"),
    ];
  }, [embedded, palette, activeId, rows]);

  // Memo + `uirevision` cố định: đổi topic chỉ đổi traces, Plotly giữ nguyên góc xoay
  // người xem đã chỉnh (thiếu uirevision thì mỗi lần chọn topic camera bị reset).
  const layout: Partial<Layout> | null = useMemo(
    () =>
      palette === null
        ? null
        : {
            paper_bgcolor: palette.card,
            font: { color: palette.text, family: "var(--font-inter), system-ui, sans-serif", size: 12 },
            margin: { l: 0, r: 0, t: 0, b: 0 },
            showlegend: false,
            uirevision: "topic-map",
            scene: {
              bgcolor: palette.card,
              xaxis: { title: { text: "" }, showticklabels: false, gridcolor: palette.grid, zerolinecolor: palette.grid },
              yaxis: { title: { text: "" }, showticklabels: false, gridcolor: palette.grid, zerolinecolor: palette.grid },
              zaxis: { title: { text: "" }, showticklabels: false, gridcolor: palette.grid, zerolinecolor: palette.grid },
            },
          },
    [palette],
  );

  if (error !== null) {
    return (
      <div className="rounded-xl border border-border-hairline bg-bg-card p-6 text-negative">
        Could not reach the API at the configured base URL. Is `uvicorn src.main:app` running? ({error})
      </div>
    );
  }

  if (units === null || topics === null) {
    return (
      <div className="flex flex-col gap-4">
        <div className="h-[92px] animate-pulse rounded-xl bg-bg-surface" />
        <div className="h-[420px] animate-pulse rounded-xl bg-bg-surface" />
      </div>
    );
  }

  if (embedded.length === 0) {
    return (
      <div className="rounded-xl border border-border-hairline bg-bg-card p-6 text-text-secondary">
        No content unit has embedding coordinates yet — run the NLP pipeline
        (<code className="text-text-primary">src/nlp/topics.py</code>) to discover topics.
      </div>
    );
  }

  const maxN = Math.max(...rows.map((row) => row.n), 1);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex gap-3 rounded-xl border border-border-hairline bg-bg-surface p-4 text-[13px] leading-snug text-text-secondary">
        <Info size={18} aria-hidden="true" className="mt-0.5 shrink-0 text-text-primary" />
        <p>
          <span className="font-semibold text-text-primary">Provisional clusters.</span> The text each post is
          clustered on currently also includes the author&apos;s replies to followers under that post, which
          blurs topics. A data fix is scheduled; clusters and names will be recomputed after it.
        </p>
      </div>

      <StatRow
        units={units.length}
        topics={clusterCount}
        embedded={embedded.length}
        unclustered={unclusteredCount}
        waiting={waiting}
      />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
        <section className="flex flex-col gap-3 rounded-xl border border-border-hairline bg-bg-card p-5">
          <div className="flex flex-col gap-1">
            <h2 className="text-[15px] font-semibold text-text-primary">Topics by number of posts</h2>
            <p className="text-[13px] leading-snug text-text-secondary">
              Share of the {embedded.length} embedded posts. Names and descriptions are written by an LLM from
              each cluster&apos;s posts. Select a topic to locate it on the map.
            </p>
          </div>
          <ul className="flex flex-col gap-1">
            {rows.map((row) => {
              const active = row.id === activeId;
              const share = embedded.length > 0 ? (row.n / embedded.length) * 100 : 0;
              return (
                <li key={row.id}>
                  <button
                    type="button"
                    aria-pressed={active}
                    onClick={() => setSelected(row.id)}
                    title={row.description ?? undefined}
                    className={`flex min-h-[44px] w-full flex-col gap-1 rounded-[10px] px-3 py-2 text-left transition-colors ${
                      active ? "bg-amber-soft" : "hover:bg-bg-surface"
                    }`}
                  >
                    <div className="flex items-baseline justify-between gap-3">
                      <span
                        className={`text-sm ${
                          row.id === UNCLUSTERED ? "text-text-secondary italic" : "font-medium text-text-primary"
                        }`}
                      >
                        {row.label}
                      </span>
                      <span className="shrink-0 font-mono text-xs tabular-nums text-text-secondary">
                        {row.n} · {share.toFixed(0)}%
                      </span>
                    </div>
                    <div className="h-1.5 w-full overflow-hidden rounded-full bg-bg-surface">
                      <div
                        className={`h-full rounded-full ${active ? "bg-amber-600" : row.id === UNCLUSTERED ? "bg-rule" : "bg-amber-fill"}`}
                        style={{ width: `${row.n === 0 ? 0 : Math.max((row.n / maxN) * 100, 2)}%` }}
                      />
                    </div>
                  </button>
                </li>
              );
            })}
          </ul>
        </section>

        <section className="flex flex-col gap-2 rounded-xl border border-border-hairline bg-bg-card p-3">
          <div className="h-[56vh] min-h-[420px]">
            {layout !== null && (
              <Plot
                data={traces}
                layout={layout}
                config={{ displaylogo: false, responsive: true }}
                style={{ width: "100%", height: "100%" }}
              />
            )}
          </div>
          <p className="px-2 pb-1 text-xs leading-snug text-text-muted">
            UMAP projection of the post embeddings into 3 dimensions — drag to rotate. Posts close together are
            similar; axes have no unit, and distances between clusters are not meaningful.
          </p>
        </section>
      </div>
    </div>
  );
}

function StatRow({
  units,
  topics,
  embedded,
  unclustered,
  waiting,
}: {
  units: number;
  topics: number;
  embedded: number;
  unclustered: number;
  waiting: number;
}) {
  const unclusteredShare = embedded > 0 ? Math.round((unclustered / embedded) * 100) : 0;
  const stats = [
    { label: "Content units", value: units.toString(), detail: `${embedded} embedded` },
    { label: "Topic clusters", value: topics.toString(), detail: "found by HDBSCAN, no labels given" },
    {
      label: "Unclustered",
      value: `${unclusteredShare}%`,
      detail: `${unclustered} of ${embedded} embedded posts fit no cluster`,
    },
  ];

  return (
    <div className="flex flex-col gap-2">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        {stats.map((stat) => (
          <div key={stat.label} className="rounded-xl border border-border-hairline bg-bg-card p-5">
            <div className="text-xs font-medium text-text-muted">{stat.label}</div>
            <div className="mt-1 text-[28px] font-bold tabular-nums text-text-primary">{stat.value}</div>
            <div className="mt-1 font-mono text-xs tabular-nums text-text-muted">{stat.detail}</div>
          </div>
        ))}
      </div>
      {waiting > 0 && (
        <p className="text-xs text-text-muted">
          {waiting} newest {waiting === 1 ? "post is" : "posts are"} waiting for the next NLP run and not shown yet.
        </p>
      )}
    </div>
  );
}
