"use client";

import { useMemo, useState } from "react";
import { ArrowDown } from "@phosphor-icons/react";
import { AnswerRow, Bullets, MethodSection, Section, SubSection, TermLink, TYPE, type KeyNumber } from "@/components/AppBlock";
import { TopicEngagementPanel } from "@/components/LandingProof";
import { TopicComparisonTable } from "@/components/TopicComparisonTable";
import { TopicMap3D } from "@/components/TopicMap3D";
import { TopicMethods } from "@/components/TopicMethods";
import type { ContentUnit } from "@/lib/api";
import { count, dayMonthYear, firstLine, parisDate, pct, UNIT_NOUN, type LandingData } from "@/lib/landing";
import { topicMark } from "@/lib/topicColors";
import { sectionShort } from "@/lib/topicSections";

// Trang /topics (ADR-0023 1a): "kênh viết về gì, và có topic nào có engagement khác phần còn lại
// của kênh không?". Tầng A (card 12px viền hairline, design-system §7). Dựng lại 2026-10-29 theo
// luật "trình bày như nhà nghiên cứu NLP" (.claude/rules/dashboard.md) sau khi Thy bác bản đầu:
// mỗi khối = số + tiêu đề h2 + mục đích → câu trả lời (khung nhấn) + ý chính + số chính (cột phải) →
// các mục h3 (bằng chứng) → "Method and limits" MỞ SẴN; công thức đầy đủ ở khối cuối (`TopicMethods`).
// Lần bác thứ 2 (Thy 2026-10-29): tiêu đề phải lớn hơn nội dung và tách khối rõ để đọc nhanh không sót
// — thang chữ `TYPE` (AppBlock.tsx); bản đồ bên trái, mỗi topic 1 màu (lib/topicColors.ts).
const noun = UNIT_NOUN;
const H4 = TYPE.h4;

// Ô màu + hình của topic (chú giải cho bản đồ): tròn cho 8 topic đầu, thoi cho 9–16, vuông cho 17–24
function Swatch({ index, size = 12 }: { index: number; size?: number }) {
  const mark = topicMark(index);
  return (
    <span
      aria-hidden="true"
      className={`inline-block shrink-0 ${
        mark.shape === "circle" ? "rounded-full" : mark.shape === "diamond" ? "rotate-45 rounded-[2px]" : "rounded-[2px]"
      }`}
      style={{ width: size * (mark.shape === "circle" ? 1 : 0.8), height: size * (mark.shape === "circle" ? 1 : 0.8), background: mark.cssVar }}
    />
  );
}

function share(part: number, whole: number): string {
  return whole > 0 ? `${Math.round((part * 100) / whole)}%` : "—";
}

export function TopicsView({ data, units }: { data: LandingData; units: ContentUnit[] }) {
  return (
    <div className="flex flex-col gap-10">
      <PageIntro data={data} units={units} />
      <TopicProfilePanel data={data} units={units} />
      <TopicEngagementPanel data={data} variant="app" noun={noun} />
      <TopicComparisonTable data={data} noun={noun} />
      <StabilityPanel data={data} />
      <TopicMethods
        run={data.summary.latest_cluster_run}
        method={data.topicTests?.method ?? null}
        minPosts={data.summary.min_posts_to_compare}
      />
    </div>
  );
}

