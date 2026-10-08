"use client";

import { useState } from "react";
import { SectionHead, type RoadmapStatus } from "@/components/LandingParts";
import { count, type LandingData } from "@/lib/landing";

// Sơ đồ "How it works" trên dải tối (handoff §3.5, design-system §2.6). Toạ độ, nhãn, mô tả
// node theo mockup; số liệu sống (vai reply, lần gom cụm) đọc từ /pipeline/summary.
// Bộ phân loại RQ-08 chỉ là nhánh research, không nối vào HDBSCAN (UI-0001-classifier-research);
// tầng dữ liệu chỉ có SQLite (UI-0010-sqlite-only); lịch NLP theo giờ máy (UI-0017-nlp-schedule).

type Edge = `e${1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12}`;

interface Node {
  id: string;
  name: string;
  tag: string;
  x: number;
  y: number;
  w: number;
  h: number;
  status: RoadmapStatus;
  ext?: boolean;
  dashed?: boolean;
  dotted?: boolean;
  body: string;
  stack: [string, string][];
  edges: Edge[];
}

function buildNodes(data: LandingData | null): Node[] {
  const roles = data?.summary.reply_roles;
  const run = data?.summary.latest_cluster_run ?? null;
  const p = run?.params ?? {};
  const dbcv = run?.dbcv == null ? "not computed (fewer than 2 clusters)" : run.dbcv.toFixed(3);
  return [
    { id: "threads", name: "Threads Graph API", tag: "external", x: 0, y: 32, w: 170, h: 100, status: "live", ext: true,
      body: "The only data source. Posts, replies, per-post insights and daily account views are read through the official API with a long-lived token.",
      stack: [["endpoints", "threads · replies · conversation · insights"], ["metrics", "views · likes · replies · reposts · quotes"]], edges: ["e1"] },
    { id: "collect", name: "Collect", tag: "ingest.py", x: 230, y: 32, w: 200, h: 100, status: "live",
      body: "Every 4 hours, while the machine is awake, a headless job pulls new posts and fresh insight snapshots. Reply roles are rebuilt from the replied_to graph, never from timestamps, and each post gets a clean full_text.",
      stack: [["client", "httpx (async) · pydantic v2"], ["schedule", "Task Scheduler + pythonw"],
        ...(roles ? [["roles", `${count(roles.self_continuation)} self_continuation · ${count(roles.author_answer)} author_answer · ${count(roles.outbound)} outbound`] as [string, string]] : [])],
      edges: ["e1", "e2"] },
    { id: "store", name: "SQLite", tag: "data/threads.db", x: 490, y: 32, w: 190, h: 100, status: "live",
      body: "One file holds posts, content units, insight snapshots over time, embeddings and every clustering run with its parameters and scores. It is the only database.",
      stack: [["tables", "posts · content_units · insights_snapshots"], ["", "embeddings · topics · cluster_runs"]], edges: ["e2", "e3", "e5", "e8", "e10"] },
    { id: "api", name: "API", tag: "FastAPI", x: 740, y: 32, w: 170, h: 100, status: "live",
      body: "Read-only. Serves posts, insights, topics and channel statistics from what the jobs stored. Posts with no recorded views are excluded and counted. Per-topic comparisons are next.",
      stack: [["server", "FastAPI + uvicorn"], ["statistics", "median/IQR live · Mann-Whitney U + Cliff's δ + bootstrap CI + Holm in src/analysis · per-topic tests next"]], edges: ["e3", "e4"] },
    { id: "web", name: "Dashboard · Landing", tag: "Next.js 16", x: 966, y: 32, w: 170, h: 100, status: "live",
      body: "The dashboard and this page. Charts are hand-built SVG; the topic map uses Plotly.",
      stack: [["framework", "Next.js 16 · Tailwind v4"], ["charts", "SVG · Plotly"], ["icons", "Phosphor"]], edges: ["e4", "e11"] },
    { id: "embed", name: "Embed", tag: "bge-m3", x: 230, y: 316, w: 140, h: 94, status: "live",
      body: "Each full_text is embedded once and re-embedded only when its content hash changes. Language detection and the Code-Mixing Index run in the same step.",
      stack: [["model", run ? `${run.model_id}${run.embedding_dim ? ` · ${run.embedding_dim}D` : ""}` : "BAAI/bge-m3"], ["language", "lingua-py + Code-Mixing Index"]], edges: ["e5", "e6", "e12"] },
    { id: "cluster", name: "Cluster", tag: "UMAP + HDBSCAN", x: 390, y: 316, w: 140, h: 94, status: "live",
      body: "Embeddings are reduced to 3 dimensions and clustered by density. Posts that fit no cluster stay labelled as noise instead of being forced into one.",
      stack: run
        ? [["reduce", `UMAP ${p.umap_n_components ?? "?"}D · n_neighbors ${p.umap_n_neighbors ?? "?"} · seed ${p.umap_random_state ?? "?"}`],
           ["cluster", `HDBSCAN ${p.cluster_selection_method ?? "?"} · min_cluster_size ${p.hdbscan_min_cluster_size ?? "?"}`],
           ["result", `${run.n_clusters} clusters · noise ${(run.noise_ratio * 100).toFixed(1)}% of ${count(run.n_units)} embedded · validity_index (DBCV) ${dbcv}`]]
        : [["result", "no clustering run stored yet"]],
      edges: ["e6", "e7"] },
    { id: "name", name: "Name", tag: "topic_profile.py · topics.py", x: 550, y: 316, w: 140, h: 94, status: "live",
      body: "Each topic gets c-TF-IDF keywords and its 3 posts nearest the centre for reading. Claude is called only for topics that need a name or a new one: it receives up to 15 posts nearest the centre, text only, and returns a short English name and description. It does not classify or embed.",
      stack: [["profile", "c-TF-IDF keywords · 3 nearest posts"], ["naming", "Claude API · up to 15 nearest posts, no keywords"], ["output", "topic_N · name history · centroid_similarity per post"]], edges: ["e7", "e8", "e9"] },
    { id: "claude", name: "Claude API", tag: "external", x: 740, y: 316, w: 170, h: 94, status: "live", ext: true,
      body: "Called only when a topic is new, split, merged, has drifted, or was named under an older setup. It receives up to 15 of that topic's posts nearest the centre. No keywords are sent.",
      stack: [["used for", "cluster names and descriptions only"]], edges: ["e9"] },
    { id: "kb", name: "Knowledge base", tag: "src/kb/", x: 966, y: 312, w: 170, h: 98, status: "next", dashed: true,
      body: "Posts and author answers as one searchable index: keyword and dense retrieval fused, then reranked. It will be scored on a test set of real questions, once a privacy decision is made, before any chatbot is built on top.",
      stack: [["retrieval", "SQLite FTS5 (BM25) + dense numpy + RRF"], ["rerank", "bge-reranker-v2-m3"], ["gate (provisional)", "recall@10 ≥ 0.80 · nDCG@10 ≥ 0.60"]], edges: ["e10", "e11"] },
    { id: "clf", name: "Classifier", tag: "RQ-08", x: 740, y: 444, w: 170, h: 56, status: "research", dotted: true,
      body: "Whether 6 fixed labels can be learned from the embeddings. A research question with its own hand-labelled set, not a product component.",
      stack: [["plan", "baseline ladder → SVM-RBF · nested CV · Cohen's κ"]], edges: ["e12"] },
  ];
}

