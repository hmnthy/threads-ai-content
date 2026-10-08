"use client";

import { useMemo, useState } from "react";
import {
  MethodBlock,
  MethodButton,
  PANEL,
  SECTION,
  SectionHead,
  StatusPill,
} from "@/components/LandingParts";
import {
  axisPct,
  count,
  parisTime,
  pct,
  rowSwarm,
  ticks,
  type LandingData,
  type TopicView,
} from "@/lib/landing";

// "Product proof" (handoff §3.4). Panel 1: median/IQR/n theo topic là số thật từ API (mô tả);
// Cliff's δ + p Holm theo topic chờ Việc 1 chốt nhóm so sánh → pill `next` + câu "Preview", ô
// hiện "—", không điền số giả (UI-L20260903-stack-real-status). Panel 2 đọc cluster_runs thật.

const TABLE = "grid grid-cols-[minmax(150px,240px)_44px_minmax(0,1fr)_64px_52px_60px] gap-4";

export function LandingProof({ data }: { data: LandingData | null }) {
  return (
    <section
      id="proof"
      data-screen-label="04 Product proof"
      className={`${SECTION} flex flex-col gap-8 border-t border-rule py-[104px]`}
    >
      <SectionHead eyebrow="03 · Proof" title="What the data already answers, and what it doesn't yet.">
        Each panel asks one question, answers it in a line, shows the evidence, and keeps the method
        one click away.
      </SectionHead>
      {data && data.topics.length > 0 ? (
        <>
          <TopicEngagementPanel data={data} />
          <TopicStructurePanel data={data} />
        </>
      ) : (
        <div className={`${PANEL} gap-2`}>
          <span className="text-[13px] font-semibold text-amber-600">
            Which topics get more engagement than the channel?
          </span>
          <span className="text-base text-text-secondary">
            {!data
              ? "The data service is not reachable right now. Reload in a moment."
              : data.summary.latest_cluster_run
                ? "The latest clustering run found no topics: every post was left as noise."
                : "No clustering run is stored yet, so there are no topics to show."}
          </span>
        </div>
      )}
    </section>
  );
}