function PageIntro({ data, units }: { data: LandingData; units: ContentUnit[] }) {
  const run = data.summary.latest_cluster_run;
  const total = data.summary.content_units;
  const noText = data.summary.units_without_text;
  // Bài có chữ nhưng chưa qua lần chạy NLP (umap null) — đếm riêng, không gộp vào nhiễu
  // (UI-L20260830-precomputed, UI-L20260902-no-text-excluded)
  const waiting = units.filter((unit) => unit.umap === null && unit.full_text.trim()).length;
  const chain: KeyNumber[] = [
    {
      value: count(total),
      label: "content units",
      note: (
        <>
          Every content unit collected so far, as of the latest <TermLink term="snapshot">snapshot</TermLink>.
        </>
      ),
      term: "content-unit",
    },
  ];
  if (run) {
    chain.push(
      {
        value: count(run.n_units),
        label: "with text, in the latest clustering run",
        note:
          noText > 0
            ? `${noText} have no text to embed (for example, a repost with no caption)${data.sameExcludedPosts ? "; the same ones have no recorded views either" : ""}.`
            : "Every content unit has text.",
        term: "embedding",
      },
      {
        value: count(run.n_units - run.n_noise),
        label: `in ${run.n_clusters} topics`,
        note: `The other ${count(run.n_noise)} fit no topic and stay unclustered.`,
        term: "hdbscan",
      },
    );
  }
  return (
    <Section
      id="intro"
      n="01"
      short={sectionShort("intro")}
      title="How to read this page"
      purpose="Defines the unit every number counts, and how each block below is organised."
    >
      <AnswerRow
        answer="Every count and rate on this page is about content units: one post as published, plus the follow-up parts its author added in the same thread."
        points={[
          "**Comments are left out**, including the author's own replies to followers, so topics reflect what was published, not the conversation under it.",
          "**Rates are per 100 views of the opening post**: engagement counts likes, replies, reposts and quotes; share counts reposts and quotes; conversation counts replies.",
          "Each block below asks **one question**, answers it in one line, then shows the evidence and, open underneath, the method and its limits.",
          <>
            Every term and formula is defined in the last block,{" "}
            <a href="#terms" className="font-medium text-amber-700 underline underline-offset-4">
              How every number on this page is computed
            </a>
            .
          </>,
          !data.sameExcludedPosts && data.channel.excluded > 0
            ? `${data.channel.excluded} of ${count(data.channel.total)} excluded: no views recorded. No rate includes them.`
            : null,
          waiting > 0
            ? `${waiting} ${waiting === 1 ? "content unit was" : "content units were"} published after the latest clustering run and ${waiting === 1 ? "waits" : "wait"} for the next one.`
            : null,
        ]}
        keyNumbers={chain}
      />
    </Section>
  );
}