const EDGES: { id: Edge; d: string; dash?: string }[] = [
  { id: "e1", d: "M170,82 H226" },
  { id: "e2", d: "M430,82 H486" },
  { id: "e3", d: "M680,82 H736" },
  { id: "e4", d: "M910,82 H962" },
  { id: "e5", d: "M520,132 V200 H300 V316" },
  { id: "e6", d: "M370,362 H386" },
  { id: "e7", d: "M530,362 H546" },
  { id: "e8", d: "M620,316 V136" },
  { id: "e9", d: "M690,350 H736" },
  { id: "e9", d: "M736,374 H694" },
  { id: "e10", d: "M665,132 V230 H1020 V312", dash: "5 5" },
  { id: "e11", d: "M1090,312 V136", dash: "5 5" },
  { id: "e12", d: "M300,410 V474 H736", dash: "2 4" },
];

const EDGE_LABELS = [
  { x: 356, y: 186, text: "full_text" },
  { x: 628, y: 220, text: "topics, labels" },
  { x: 820, y: 212, text: "posts + answers" },
  { x: 330, y: 478, text: "embeddings" },
];

export function LandingTechStack({ data }: { data: LandingData | null }) {
  const nodes = buildNodes(data);
  const [selectedId, setSelectedId] = useState("cluster");
  const selected = nodes.find((n) => n.id === selectedId)!;
  const active = new Set(selected.edges);

  return (
    <section
      id="method"
      data-screen-label="05 How it works"
      className="on-dark scroll-mt-[72px] bg-dark-bg text-dark-text"
    >
      <div className="mx-auto box-border flex max-w-[1200px] flex-col gap-9 px-4 py-[104px] sm:px-8">
        <SectionHead eyebrow="04 · How it works" title="From the Threads API to this page." onDark>
          Two scheduled jobs write to one SQLite file. A read-only API serves it. Select a step to
          see what runs there.
        </SectionHead>

        <div className="-mx-2 overflow-x-auto px-2">
          <div className="relative h-[500px] w-[1136px]">
            <div className="absolute left-[210px] top-[262px] h-[200px] w-[500px] rounded-2xl border border-dashed border-white/20" />
            <span className="absolute left-[226px] top-[272px] font-mono text-[11.5px] font-medium text-dark-text-muted">
              daily 12:30 (machine time) · WSL2
            </span>
            <span className="absolute left-[230px] top-2.5 font-mono text-[11.5px] font-medium text-dark-text-muted">
              every 4h while the machine is awake · Task Scheduler
            </span>
            <svg
              width="1136"
              height="500"
              viewBox="0 0 1136 500"
              className="absolute inset-0 overflow-visible"
              aria-hidden="true"
            >
              <defs>
                <marker id="ah" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="8" markerHeight="8" orient="auto">
                  <path d="M0,0 L8,4 L0,8 z" fill="rgba(255,255,255,0.5)" />
                </marker>
                <marker id="aa" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="8" markerHeight="8" orient="auto">
                  <path d="M0,0 L8,4 L0,8 z" fill="var(--amber-on-dark)" />
                </marker>
              </defs>
              {EDGES.map((edge, i) => {
                const on = active.has(edge.id);
                return (
                  <path
                    key={i}
                    d={edge.d}
                    fill="none"
                    stroke={on ? "var(--amber-on-dark)" : "var(--dark-line-strong)"}
                    strokeWidth={1.5}
                    strokeDasharray={edge.dash}
                    markerEnd={on ? "url(#aa)" : "url(#ah)"}
                  />
                );
              })}
            </svg>
            {EDGE_LABELS.map((label) => (
              <span
                key={label.text}
                className="absolute whitespace-nowrap font-mono text-[11px] text-dark-text-muted"
                style={{ left: label.x, top: label.y }}
              >
                {label.text}
              </span>
            ))}
            {nodes.map((node) => {
              const on = node.id === selectedId;
              const border = on
                ? "border-[1.5px] border-solid border-amber-on-dark"
                : node.dashed
                  ? "border-[1.5px] border-dashed border-white/40"
                  : node.dotted
                    ? "border-[1.5px] border-dotted border-white/40"
                    : node.ext
                      ? "border border-white/20"
                      : "border border-dark-line";
              const bg = on ? "bg-amber-on-dark-fill" : node.ext ? "bg-transparent" : "bg-dark-node";
              return (
                <button
                  key={node.id}
                  type="button"
                  onClick={() => setSelectedId(node.id)}
                  aria-pressed={on}
                  className={`absolute box-border flex cursor-pointer flex-col items-start justify-center gap-1 rounded-xl px-3.5 text-left text-dark-text ${border} ${bg}`}
                  style={{ left: node.x, top: node.y, width: node.w, height: node.h }}
                >
                  <span
                    className={`text-sm font-semibold ${node.dashed || node.dotted ? "text-dark-text-secondary" : "text-dark-text"}`}
                  >
                    {node.name}
                  </span>
                  <span className={`font-mono text-[11px] ${on ? "text-amber-on-dark" : "text-dark-text-muted"}`}>
                    {node.tag}
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        <div
          className="grid grid-cols-[repeat(auto-fit,minmax(min(100%,320px),1fr))] gap-7 border-t border-dark-line pt-7"
          aria-live="polite"
        >
          <div className="flex flex-col gap-2.5">
            <div className="flex items-center gap-3">
              <span className="text-[22px] font-bold tracking-[-0.02em]">{selected.name}</span>
              <span
                className={`rounded-full px-2.5 py-[3px] text-[11px] font-medium ${
                  selected.status === "live"
                    ? "bg-amber-on-dark/20 text-amber-soft"
                    : "bg-white/10 text-dark-text"
                }`}
              >
                {selected.status}
              </span>
            </div>
            <p className="m-0 text-[15px] leading-[1.65] text-dark-text-secondary [text-wrap:pretty]">
              {selected.body}
            </p>
          </div>
          <div className="flex flex-col">
            {selected.stack.map(([key, value], i) => (
              <div
                key={i}
                className="grid grid-cols-[104px_minmax(0,1fr)] items-baseline gap-3 border-b border-white/10 py-2.5"
              >
                <span className="text-xs text-dark-text-muted">{key}</span>
                <span className="font-mono text-[13px] leading-[1.5] text-amber-on-dark-text">{value}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-6 border-t border-dark-line pt-5 text-[12.5px] text-dark-text-secondary">
          <span className="flex items-center gap-2">
            <span className="w-6 border-t-[1.5px] border-solid border-white/50" />
            live
          </span>
          <span className="flex items-center gap-2">
            <span className="w-6 border-t-[1.5px] border-dashed border-white/50" />
            next
          </span>
          <span className="flex items-center gap-2">
            <span className="w-6 border-t-[1.5px] border-dotted border-white/50" />
            research
          </span>
          <span className="ml-auto font-mono text-dark-text-muted">
            {/* mockup ghi "7 pre-commit gates" — bỏ số đếm tay để khỏi trôi (docs.md) */}
            ruff · mypy strict · pytest · pre-commit gates
          </span>
        </div>
      </div>
    </section>
  );
}