function TopicEngagementPanel({ data }: { data: LandingData }) {
  const [hover, setHover] = useState<string | null>(null);
  const [methodOpen, setMethodOpen] = useState(false);
  const axisMax = data.axisMax;
  const channelMedian = data.channel.stats.median;
  const hasChannelMedian = data.channel.stats.n > 0;
  // Topic mang cờ insufficient_data không nhận câu kết luận → không chọn làm topic dẫn đầu
  const comparable = data.topics.filter((t) => !t.stats.insufficient_data && t.stats.n > 0);
  const lead = comparable.reduce<TopicView | null>(
    (best, t) => (best === null || t.stats.median > best.stats.median ? t : best),
    null,
  );
  const rows = useMemo(
    () => data.topics.map((t) => ({ topic: t, dots: rowSwarm(t.rates, axisMax, 20, 5) })),
    [data.topics, axisMax],
  );
  const noiseDots = useMemo(
    () => rowSwarm(data.noise.rates, axisMax, 22, 5),
    [data.noise.rates, axisMax],
  );
  const hovered = data.topics.find((t) => t.id === hover) ?? null;
  const excluded = data.topics.reduce((sum, t) => sum + t.excluded, 0) + data.noise.excluded;

  const anyFlagged = data.topics.some((t) => t.stats.insufficient_data);
  const answer = lead
    ? `${lead.name} has the highest median engagement rate${anyFlagged ? " among topics with enough posts to compare" : ""}: ${pct(lead.stats.median)}${hasChannelMedian ? `, against ${pct(channelMedian)} for the channel` : ""}. The gap is not tested yet.`
    : "Every topic is too small to compare yet.";
  const readNote = hovered
    ? hovered.stats.n === 0
      ? `${hovered.name}: no measured posts (n = 0).`
      : `${hovered.name}: median ${pct(hovered.stats.median)}, IQR ${hovered.stats.iqr_low.toFixed(2)}–${pct(hovered.stats.iqr_high)}, n = ${hovered.stats.n}.${
        hovered.stats.insufficient_data ? " Too few posts to compare, read as indicative." : ""
      }`
    : hasChannelMedian
      ? `Dashed line: channel median ${pct(channelMedian)}. Hover or focus a row to read it.`
      : "Hover or focus a row to read it.";

  return (
    <div className={`${PANEL} gap-[22px]`}>
      <div className="flex max-w-[840px] flex-col gap-1.5">
        <div className="flex flex-wrap items-center gap-2.5">
          <span className="text-[13px] font-semibold text-amber-600">
            Which topics get more engagement than the channel?
          </span>
          <StatusPill status="next" />
        </div>
        <span className="text-2xl font-bold leading-[1.3] tracking-[-0.02em]">{answer}</span>
        <span className="text-[13px] leading-[1.55] text-text-secondary [text-wrap:pretty]">
          Preview. Per-topic tests are not in the dashboard yet: medians and spread are live, Cliff&apos;s
          δ and Holm-corrected p-values are next.
        </span>
      </div>

      <div className="overflow-x-auto">
        <div className="flex min-w-[760px] flex-col tabular-nums">
          <div
            className={`${TABLE} items-end border-b border-rule pb-2 text-[11px] font-semibold text-text-muted`}
          >
            <span>Topic · named by Claude</span>
            <span className="text-right">n</span>
            <div className="relative h-4" aria-hidden="true">
              {ticks(axisMax).map((tick) => (
                <span
                  key={tick}
                  className="absolute -translate-x-1/2 font-mono text-[11px] font-normal"
                  style={{ left: axisPct(tick, axisMax) }}
                >
                  {tick}%
                </span>
              ))}
            </div>
            <span className="text-right">median</span>
            <span className="text-right">δ · next</span>
            <span className="text-right">p, Holm · next</span>
          </div>
          <div className="relative">
            <div className={`${TABLE} pointer-events-none absolute inset-0`} aria-hidden="true">
              <span />
              <span />
              <div className="relative">
                {hasChannelMedian ? (
                  <div
                    className="absolute inset-y-0 w-0 border-l-[1.5px] border-dashed border-text-primary"
                    style={{ left: axisPct(channelMedian, axisMax) }}
                  />
                ) : null}
              </div>
            </div>
            {rows.map(({ topic, dots }) => {
              const isLead = topic.id === lead?.id;
              const isHover = hover === topic.id;
              const faded = topic.stats.insufficient_data && !isHover;
              // n = 0: backend trả 0.0 cho tập rỗng — không vẽ median/IQR giả (ADR-0011)
              const showStats = topic.stats.n > 0;
              return (
                <div
                  key={topic.id}
                  tabIndex={0}
                  role="group"
                  aria-label={`${topic.name}, n ${topic.stats.n}, median ${showStats ? pct(topic.stats.median) : "not available"}`}
                  onMouseEnter={() => setHover(topic.id)}
                  onMouseLeave={() => setHover(null)}
                  onFocus={() => setHover(topic.id)}
                  onBlur={() => setHover(null)}
                  className={`${TABLE} relative h-10 items-center border-b border-bg-surface transition-opacity duration-150 ease-out ${
                    isHover ? "bg-bg-sunken" : ""
                  } ${faded ? "opacity-50" : ""}`}
                >
                  <span
                    title={topic.name}
                    className={`truncate text-[13.5px] ${isLead ? "font-semibold text-amber-600" : "text-text-primary"}`}
                  >
                    {topic.name}
                  </span>
                  <span className="text-right font-mono text-[12.5px] text-text-secondary">
                    {topic.stats.n}
                  </span>
                  <div className="relative h-10" aria-hidden="true">
                    {showStats ? (
                      <div
                        className={`absolute top-[13px] h-3.5 rounded ${isLead ? "bg-amber-soft" : "bg-bg-surface"}`}
                        style={{
                          left: axisPct(topic.stats.iqr_low, axisMax),
                          width: axisPct(topic.stats.iqr_high - topic.stats.iqr_low, axisMax),
                        }}
                      />
                    ) : null}
                    {dots.map((dot, i) => (
                      <div
                        key={i}
                        className={`absolute h-1.5 w-1.5 -translate-x-1/2 -translate-y-1/2 rounded-full ${
                          isLead ? "bg-amber-600" : isHover ? "bg-text-primary" : "bg-chart-dot"
                        }`}
                        style={dot}
                      />
                    ))}
                    {showStats ? (
                      <div
                        className={`absolute top-[9px] h-[22px] w-[3px] -translate-x-1/2 rounded-sm ${isLead ? "bg-amber-600" : "bg-text-primary"}`}
                        style={{ left: axisPct(topic.stats.median, axisMax) }}
                      />
                    ) : null}
                  </div>
                  <span
                    className={`text-right font-mono text-[12.5px] font-medium ${isLead ? "text-amber-600" : "text-text-primary"}`}
                  >
                    {showStats ? pct(topic.stats.median) : "—"}
                  </span>
                  <span className="text-right font-mono text-[12.5px] text-text-muted">
                    <span aria-hidden="true">—</span>
                    <span className="sr-only">not computed yet</span>
                  </span>
                  <span className="text-right font-mono text-[12.5px] text-text-muted">
                    <span aria-hidden="true">—</span>
                    <span className="sr-only">not computed yet</span>
                  </span>
                </div>
              );
            })}
            {data.noise.stats && data.noise.stats.n > 0 ? (
              <div
                className={`${TABLE} h-11 items-center border-b border-dashed border-rule bg-bg-sunken`}
              >
                <span className="text-[13.5px] text-text-muted">Unclustered (HDBSCAN noise)</span>
                <span className="text-right font-mono text-[12.5px] text-text-muted">
                  {data.noise.stats.n}
                </span>
                <div className="relative h-11" aria-hidden="true">
                  <div
                    className="absolute top-[15px] h-3.5 rounded bg-bg-surface"
                    style={{
                      left: axisPct(data.noise.stats.iqr_low, axisMax),
                      width: axisPct(data.noise.stats.iqr_high - data.noise.stats.iqr_low, axisMax),
                    }}
                  />
                  {noiseDots.map((dot, i) => (
                    <div
                      key={i}
                      className="absolute box-border h-1.5 w-1.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-[1.5px] border-chart-dot"
                      style={dot}
                    />
                  ))}
                  <div
                    className="absolute top-[11px] h-[22px] w-[3px] -translate-x-1/2 rounded-sm bg-text-muted"
                    style={{ left: axisPct(data.noise.stats.median, axisMax) }}
                  />
                </div>
                <span className="text-right font-mono text-[12.5px] font-medium text-text-muted">
                  {pct(data.noise.stats.median)}
                </span>
                <span className="col-span-2 text-right text-[11.5px] text-text-muted">not tested</span>
              </div>
            ) : null}
          </div>
        </div>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-4 border-t border-bg-surface pt-3">
        <div className="flex max-w-[820px] flex-col gap-1">
          <span className="text-[13px] leading-[1.55] text-text-secondary" aria-live="polite">
            {readNote}
          </span>
          {excluded > 0 ? (
            <span className="text-[12.5px] text-text-secondary">
              {excluded} excluded: no views recorded
            </span>
          ) : null}
        </div>
        <MethodButton open={methodOpen} onToggle={() => setMethodOpen((open) => !open)} />
      </div>
      {methodOpen ? (
        <div className="-mt-2">
          <MethodBlock
            formula={`median and IQR of engagement rate per topic, posts with recorded views only · dashed line = channel median ${hasChannelMedian ? pct(channelMedian) : "—"} · next: Mann-Whitney U per topic, Cliff's δ, Holm across topics`}
            limits={`Topics with fewer than ${data.summary.min_posts_to_compare} posts with recorded views are faded and read as indicative. A higher median is a description, not a tested difference, until the per-topic tests ship.`}
          />
        </div>
      ) : null}
    </div>
  );
}