function TopicProfilePanel({ data, units }: { data: LandingData; units: ContentUnit[] }) {
  const run = data.summary.latest_cluster_run;
  const [sel, setSel] = useState<string>(data.topics[0].id);
  const selected = data.topics.find((t) => t.id === sel) ?? data.topics[0];
  const embedded = useMemo(() => units.filter((unit) => unit.umap !== null), [units]);
  // Tử số và mẫu số cùng 1 nguồn: đếm trên chính các unit đã embed (không dùng post_count)
  const countOf = useMemo(() => {
    const counts = new Map<string, number>();
    for (const unit of embedded) {
      if (unit.topic) counts.set(unit.topic.topic_id, (counts.get(unit.topic.topic_id) ?? 0) + 1);
    }
    return counts;
  }, [embedded]);
  const labelOf = useMemo(() => new Map(data.topics.map((t) => [t.id, t.name])), [data.topics]);
  const maxN = Math.max(...data.topics.map((t) => countOf.get(t.id) ?? 0), 1);
  const topicIds = useMemo(() => data.topics.map((t) => t.id), [data.topics]);
  const selectedIndex = Math.max(0, topicIds.indexOf(selected.id));
  const inRun = embedded.length;
  const unclustered = embedded.filter((unit) => unit.topic === null).length;
  // Tham số thiếu trong API → câu viết bằng chữ (như TopicMethods), không hiện "?"
  const param = (key: string, fallback: string) => {
    const value = run?.params[key];
    return value === undefined || value === null ? fallback : String(value);
  };

  return (
    <Section
      id="topics"
      n="02"
      short={sectionShort("topics")}
      title="What does the channel write about?"
      purpose="Groups the content units into topics from their text alone, then shows each topic's words, its most typical content units and where it sits on the map."
    >
      <AnswerRow
        answer={
          run
            ? run.n_noise === 0
              ? `${run.n_clusters} topics cover every content unit in the latest clustering run.`
              : `${run.n_clusters} topics cover ${count(run.n_units - run.n_noise)} of the ${count(run.n_units)} content units in the latest clustering run (${share(run.n_units - run.n_noise, run.n_units)}).`
            : "No clustering run is stored yet."
        }
        points={[
          "Topics are found from the **text alone** (no predefined categories, no views or interactions), so comparing their engagement afterwards is not circular.",
          "Content units that fit no topic are **kept apart as unclustered**, not forced into the nearest topic.",
          "**Select a topic** to see its keywords, its most typical content units and where it sits on the map.",
        ]}
        keyNumbers={
          run
            ? [
                {
                  value: `${run.n_clusters}`,
                  label: "topics",
                  note: `Groups of similar texts found by a density-based clustering method (HDBSCAN); each needs at least ${param("hdbscan_min_cluster_size", "a minimum number of")} content units.`,
                  term: "topic",
                },
                {
                  value: `${count(unclustered)} of ${count(inRun)}`,
                  label: "unclustered",
                  note: `${share(unclustered, inRun)}: no dense group around them, so they are kept apart.`,
                  term: "hdbscan",
                },
              ]
            : undefined
        }
      />

      <SubSection
        title="Topics and their map"
        note="Each colour is one topic. Select a topic in the list to highlight it on the map and open its profile below."
      >
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,7fr)_minmax(0,5fr)]">
          <div className="flex flex-col gap-3">
            <h4 className={`m-0 ${H4}`}>Map of the content units</h4>
            <TopicMap3D units={embedded} activeId={selected.id} labelOf={labelOf} topicIds={topicIds} />
            <Bullets
              tone="muted"
              items={[
                <>
                  Each dot is one content unit, placed by the {param("umap_n_components", "few")} numbers{" "}
                  <TermLink term="umap">UMAP</TermLink> computed from its text. Drag to rotate; hover a dot to read it.
                </>,
                "**Colour and shape name the topic** (see the list); the selected topic has larger dots. Grey rings are unclustered.",
                "Nearby dots have similar meaning; the axes have no units, and far-apart topics are not necessarily more different.",
              ]}
            />
          </div>

          <div className="flex flex-col gap-3">
            <div className="flex flex-col gap-0.5 sm:flex-row sm:items-baseline sm:justify-between sm:gap-3">
              <h4 className={`m-0 ${H4}`}>Topics (select one)</h4>
              <span className={TYPE.label}>content units · % of {count(inRun)}</span>
            </div>
            <ul className="m-0 flex list-none flex-col gap-0.5 p-0">
              {data.topics.map((t, i) => {
                const n = countOf.get(t.id) ?? 0;
                const on = t.id === selected.id;
                return (
                  <li key={t.id}>
                    {/* < sm: tên 1 dòng đủ rộng, bar + số xuống dòng dưới */}
                    <button
                      type="button"
                      onClick={() => setSel(t.id)}
                      aria-pressed={on}
                      className={`grid min-h-[44px] w-full cursor-pointer grid-cols-[16px_minmax(0,1fr)_64px] items-center gap-x-3 gap-y-1 rounded-[10px] border px-2.5 py-1.5 text-left xl:grid-cols-[16px_minmax(0,1fr)_minmax(40px,90px)_64px] ${
                        on ? "border-text-primary bg-bg-sunken" : "border-transparent bg-transparent hover:bg-bg-surface"
                      }`}
                    >
                      <Swatch index={i} />
                      <span className={`col-span-2 xl:col-span-1 text-[15px] leading-[1.35] ${on ? "font-semibold text-text-primary" : "text-text-primary"}`}>
                        {t.name}
                      </span>
                      <span className="relative col-start-2 h-1.5 overflow-hidden rounded-full bg-bg-surface xl:col-start-auto">
                        <span
                          className="absolute inset-y-0 left-0 rounded-full"
                          style={{ width: `${(n / maxN) * 100}%`, background: topicMark(i).cssVar }}
                        />
                      </span>
                      <span className={`text-right ${TYPE.mono} text-text-secondary`}>
                        {n} · {share(n, inRun)}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
            <span className={`grid grid-cols-[16px_minmax(0,1fr)_auto] items-center gap-x-3 px-2.5 pt-1 text-[15px] text-text-muted`}>
              <span aria-hidden="true" className="box-border inline-block h-3 w-3 rounded-full border-[1.5px] border-chart-dot" />
              <span>Unclustered</span>
              <span className={TYPE.mono}>
                {unclustered} · {share(unclustered, inRun)}
              </span>
            </span>
          </div>
        </div>
      </SubSection>

      <TopicProfile selected={selected} index={selectedIndex} count={countOf.get(selected.id) ?? 0} inRun={inRun} />

      <UnitTable embedded={embedded} data={data} selectedId={selected.id} selectedName={selected.name} labelOf={labelOf} />

      <MethodSection
        steps={[
          {
            title: "Text",
            plain: "The full text of each content unit: the opening post plus the author's follow-up parts. Content units without text are left out.",
          },
          {
            title: "Embedding",
            plain: (
              <>
                {run?.model_id ?? "A multilingual model"} turns each text into a vector of {run?.embedding_dim ? count(run.embedding_dim) : "many"} numbers,
                scaled to length 1 so only its direction matters. The model places texts with similar meaning in similar
                directions.
              </>
            ),
            formula: "e = model(text),  ||e|| = 1",
          },
          {
            title: "Compression",
            plain: `UMAP compresses each vector to ${param("umap_n_components", "a few")} numbers, keeping each content unit's nearest neighbours (${param("umap_n_neighbors", "a fixed number of them")}) close. Its seed is fixed${run?.params.umap_random_state != null ? ` (${run.params.umap_random_state})` : ""}, so the same set of content units always gives the same map.`,
          },
          {
            title: "Clustering",
            plain: `HDBSCAN groups content units that sit densely together, with at least ${param("hdbscan_min_cluster_size", "a minimum number of content units")} per topic${run?.params.cluster_selection_method === "leaf" ? '; the "leaf" setting keeps the finest groups' : ""}. The rest are unclustered.`,
            formula: "d_mreach(a, b) = max( core(a), core(b), d(a, b) )",
          },
          {
            title: "Profile",
            plain: "Each topic's centre is the average direction of its vectors; similarity to centre ranks its content units, most typical first. Keywords are words frequent in the topic but rare elsewhere.",
            formula: ["similarity(i, t) = e_i · c_t", "W(w, t) = tf(w, t) · log(1 + A ÷ f(w))"],
          },
          {
            title: "Name",
            plain: "Claude writes each name from the text of up to 15 content units nearest the centre. The name plays no part in any test.",
          },
        ]}
        limits={[
          "Clustering sees **only the text**, never views or interactions.",
          "Names are written by Claude and **can be wrong at the edges** of a topic.",
          "A topic is renamed only when it is new, was split or merged, has drifted away from its original content, or was named with an older version of the naming prompt or model.",
          "UMAP keeps neighbours, not global distances, so far-apart topics are not necessarily more different.",
          "Another UMAP seed can draw the topics differently; measuring that is still research (see the stability block below).",
        ]}
        more={
          <>
            Every symbol is explained in{" "}
            <a href="#term-embedding" className="font-medium text-amber-700 underline underline-offset-4">
              Finding topics
            </a>
            .
          </>
        }
      />
    </Section>
  );
}

function TopicProfile({
  selected,
  index,
  count: n,
  inRun,
}: {
  selected: LandingData["topics"][number];
  index: number;
  count: number;
  inRun: number;
}) {
  const facts: { label: React.ReactNode; value: string }[] = [
    { label: "Content units in this topic", value: `${n} (${share(n, inRun)} of ${count(inRun)})` },
  ];
  if (selected.stats.n > 0) {
    facts.push(
      { label: <TermLink term="median">Median engagement rate</TermLink>, value: pct(selected.stats.median) },
      { label: <TermLink term="median">Middle half (IQR)</TermLink>, value: `${pct(selected.stats.iqr_low)} to ${pct(selected.stats.iqr_high)}` },
      { label: <TermLink term="recorded-views">With recorded views (n)</TermLink>, value: `${selected.stats.n}` },
    );
  } else {
    facts.push({ label: <TermLink term="recorded-views">With recorded views (n)</TermLink>, value: "0: no rate to show" });
  }
  // runs_keeping_label = 0 khi topic vừa được đặt/đặt lại tên ở lần chạy mới nhất
  // (src/nlp/topic_identity.py); đếm lần chạy hằng ngày, không phải "clustering" (cách chia khác nhau)
  const naming = [
    selected.labeledAt ? `Name and description written by Claude${selected.labelModel ? ` (${selected.labelModel})` : ""} on ${dayMonthYear(selected.labeledAt)}.` : "Name and description written by Claude.",
    selected.runsKeepingLabel === 0
      ? "Named in the latest clustering run."
      : `Name unchanged for the last ${selected.runsKeepingLabel} daily ${selected.runsKeepingLabel === 1 ? "run" : "runs"}.`,
  ].filter(Boolean) as string[];

  return (
    <SubSection
      title={
        <span className="inline-flex items-center gap-2.5">
          <Swatch index={index} size={14} />
          <span>Selected topic: {selected.name}</span>
        </span>
      }
      note={naming.join(" ")}
    >
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,7fr)_minmax(0,5fr)]">
        <div className="flex flex-col gap-2">
          <h4 className={`m-0 ${H4}`}>What it is about</h4>
          {selected.description ? (
            <p className={`m-0 ${TYPE.measure} ${TYPE.body}`}>{selected.description}</p>
          ) : (
            <p className={`m-0 ${TYPE.body}`}>No description stored for this topic.</p>
          )}
          <div className="mt-4" />
          <div className="flex flex-col gap-2">
            <h4 className={`m-0 ${H4}`}>Keywords</h4>
            <p className={`m-0 ${TYPE.note}`}>
              Chosen by <TermLink term="keywords">c-TF-IDF</TermLink>: frequent in this topic, rare in the others.
            </p>
            {selected.keywords.length > 0 ? (
              <div className="flex flex-wrap gap-1.5">
                {selected.keywords.map((kw) => (
                  <span key={kw} className={`rounded-md bg-bg-surface px-2 py-[3px] ${TYPE.cell} text-text-primary`}>
                    {kw}
                  </span>
                ))}
              </div>
            ) : (
              <span className={TYPE.body}>No keywords stored for this topic.</span>
            )}
            <Bullets
              tone="muted"
              items={[
                `Shown in the original language (mostly Vietnamese, some French). The keywords are not translated; the topic name, “${selected.name}”, says in English what they are about.`,
              ]}
            />
          </div>
        </div>
        <div className="flex flex-col gap-3 rounded-xl border border-warm-border bg-warm-surface px-5 py-4">
          <h4 className={`m-0 ${H4}`}>This topic in numbers</h4>
          <dl className="m-0 flex flex-1 flex-col justify-evenly">
            {facts.map((fact, i) => (
              <div key={i} className="flex items-baseline justify-between gap-4 border-t border-warm-border py-2 first:border-t-0">
                <dt className="min-w-0 text-[15px] font-semibold text-text-primary">{fact.label}</dt>
                <dd className="m-0 whitespace-nowrap text-right text-[15px] font-bold tabular-nums text-text-primary">{fact.value}</dd>
              </div>
            ))}
          </dl>
        </div>
      </div>

      <div className="flex flex-col gap-2">
        <h4 className={`m-0 ${H4}`}>Most typical content units</h4>
        <span className={TYPE.label}>
          The {selected.representatives.length} nearest the topic&apos;s centre · original language ·{" "}
          <TermLink term="similarity">similarity to centre</TermLink> (cosine, at most 1)
        </span>
        {selected.representatives.length === 0 ? (
          <span className={TYPE.body}>No content units stored for this topic.</span>
        ) : (
          <ol className="m-0 flex list-none flex-col p-0">
            {selected.representatives.map((rep) => (
              <li key={rep.id} className="grid grid-cols-[minmax(0,1fr)_56px] items-baseline gap-4 border-b border-bg-surface py-2.5">
                <span className="flex flex-col gap-0.5">
                  <span className={`${TYPE.body} text-text-primary`}>{rep.text}</span>
                  <span className={TYPE.label}>Original language · topic: {selected.name}</span>
                </span>
                <span className={`text-right ${TYPE.mono} font-medium`}>{rep.similarity?.toFixed(3) ?? "—"}</span>
              </li>
            ))}
          </ol>
        )}
      </div>
    </SubSection>
  );
}

const PAGE = 20; // số dòng hiện trước ở chế độ "All" — tránh bảng 1 khung cuộn lồng (ux-reviewer S2)

function UnitTable({
  embedded,
  data,
  selectedId,
  selectedName,
  labelOf,
}: {
  embedded: ContentUnit[];
  data: LandingData;
  selectedId: string;
  selectedName: string;
  labelOf: Map<string, string>;
}) {
  // Bảng content unit: 1 topic hoặc cả lần gom cụm. Cột "Topic (English)" cho người không đọc tiếng
  // Việt biết mỗi dòng thuộc chủ đề gì (Thy 2026-10-29: luồng đọc song ngữ, .claude/rules/dashboard.md)
  const [scope, setScope] = useState<"topic" | "all">("topic");
  const [showAll, setShowAll] = useState(false);
  const order = useMemo(() => new Map(data.topics.map((t, i) => [t.id, i])), [data.topics]);
  const bySimilarity = (a: ContentUnit, b: ContentUnit) =>
    (b.topic?.centroid_similarity ?? -2) - (a.topic?.centroid_similarity ?? -2);
  const members =
    scope === "topic"
      ? embedded.filter((unit) => unit.topic?.topic_id === selectedId).sort(bySimilarity)
      : [...embedded].sort(
          (a, b) =>
            (a.topic ? (order.get(a.topic.topic_id) ?? 998) : 999) -
              (b.topic ? (order.get(b.topic.topic_id) ?? 998) : 999) || bySimilarity(a, b),
        );
  const shown = scope === "all" && !showAll ? members.slice(0, PAGE) : members;
  const topicOf = (unit: ContentUnit) =>
    unit.topic ? (labelOf.get(unit.topic.topic_id) ?? "Unnamed topic") : "Unclustered";
  const rate = (unit: ContentUnit) => (unit.metrics ? pct(unit.metrics.engagement_rate) : "no views recorded");
  const sim = (unit: ContentUnit) => unit.topic?.centroid_similarity?.toFixed(3) ?? "—";

  return (
    <div className="flex flex-col gap-3 border-t border-border-hairline pt-7">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className={`m-0 ${TYPE.h3}`}>
          {scope === "topic"
            ? `Every content unit in “${selectedName}”, most typical first`
            : `All ${count(embedded.length)} content units in the latest clustering run, by topic`}
        </h3>
        <div className="flex gap-1" role="group" aria-label="Which content units to list">
          {(
            [
              ["topic", "This topic"],
              ["all", "All content units"],
            ] as const
          ).map(([value, label]) => (
            <button
              key={value}
              type="button"
              aria-pressed={scope === value}
              onClick={() => {
                setScope(value);
                setShowAll(false);
              }}
              className={`min-h-[44px] cursor-pointer rounded-full border px-4 text-[13px] font-medium ${
                scope === value
                  ? "border-amber-600 bg-amber-soft text-amber-700"
                  : "border-border-hairline bg-bg-card text-text-secondary hover:bg-bg-surface"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>
      <Bullets
        tone="muted"
        items={[
          "First lines are shown as written (original language); the English topic name on the same row says which topic each one belongs to. Unclustered rows have no English label yet.",
          "Parts: how many posts make up the content unit (the opening post plus its follow-ups).",
          "Engagement rate: the opening post's rate in the latest data.",
        ]}
      />
      {members.length === 0 ? (
        <span className={TYPE.body}>No content units to list.</span>
      ) : (
        <>
          {/* ≥ md: bảng; < md: mỗi dòng 1 thẻ để cột "Topic (English)" không nằm ngoài màn hình (ux-reviewer B9) */}
          <table className="hidden w-full table-fixed border-collapse text-left md:table">
            <colgroup>
              <col />
              <col className="w-[22%]" />
              <col className="w-[104px]" />
              <col className="w-[56px]" />
              <col className="w-[96px]" />
              <col className="w-[96px]" />
            </colgroup>
            <thead>
              <tr className="border-b border-rule">
                <th scope="col" className={`px-3 py-2 ${TYPE.th}`}>First line · original language</th>
                <th scope="col" className={`px-3 py-2 ${TYPE.th}`}>Topic (English)</th>
                <th scope="col" className={`px-3 py-2 ${TYPE.th}`}>Published</th>
                <th scope="col" className={`px-3 py-2 text-right ${TYPE.th}`}>Parts</th>
                <th scope="col" className={`px-3 py-2 text-right ${TYPE.th}`}>
                  <TermLink term="rates">Engagement rate</TermLink>
                </th>
                <th scope="col" className={`px-3 py-2 text-right ${TYPE.th}`}>
                  <TermLink term="similarity">Similarity</TermLink>
                </th>
              </tr>
            </thead>
            <tbody>
              {shown.map((unit) => (
                <tr key={unit.id} className="border-b border-bg-surface align-baseline hover:bg-bg-sunken">
                  <td className={`px-3 py-2 ${TYPE.cell} text-text-primary`}>{firstLine(unit.full_text)}</td>
                  <td
                    className={`px-3 py-2 ${TYPE.cell} ${
                      scope === "all" && unit.topic?.topic_id === selectedId ? "font-medium text-amber-700" : "text-text-secondary"
                    }`}
                  >
                    {topicOf(unit)}
                  </td>
                  <td className={`whitespace-nowrap px-3 py-2 ${TYPE.mono} text-text-secondary`}>
                    {unit.timestamp ? dayMonthYear(unit.timestamp) : "—"}
                  </td>
                  <td className={`px-3 py-2 text-right ${TYPE.mono} text-text-secondary`}>{unit.continuation_count + 1}</td>
                  <td className={`px-3 py-2 text-right ${TYPE.mono} text-text-primary`}>{rate(unit)}</td>
                  <td className={`px-3 py-2 text-right ${TYPE.mono} text-text-primary`}>{sim(unit)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <ul className="m-0 flex list-none flex-col p-0 md:hidden">
            {shown.map((unit) => (
              <li key={unit.id} className="flex flex-col gap-1 border-b border-bg-surface py-3">
                <span className={`${TYPE.cell} text-text-primary`}>{firstLine(unit.full_text)}</span>
                <span className={TYPE.label}>Original language · topic: {topicOf(unit)}</span>
                {/* cặp nhãn + giá trị không tách khi xuống dòng (ux-reviewer P2) */}
                <span className="flex flex-wrap gap-x-3 gap-y-0.5">
                  {[
                    ["published", unit.timestamp ? dayMonthYear(unit.timestamp) : "—"],
                    ["parts", `${unit.continuation_count + 1}`],
                    ["engagement rate", rate(unit)],
                    ["similarity", sim(unit)],
                  ].map(([label, value]) => (
                    <span key={label} className="whitespace-nowrap">
                      <span className={TYPE.label}>{label} </span>
                      <span className={`${TYPE.mono} text-text-secondary`}>{value}</span>
                    </span>
                  ))}
                </span>
              </li>
            ))}
          </ul>
          {scope === "all" && members.length > PAGE ? (
            <button
              type="button"
              onClick={() => setShowAll((value) => !value)}
              aria-expanded={showAll}
              className="inline-flex min-h-[44px] w-fit cursor-pointer items-center gap-2 rounded-full border border-border-hairline bg-bg-surface px-4 text-[13px] font-semibold text-text-primary hover:border-amber-600 hover:text-amber-700"
            >
              <ArrowDown size={16} aria-hidden="true" className={showAll ? "rotate-180" : ""} />
              {showAll ? `Show the first ${PAGE} only` : `Show all ${count(members.length)} content units`}
            </button>
          ) : null}
        </>
      )}
    </div>
  );
}

function StabilityPanel({ data }: { data: LandingData }) {
  const run = data.summary.latest_cluster_run;
  const history = data.topicTests?.history ?? null;
  const fmt = (value: number | null | undefined) => (value === null || value === undefined ? "—" : value.toFixed(2));
  // Câu trả lời không tự đặt ngưỡng "ổn định" (UI-0004-ari-two-ways, ADR-0024): luật bền vẫn để mở
  // → mọi phép so là gợi ý. Không suy "cùng cách chia" từ ARI = 1: ARI chỉ tính trên unit có mặt ở
  // cả 2 lần (ADR-0024 bằng chứng 1, .claude/rules/pipeline-db.md)
  const rows: { name: React.ReactNode; value: string; meaning: string; missing?: boolean }[] = run
    ? [
        {
          name: <TermLink term="ari">ARI, content units with a topic in both runs</TermLink>,
          value: fmt(run.ari_clustered_only),
          meaning:
            run.ari_clustered_only === null
              ? "Not computed: no previous run, or fewer than 2 content units to compare."
              : "Do the content units that had a topic both times stay grouped the same way? 1 = identical grouping, about 0 = chance.",
          missing: run.ari_clustered_only === null,
        },
        {
          name: <TermLink term="ari">ARI, unclustered counted as one group</TermLink>,
          value: fmt(run.ari_vs_previous),
          meaning:
            run.ari_vs_previous === null
              ? "Not computed: no previous run, or fewer than 2 content units to compare."
              : "Same question, counting moves into and out of the unclustered group as changes too.",
          missing: run.ari_vs_previous === null,
        },
        {
          name: <TermLink term="dbcv">DBCV (density-based clustering validation)</TermLink>,
          value: run.dbcv === null ? "—" : run.dbcv.toFixed(3),
          meaning:
            run.dbcv === null
              ? "Not computed: fewer than 2 topics."
              : "From −1 to 1: higher means denser topics, better separated. There is no standard pass mark, and this page shows only the latest run.",
          missing: run.dbcv === null,
        },
        {
          name: <TermLink term="hdbscan">Unclustered share</TermLink>,
          value: `${count(run.n_noise)} of ${count(run.n_units)} (${share(run.n_noise, run.n_units)})`,
          meaning: `Content units that fit no dense group. A high share can mean one-off subjects or strict topic boundaries (each topic needs at least ${run.params.hdbscan_min_cluster_size ?? "a minimum number of"} content units); this page does not tell the two apart.`,
        },
      ]
    : [];

  return (
    <Section
      id="stability"
      n="05"
      short={sectionShort("stability")}
      title="How stable are these topics?"
      purpose="Shows how much the topics changed since the previous run and how well separated they are, which decides how far any result above can be trusted."
    >
      <AnswerRow
        answer="No stability rule is set yet, so a topic that stands out on this page is at most a lead, not a finding."
        points={[
          "New content units can **re-draw the topic boundaries** every day.",
          "Test results have appeared and disappeared as the boundaries moved.",
          history && history.clusterings_compared > 0
            ? `Since ${history.since ? parisDate(history.since) : "the first test"}, the tests have run on ${history.clusterings_compared} different ${history.clusterings_compared === 1 ? "clustering" : "clusterings"} of the content units (daily runs that gave exactly the same grouping count once).`
            : null,
          "The rule will come from **re-clustering the same content units with several random seeds** (research, not measured yet).",
        ]}
        keyNumbers={
          run
            ? [
                // 2 cách tính ARI luôn đi cùng nhau (UI-0004-ari-two-ways) — không chọn số đẹp
                {
                  value: `${fmt(run.ari_clustered_only)} and ${fmt(run.ari_vs_previous)}`,
                  label: "ARI vs the previous run",
                  note: `${fmt(run.ari_clustered_only)} on content units with a topic in both runs; ${fmt(run.ari_vs_previous)} when moves into or out of unclustered count as changes. 1 = identical grouping.`,
                  term: "ari",
                },
                { value: run.dbcv === null ? "—" : run.dbcv.toFixed(3), label: "DBCV of this run", note: "From −1 to 1, higher = better separated topics.", term: "dbcv" },
                ...(history && history.clusterings_compared > 0
                  ? [
                      {
                        value: `${history.clusterings_compared}`,
                        label: "clusterings tested",
                        note: `Distinct groupings the tests have run on${history.since ? ` since ${parisDate(history.since)}` : ""}.`,
                        term: "stood-out",
                      },
                    ]
                  : []),
              ]
            : undefined
        }
      />

      {run ? (
        <div className="flex flex-col gap-3 border-t border-border-hairline pt-7">
          <h3 className={`m-0 ${TYPE.h3}`}>Measures of the latest clustering run</h3>
          {/* 1 lưới chung cho mọi hàng (subgrid) — cột giá trị và cột nghĩa thẳng hàng từ trên xuống */}
          <dl className="m-0 flex flex-col md:grid md:grid-cols-[max-content_max-content_minmax(0,1fr)] md:gap-x-8">
            {rows.map((row, i) => (
              <div
                key={i}
                className="grid grid-cols-[minmax(0,1fr)_auto] gap-x-6 gap-y-1 border-b border-bg-surface py-3 md:col-span-3 md:grid-cols-subgrid"
              >
                <dt className={`text-[15px] font-semibold ${row.missing ? "text-text-muted" : "text-text-primary"}`}>{row.name}</dt>
                <dd className={`m-0 text-right md:text-left ${TYPE.mono} font-medium ${row.missing ? "text-text-muted" : "text-text-primary"}`}>
                  {row.value}
                </dd>
                <dd className="col-span-2 m-0 text-[13px] leading-[1.55] text-text-secondary md:col-span-1">{row.meaning}</dd>
              </div>
            ))}
            <div className="grid grid-cols-[minmax(0,1fr)_auto] gap-x-6 gap-y-1 py-3 md:col-span-3 md:grid-cols-subgrid">
              <dt className="text-[15px] font-semibold text-text-primary">
                <TermLink term="seed">Stability across random seeds</TermLink>
              </dt>
              <dd className="m-0 text-right md:text-left">
                <span className={`rounded-full border border-border-hairline bg-bg-surface px-2.5 py-[3px] ${TYPE.label}`}>not measured yet</span>
              </dd>
              <dd className="col-span-2 m-0 text-[13px] leading-[1.55] text-text-secondary md:col-span-1">
                Re-clustering the same content units with several seeds measures how much the topics depend on chance.
                That measurement will set the rule a result must pass to become a finding.
              </dd>
            </div>
          </dl>
        </div>
      ) : null}

      <MethodSection
        steps={[
          {
            title: "Agreement with the previous run",
            plain: "Take the content units present in both runs and count the pairs both runs put together, corrected for chance (adjusted Rand index). Computed twice: on content units with a topic in both runs, and with unclustered counted as one group.",
            formula: "ARI = (Σ_ij C(n_ij, 2) − E) ÷ (1/2 [Σ_i C(a_i, 2) + Σ_j C(b_j, 2)] − E)",
          },
          {
            title: "Separation of this run",
            plain: `DBCV compares, for each topic, how loose it is inside with how far it sits from the nearest other topic, weighted by topic size (n counts every content unit in the run). Computed on the ${run?.params.umap_n_components ?? "compressed"} UMAP numbers HDBSCAN clustered.`,
            formula: "DBCV = Σ_t (|t| ÷ n) · (sep(t) − spread(t)) ÷ max(sep(t), spread(t))",
          },
          {
            title: "Unclustered share",
            plain: "Unclustered content units divided by all content units in the run.",
          },
        ]}
        limits={[
          "Every daily run uses the same UMAP seed, so a run on unchanged content units repeats the previous one exactly: an ARI of 1.00 then shows **reproducibility, not stability**.",
          "ARI only covers content units present in both runs, so a run that adds new content units can still score 1.00 on the old ones.",
          "Comparing with the previous run mixes two changes: new content units, and the re-drawing they cause. Stability across seeds would measure the chance part alone (same content units, other seeds); it is not measured yet.",
          "DBCV is computed on the compressed UMAP numbers, not on the full embeddings.",
        ]}
        more={
          <>
            Every symbol is explained in{" "}
            <a href="#term-dbcv" className="font-medium text-amber-700 underline underline-offset-4">
              Quality and stability of the topics
            </a>
            .
          </>
        }
      />
    </Section>
  );
}