function TopicStructurePanel({ data }: { data: LandingData }) {
  const run = data.summary.latest_cluster_run;
  const heroTopicId = data.hero?.topicId ?? null;
  const [sel, setSel] = useState<string>(
    data.topics.some((t) => t.id === heroTopicId) ? heroTopicId! : data.topics[0].id,
  );
  const [methodOpen, setMethodOpen] = useState(false);
  const selected = data.topics.find((t) => t.id === sel) ?? data.topics[0];
  const maxN = Math.max(...data.topics.map((t) => t.postCount), 1);
  const dbcvText =
    run?.dbcv == null ? "not computed (fewer than 2 clusters)" : run.dbcv.toFixed(3);
  const runAt = run ? parisTime(run.run_at) : null;
  const totalPosts = data.summary.content_units;

  const ari = [
    { label: "vs previous run, posts clustered in both runs", value: run?.ari_clustered_only ?? null },
    { label: "vs previous run, noise counted as one group", value: run?.ari_vs_previous ?? null },
  ];
  // Câu trả lời đọc thẳng 2 số, không ngưỡng "ổn định" tự đặt (UI-0004-ari-two-ways)
  const ariHead = ari.every((a) => a.value === null)
    ? "Not computed for this run."
    : ari.every((a) => a.value === 1)
      ? `This run matches the previous one exactly (ARI 1.00 on both measures).${
          run?.params.umap_random_state != null
            ? " With the seed fixed, that shows it is reproducible, not that it is stable."
            : ""
        } Stability across seeds is still research (RQ-01).`
      : `Agreement ${ari[0].value?.toFixed(2) ?? "—"} on posts clustered in both runs, ${ari[1].value?.toFixed(2) ?? "—"} with noise counted.`;

  const params = run?.params ?? {};
  const param = (key: string) => (params[key] ?? "?").toString();

  return (
    <div className={`${PANEL} gap-6`}>
      <div className="flex flex-wrap items-start justify-between gap-6">
        <div className="flex max-w-[840px] flex-col gap-1.5">
          <span className="text-[13px] font-semibold text-amber-600">
            Do the topics describe real structure in the text?
          </span>
          <span className="text-2xl font-bold leading-[1.3] tracking-[-0.02em]">
            {run
              ? run.n_noise === 0
                ? `Yes. All ${count(run.n_units)} posts with text fall into ${run.n_clusters} topics.`
                : `Partly. ${count(run.n_units - run.n_noise)} of the ${count(run.n_units)} posts with text fall into ${run.n_clusters} topics; the other ${count(run.n_noise)} fit none and stay unclustered.`
              : "No clustering run is stored yet."}
          </span>
          <div className="flex flex-col gap-0.5 text-[13px] leading-[1.55] text-text-secondary">
            {data.sameExcludedPosts ? (
              <span>
                {data.summary.units_without_text} of {count(totalPosts)} posts have no text to embed;
                the same {data.summary.units_without_text} have no recorded views.
              </span>
            ) : (
              <>
                <span>
                  {data.summary.units_without_text} of {count(totalPosts)} posts have no text to embed
                </span>
                <span>
                  {data.channel.excluded} of {count(data.channel.total)} excluded: no views recorded
                </span>
              </>
            )}
          </div>
        </div>
        {run ? (
          <div className="flex flex-col gap-1 font-mono text-[12.5px] text-text-secondary">
            <span>validity_index (DBCV) {dbcvText}</span>
            <span>
              noise {(run.noise_ratio * 100).toFixed(1)}% of {count(run.n_units)} embedded
            </span>
            <span className="text-text-muted">clustered {runAt}</span>
          </div>
        ) : null}
      </div>

      <div className="grid grid-cols-[repeat(auto-fit,minmax(min(100%,440px),1fr))] items-start gap-7">
        <div className="flex flex-col gap-2.5">
          <div className="relative aspect-[4/3] rounded-xl bg-bg-sunken" aria-hidden="true">
            {data.mapPoints.map((p, i) => {
              const isSel = p.topicId === selected.id;
              const noise = p.topicId === null;
              return (
                <div
                  key={i}
                  className={`absolute box-border -translate-x-1/2 -translate-y-1/2 rounded-full ${
                    isSel
                      ? "z-[2] bg-amber-600"
                      : noise
                        ? "z-[1] border-[1.5px] border-chart-dot bg-transparent"
                        : "z-[1] bg-chart-dot"
                  }`}
                  style={{
                    left: `${3 + p.x * 0.94}%`,
                    top: `${3 + (100 - p.y) * 0.94}%`,
                    width: isSel ? 10 : 7,
                    height: isSel ? 10 : 7,
                  }}
                />
              );
            })}
          </div>
          <div className="flex flex-wrap gap-[18px] text-xs text-text-secondary">
            <span className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-amber-600" />
              selected topic
            </span>
            <span className="flex items-center gap-1.5">
              <span className="h-[7px] w-[7px] rounded-full bg-chart-dot" />
              other topics
            </span>
            <span className="flex items-center gap-1.5">
              <span className="box-border h-[7px] w-[7px] rounded-full border-[1.5px] border-chart-dot" />
              noise{run ? ` · ${run.n_noise}` : ""}
            </span>
            <span className="font-mono text-text-muted">
              UMAP dims 1–2 of {param("umap_n_components")}
            </span>
          </div>
        </div>

        <div className="flex flex-col gap-[18px]">
          <div className="flex flex-col">
            <span className="px-2 pb-1.5 text-[11px] font-semibold text-text-muted">
              Topics · named by Claude · select one
            </span>
            {data.topics.map((t) => {
              const on = t.id === selected.id;
              return (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => setSel(t.id)}
                  aria-pressed={on}
                  className={`grid h-[34px] cursor-pointer grid-cols-[minmax(0,1fr)_minmax(48px,120px)_28px] items-center gap-3 border-0 border-b border-bg-surface px-2 text-left ${
                    on ? "bg-amber-soft" : "bg-transparent"
                  }`}
                >
                  <span
                    title={t.name}
                    className={`truncate text-[13px] ${on ? "font-semibold text-amber-700" : "text-text-primary"}`}
                  >
                    {t.name}
                  </span>
                  <span className="relative h-2 overflow-hidden rounded-full bg-bg-surface">
                    <span
                      className={`absolute inset-y-0 left-0 rounded-full ${on ? "bg-amber-600" : "bg-chart-dot"}`}
                      style={{ width: `${(t.postCount / maxN) * 100}%` }}
                    />
                  </span>
                  <span className="text-right font-mono text-xs text-text-secondary">{t.postCount}</span>
                </button>
              );
            })}
          </div>
          <div className="flex flex-col gap-3 border-t-2 border-text-primary pt-3.5">
            <div className="flex flex-wrap items-baseline justify-between gap-3">
              <span className="flex flex-col gap-0.5">
                <span className="text-base font-bold">{selected.name}</span>
                <span className="text-[11.5px] text-text-muted">named by Claude</span>
              </span>
              <span className="font-mono text-xs text-text-secondary">
                {selected.id} · n {selected.postCount}
                {selected.stats.n > 0
                  ? ` · median ${pct(selected.stats.median)}${
                      selected.stats.n !== selected.postCount ? ` (${selected.stats.n} measured)` : ""
                    }`
                  : " · no measured posts"}
              </span>
            </div>
            <div className="flex flex-col gap-1.5">
              <span className="text-[11px] font-semibold text-text-muted">Keywords (c-TF-IDF)</span>
              {selected.keywords.length > 0 ? (
                <div className="flex flex-wrap gap-1.5">
                  {selected.keywords.map((kw) => (
                    <span
                      key={kw}
                      className="rounded-full bg-amber-soft px-2.5 py-[3px] font-mono text-xs text-amber-700"
                    >
                      {kw}
                    </span>
                  ))}
                </div>
              ) : (
                <span className="text-[13px] text-text-secondary">No keywords stored for this topic.</span>
              )}
            </div>
            <div className="flex flex-col gap-1.5">
              <span className="text-[11px] font-semibold text-text-muted">
                Posts nearest the centre, for reading · similarity to centre
              </span>
              {selected.representatives.length === 0 ? (
                <span className="text-[13px] text-text-secondary">No posts stored for this topic.</span>
              ) : null}
              {selected.representatives.map((rep) => (
                <div
                  key={rep.id}
                  className="grid grid-cols-[minmax(0,1fr)_48px] items-baseline gap-3 border-b border-bg-surface py-1.5"
                >
                  <span className="text-[13px] leading-[1.5] text-text-primary">{rep.text}</span>
                  <span className="text-right font-mono text-xs font-medium text-text-primary">
                    {rep.similarity?.toFixed(3) ?? "—"}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-[repeat(auto-fit,minmax(min(100%,440px),1fr))] gap-7 border-t border-rule pt-6">
        <div className="flex flex-col gap-3">
          <div className="flex flex-col gap-1">
            <span className="text-[13px] font-semibold text-text-secondary">Are the clusters stable?</span>
            <span className="text-[17px] font-bold leading-[1.35]">{ariHead}</span>
          </div>
          {ari.map((a) => {
            const missing = a.value === null;
            return (
              <div
                key={a.label}
                className="grid min-h-[34px] grid-cols-[minmax(0,1fr)_minmax(56px,140px)_44px] items-center gap-3 border-b border-bg-surface"
              >
                <span className="flex flex-col gap-0.5 py-1.5">
                  <span className={`text-[13px] leading-[1.4] ${missing ? "text-text-muted" : "text-text-primary"}`}>
                    {a.label}
                  </span>
                  {missing ? (
                    <span className="font-mono text-xs text-text-muted">
                      not computed (fewer than 2 posts to compare)
                    </span>
                  ) : null}
                </span>
                <span
                  className={`relative h-2 overflow-hidden rounded-full ${
                    missing ? "border border-dashed border-chart-dot-faint" : "bg-bg-surface"
                  }`}
                >
                  <span
                    className="absolute inset-y-0 left-0 rounded-full bg-text-muted"
                    style={{ width: missing ? "0%" : `${Math.max(0, a.value!) * 100}%` }}
                  />
                </span>
                <span
                  className={`text-right font-mono text-[12.5px] font-medium tabular-nums ${missing ? "text-text-muted" : "text-text-primary"}`}
                >
                  {missing ? "—" : a.value!.toFixed(2)}
                </span>
              </div>
            );
          })}
          <span className="font-mono text-xs leading-[1.6] text-text-muted">
            Adjusted Rand Index · 1.00 = identical partition · seed variance across 10 seeds:
            research, RQ-01
          </span>
        </div>

        <div className="flex flex-col gap-3">
          <div className="flex items-start justify-between gap-3">
            <div className="flex flex-col gap-1">
              <span className="text-[13px] font-semibold text-text-secondary">
                Does mixing languages change engagement?
              </span>
              <span className="text-[17px] font-bold leading-[1.35]">Not tested yet.</span>
            </div>
            <StatusPill status="research" label="research · RQ-04" />
          </div>
          <span className="text-[13px] leading-[1.6] text-text-secondary">
            Every post gets a Code-Mixing Index (roughly, how much of it is in languages other than
            its main one) across Vietnamese, French and English. Whether it relates to engagement is
            still open: no number appears here until it is tested with an effect size and Holm
            correction.
          </span>
        </div>
      </div>

      <div className="flex justify-end border-t border-bg-surface pt-1">
        <MethodButton open={methodOpen} onToggle={() => setMethodOpen((open) => !open)} />
      </div>
      {methodOpen && run ? (
        <div className="-mt-4">
          <MethodBlock
            formula={`${run.model_id}${run.embedding_dim ? ` ${run.embedding_dim}D` : ""} on full_text → UMAP ${param("umap_n_components")}D (n_neighbors ${param("umap_n_neighbors")}, seed ${param("umap_random_state")}) → HDBSCAN ${param("cluster_selection_method")}, min_cluster_size ${param("hdbscan_min_cluster_size")} · validity_index (DBCV) ${dbcvText} · centroid_similarity = cosine to cluster centre`}
            limits="Limits: the map is 2 of 3 UMAP dimensions, so distance on screen is approximate. Names are written by Claude from up to 15 posts nearest the centre, text only, and can be wrong at the edges of a cluster. A topic is renamed only when it is new, split, merged, drifts, or was named under an older setup."
          />
        </div>
      ) : null}
    </div>
  );
}
