"use client";

import { useMemo, useState } from "react";
import type { TopicComparisonRow } from "@/lib/api";
import { AnswerRow, Bullets, MethodSection, Section, SubSection, TermLink, TYPE } from "@/components/AppBlock";
import { VerdictLabel, VerdictMark, tooFewLabel, verdictParts } from "@/components/Verdict";
import { sectionShort } from "@/lib/topicSections";
import {
  MethodBlock,
  MethodButton,
  PANEL,
  SECTION,
  SectionHead,
  StatusPill,
} from "@/components/LandingParts";
import {
  andList,
  axisPct,
  count,
  familyBreakdown as holmBreakdown,
  formatP,
  historySentence,
  noneStandOutReason,
  parisDate,
  parisTime,
  pct,
  POST_NOUN,
  rowSwarm,
  signed,
  testTimes,
  testVerdict,
  ticks,
  winShare,
  type LandingData,
  type Noun,
  type TopicView,
} from "@/lib/landing";

// "Product proof" (handoff §3.4). Panel 1: median/IQR/n theo topic là số thật từ API (mô tả, dữ
// liệu mới nhất); Cliff's δ + p Holm đọc `/topics/comparisons` — tính trong job NLP sau mỗi lần
// gom cụm, mang mốc giờ riêng (ADR-0023). Họ Holm = mọi phép so có p xác định trên trang Topics
// (mọi topic × engagement / share_rate / conversation): landing dùng đúng p Holm đó dù panel chỉ
// hiện engagement, và đọc kích thước họ từ API (`holm_family_size`), không tự nhân. Không tải
// được / chưa chạy lần nào → ô "—" + câu nói đúng lý do (`topicTestsStatus`); kết quả thuộc lần
// gom cụm cũ → API ẩn δ/p, ô "—" kèm lý do (Thy chốt D3). Panel 2 đọc cluster_runs thật. Panel 1
// dùng lại ở /topics (`variant="app"`, danh từ "content unit").
// Chữ Thy duyệt 2026-10-09: phép so là TỈ LỆ engagement so với PHẦN CÒN LẠI của kênh
const PANEL_QUESTION = "Which topics get a higher engagement rate than the rest of the channel?";
const TABLE =
  "grid grid-cols-[minmax(150px,240px)_44px_minmax(0,1fr)_64px_52px_60px_60px] gap-4";
// Cùng panel, 2 hình khối: landing (tầng B, card 20px) và trang /topics (tầng A, `AppEngagementPanel`)
export type PanelVariant = "landing" | "app";

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
            {PANEL_QUESTION}
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

export function TopicEngagementPanel({
  data,
  variant = "landing",
  noun = POST_NOUN,
}: {
  data: LandingData;
  variant?: PanelVariant;
  noun?: Noun;
}) {
  const [hover, setHover] = useState<string | null>(null);
  const [methodOpen, setMethodOpen] = useState(false);
  const axisMax = data.axisMax;
  const channelMedian = data.channel.stats.median;
  const hasChannelMedian = data.channel.stats.n > 0;
  const tests = data.topicTests;
  const testsShown = tests !== null && !tests.stale;
  const verdictOf = (t: TopicView) =>
    testsShown ? testVerdict(tests.engagement[t.id], tests.method) : "not tested";
  const higher = data.topics.filter((t) => verdictOf(t) === "higher");
  const lower = data.topics.filter((t) => verdictOf(t) === "lower");
  // Có kiểm định: tô màu đúng các topic CAO hơn phần còn lại sau hiệu chỉnh. Chưa có: topic median
  // cao nhất trong các topic đủ bài (mô tả) — topic mang cờ insufficient_data không được chọn.
  const comparable = data.topics.filter((t) => !t.stats.insufficient_data && t.stats.n > 0);
  const lead = testsShown
    ? null
    : comparable.reduce<TopicView | null>(
        (best, t) => (best === null || t.stats.median > best.stats.median ? t : best),
        null,
      );
  const highlighted = new Set(testsShown ? higher.map((t) => t.id) : lead ? [lead.id] : []);
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
  const names = (list: TopicView[]) => andList(list.map((t) => t.name));
  const family = tests?.method.holm_family_size ?? 0;
  // "9 topics ×" chỉ khi họ đúng bằng số topic × 3 chỉ số (helper chung `familyBreakdown`)
  const familyBreakdown =
    tests && holmBreakdown(tests, data.topics.length)
      ? `: ${data.topics.length} topics × engagement, share rate and conversation`
      : "";
  // topicTests null có 2 lý do (API lỗi / chưa chạy lần nào) — nói đúng lý do, không còn "next":
  // kiểm định theo topic đã live ở cả landing lẫn /topics (ADR-0023 Việc 3 + Việc 4)
  const unavailableNote =
    data.topicTestsStatus === "not-run"
      ? "The per-topic tests have not run on any clustering yet; they run in the daily NLP job after each clustering."
      : "The per-topic tests could not be loaded right now, so only the medians and spread are shown. Reload in a moment.";
  // ADR-0024: kết quả đạt p Holm vẫn chỉ là gợi ý (chưa có luật bền qua các cách chia cụm) — "for now
  // … stands out", tên topic đặt sau dấu hai chấm; không câu khẳng định kiểu "posts on X tend to …"
  // (chữ Thy duyệt 2026-10-18 sau copy-reviewer)
  const standOut = (list: TopicView[], side: "above" | "below") =>
    `${list.length === 1 ? "one topic stands" : `${list.length} topics stand`} out ${side} the rest of the channel: ${names(list)}.`;
  const answer = testsShown
    ? higher.length + lower.length === 0
      ? "For now, no topic's engagement rate can be told apart from the rest of the channel after correcting for multiple comparisons."
      : higher.length > 0 && lower.length > 0
        ? `For now, ${higher.length + lower.length} topics stand out from the rest of the channel: ${names(higher)} above it; ${names(lower)} below it.`
        : `For now, ${standOut(higher.length > 0 ? higher : lower, higher.length > 0 ? "above" : "below")}`
    : lead
      ? `${lead.name} has the highest median engagement rate${anyFlagged ? ` among topics with enough ${noun.many} to compare` : ""}: ${pct(lead.stats.median)}${hasChannelMedian ? `, against ${pct(channelMedian)} for the channel` : ""}. ${
          tests?.stale ? "The gap is not tested on the current topics yet." : "The gap is not tested yet."
        }`
      : "Every topic is too small to compare yet.";
  const hoveredRow = hovered && testsShown ? tests.engagement[hovered.id] : undefined;
  const hoveredVerdict = hovered ? verdictOf(hovered) : "not tested";
  const testFigures =
    hoveredRow && hoveredRow.effect_size !== null && hoveredRow.p_value_holm !== null
      ? `Cliff's δ ${signed(hoveredRow.effect_size)}${
          hoveredRow.effect_size_ci_low !== null && hoveredRow.effect_size_ci_high !== null
            ? `, 95% CI ${signed(hoveredRow.effect_size_ci_low)} to ${signed(hoveredRow.effect_size_ci_high)}, unadjusted`
            : ""
        }; Holm-corrected p ${formatP(hoveredRow.p_value_holm)}`
      : null;
  const testNote =
    hoveredRow && hoveredRow.effect_size !== null && testFigures
      ? hoveredVerdict === "higher" || hoveredVerdict === "lower"
        ? ` A random ${noun.one} from this topic beats a random ${noun.one} from the rest of the channel ${winShare(hoveredRow.effect_size)}% of the time (${testFigures}). A lead in the current topics, not a finding yet.`
        : hoveredVerdict === "too few posts"
          ? ` Too few ${noun.many} to draw a conclusion; read as indicative only (${testFigures}).`
          : ` Not distinguishable from the rest of the channel after correction (${testFigures}).`
      : hovered?.stats.insufficient_data
        ? ` Too few ${noun.many} to draw a conclusion; read as indicative only.`
        : "";
  // ADR-0024: lịch sử "k of m" — vẫn hiện khi `stale` (đếm từ các lần kiểm định đã lưu)
  const historyText =
    hovered && tests
      ? historySentence(tests.engagement[hovered.id], tests.method, tests.stale, noun)
      : "";
  const historyNote = historyText ? ` ${historyText}` : "";
  const deltaHint = testsShown
    ? ` δ runs from −1 to +1: above 0, the topic's ${noun.many} tend to have a higher rate than the rest of the channel.`
    : "";
  // Thy 2026-10-29: không topic nào đạt thì giải thích vì sao bằng số của chính lần kiểm định,
  // thành khối riêng ngay dưới câu trả lời — không ẩn, không chìm trong dòng phụ
  const whyNone =
    testsShown && higher.length + lower.length === 0 ? noneStandOutReason(tests, data.topics, noun, variant === "app" ? "shown in grey" : "faded", variant === "app") : [];
  const readNote = hovered
    ? hovered.stats.n === 0
      ? `${hovered.name}: no measured ${noun.many} (n = 0).`
      : `${hovered.name}: median ${pct(hovered.stats.median)}, IQR ${hovered.stats.iqr_low.toFixed(2)}–${pct(hovered.stats.iqr_high)}, n = ${hovered.stats.n}.${testNote}${historyNote}`
    : hasChannelMedian
      ? `Dashed line: channel median ${pct(channelMedian)}.${deltaHint} Hover or focus a row to read it.`
      : `${deltaHint.trim()} Hover or focus a row to read it.`.trim();
  const subline = !tests
    ? unavailableNote
    : tests.stale
      ? `Effect sizes and p-values are hidden: topics were re-clustered after the last tests ran${
          tests.computedAt ? ` on ${testTimes(tests.computedAt, null)}` : ""
        }, so those results describe an older grouping of ${noun.many}. They return once the tests are rerun on the current topics.`
      : `${
          higher.length + lower.length > 0
            ? `This is a lead, not a finding: it holds for the current topics, which are re-clustered as new ${noun.many} arrive. `
            : ""
        }Each topic is compared with every other ${noun.one}, unclustered ones included.${
          // khối "Why no topic stands out yet" đã giải thích 33 phép so — không lặp lại ở đây
          higher.length + lower.length === 0 ? "" : ` p-values are corrected for all ${family} tests${familyBreakdown}.`
        }${
          tests.computedAt
            ? ` Tests ran ${testTimes(tests.computedAt, tests.snapshotAsOf)}; the medians and dots (one per ${noun.one}) use the latest data.`
            : ""
        }`;

  const isApp = variant === "app";
  if (isApp) {
    return (
      <AppEngagementPanel
        data={data}
        noun={noun}
        rows={rows}
        noiseDots={noiseDots}
        verdictOf={verdictOf}
        highlighted={highlighted}
        answer={answer}
        whyNone={whyNone}
        familyBreakdown={familyBreakdown}
      />
    );
  }

  return (
    <div className={`${PANEL} gap-[22px]`}>
      <div className="flex max-w-[840px] flex-col gap-1.5">
        <div className="flex flex-wrap items-center gap-2.5">
          <span className="text-[13px] font-semibold text-amber-600">{PANEL_QUESTION}</span>
          <StatusPill status="live" />
        </div>
        <span className="text-2xl font-bold leading-[1.3] tracking-[-0.02em]">{answer}</span>
        {whyNone.length > 0 ? (
          <div className="mt-1.5 flex flex-col gap-1 rounded-xl bg-bg-sunken px-4 py-3">
            <span className="text-[13px] font-semibold text-text-primary">Why no topic stands out yet</span>
            <ul className="m-0 flex list-disc flex-col gap-0.5 pl-5 text-[13px] leading-[1.55] text-text-secondary">
              {whyNone.map((point) => (
                <li key={point}>{point}</li>
              ))}
            </ul>
          </div>
        ) : null}
        <span className="text-[13px] leading-[1.55] text-text-secondary [text-wrap:pretty]">
          {subline}
        </span>
      </div>

      <div className="overflow-x-auto">
        <div className="flex min-w-[840px] flex-col tabular-nums">
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
            <span className="text-right" title="Cliff's delta, from −1 to +1">
              δ
            </span>
            <span className="text-right">Holm p</span>
            <span
              className="text-right"
              title={`Clusterings in which this topic stood out, out of those with enough of its ${noun.many} to test. See Method and limits.`}
            >
              stood out in
            </span>
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
              const isLead = highlighted.has(topic.id);
              const row = testsShown ? tests.engagement[topic.id] : undefined;
              const delta = row?.effect_size ?? null;
              const pHolm = row?.p_value_holm ?? null;
              const missingReason = !tests
                ? data.topicTestsStatus === "not-run"
                  ? "tests have not run yet"
                  : "tests could not be loaded"
                : tests.stale
                  ? "hidden: tests belong to an earlier clustering run"
                  : "not tested";
              // lịch sử đọc cả khi `stale` (δ/p bị ẩn nhưng các lần kiểm định cũ vẫn đúng)
              const tally = tests?.engagement[topic.id]?.history ?? null;
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
                  <span
                    className={`text-right font-mono text-[12.5px] ${delta === null ? "text-text-muted" : isLead ? "text-amber-600" : "text-text-primary"}`}
                  >
                    {delta === null ? (
                      <>
                        <span aria-hidden="true">—</span>
                        <span className="sr-only">{missingReason}</span>
                      </>
                    ) : (
                      signed(delta)
                    )}
                  </span>
                  <span
                    className={`text-right font-mono text-[12.5px] ${pHolm === null ? "text-text-muted" : isLead ? "text-amber-600" : "text-text-primary"}`}
                  >
                    {pHolm === null ? (
                      <>
                        <span aria-hidden="true">—</span>
                        <span className="sr-only">{missingReason}</span>
                      </>
                    ) : (
                      formatP(pHolm)
                    )}
                  </span>
                  <span
                    className={`text-right font-mono text-[12.5px] ${tally && tally.clusterings > 0 ? (isLead && testsShown ? "text-amber-600" : "text-text-primary") : "text-text-muted"}`}
                  >
                    {tally && tally.clusterings > 0 ? (
                      <>
                        {/* mũi tên ghi hướng — k = 0 không có hướng (backend `direction` null) */}
                        <span aria-hidden="true">
                          {tally.stood_out} of {tally.clusterings}
                          {tally.direction ? (tally.direction === "higher" ? " ↑" : " ↓") : ""}
                        </span>
                        <span className="sr-only">
                          {tally.direction
                            ? `stood out ${tally.direction === "higher" ? "above" : "below"} the rest of the channel in ${tally.stood_out} of ${tally.clusterings} clusterings`
                            : `stood out in 0 of ${tally.clusterings} clusterings`}
                        </span>
                      </>
                    ) : (
                      <>
                        <span aria-hidden="true">—</span>
                        <span className="sr-only">
                          {tally ? `no clustering had enough of its ${noun.many} to test yet` : missingReason}
                        </span>
                      </>
                    )}
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
                <span className="col-span-3 text-right text-[11.5px] text-text-muted">not tested</span>
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
            formula={`engagement rate per topic: median and IQR, ${noun.many} with recorded views only · dashed line = channel median ${hasChannelMedian ? pct(channelMedian) : "—"}, a reference, not the comparison group · ${
              tests
                ? `each topic vs the rest of the channel, unclustered ${noun.many} included: two-sided Brunner-Munzel permutation test (${count(tests.method.n_permutations)} permutations, fixed seed) · effect size Cliff's δ = P(topic > rest) − P(topic < rest); (1 + δ) / 2 is the share of pairs a topic ${noun.one} wins, ties counted as half · 95% CI from inverting the same permutation test, unadjusted · p Holm-corrected across ${family} tests${familyBreakdown ? ` (${data.topics.length} topics × engagement, share rate, conversation)` : ""}`
                : "each topic vs the rest of the channel: Brunner-Munzel permutation test, Cliff's δ with a 95% CI (unadjusted), p Holm-corrected across every topic × engagement, share rate, conversation · results not available right now"
            }`}
            limits={
              tests
                ? `A topic is named in the answer above only when its Holm-corrected p is below ${tests.method.conclusion_alpha} and it has at least ${tests.method.min_posts_to_compare} ${noun.many} with recorded views; smaller topics are faded and read as indicative only. Medians only describe; the test alone decides which topics are named. Every comparison here is exploratory: it depends on where the topic boundaries fall. Topics are re-clustered daily with a fixed random seed, so the same ${noun.many} give the same topics, but a few new ${noun.many} or a different seed can redraw them. Re-running the tests on earlier clusterings of the same ${noun.many} has made results appear and disappear. A topic will be reported as a finding only once it passes a stability rule (re-clustering with several random seeds); that rule is not set yet. The "stood out in" column is a record, not that rule. A clustering is one way of grouping the ${noun.many} into topics; daily runs that give the same topics count once, using the latest test. The column counts the ${tests.history ? `${tests.history.clusterings_compared} ${tests.history.clusterings_compared === 1 ? "clustering" : "clusterings"}` : "clusterings"}${tests.history?.since ? ` tested since ${parisDate(tests.history.since)}` : ""} and leaves out those that gave a topic too few ${noun.many} to test; each topic's count starts at its first counted clustering. ↑ means above the rest of the channel, ↓ below; a topic that stood out both ways shows the direction of its current δ, or, while tests are hidden, the direction it stood out in more often. The clusterings share most of their ${noun.many}, so they are not independent tests. Topics are matched across clusterings by their ${noun.many} and content; when topics merge or split, the result may count as a new topic, and its count starts again. The CI is unadjusted, so it can exclude 0 while the corrected p stays above ${tests.method.conclusion_alpha}. Holm-corrected p-values are capped at 1. With so few ${noun.many} per topic only very large differences can be detected, so "not distinguishable" (even at p = 1.000) does not mean "no difference".`
                : `Topics with fewer than ${data.summary.min_posts_to_compare} ${noun.many} with recorded views are faded and read as indicative. A higher median is a description, not a tested difference: ${unavailableNote.charAt(0).toLowerCase()}${unavailableNote.slice(1)}`
            }
          />
        </div>
      ) : null}
    </div>
  );
}

// Bản /topics của panel engagement (tầng A, luật "trình bày như nhà nghiên cứu NLP", Thy 2026-10-29):
// cùng số + cùng câu trả lời với landing, nhưng: đầu khối 2 cột (ý chính + số chính), chú giải biểu đồ
// luôn hiện, tên topic không cắt, header link tới định nghĩa, dòng ít bài dùng chữ muted thay độ mờ,
// dòng đọc khi hover có vùng riêng xếp dọc, < md mỗi topic 1 thẻ (không cuộn ngang), Method mở sẵn.
// Phép so 2 phía (Thy chốt 2026-10-29 (c), phụ đề /topics): trang app hỏi "differ", không "higher";
// câu hỏi landing giữ chữ Thy duyệt 2026-10-09 (sửa landing chỉ khi Thy duyệt từng câu)
const APP_QUESTION = "Does any topic's engagement rate differ from the rest of the channel?";
const APP_GRID = "grid grid-cols-[minmax(160px,260px)_44px_minmax(0,1fr)_64px_64px_60px_76px] gap-4";
type Dot = { left: string; top: string };

function AppEngagementPanel({
  data,
  noun,
  rows,
  noiseDots,
  verdictOf,
  highlighted,
  answer,
  whyNone,
  familyBreakdown,
}: {
  data: LandingData;
  noun: Noun;
  rows: { topic: TopicView; dots: Dot[] }[];
  noiseDots: Dot[];
  verdictOf: (t: TopicView) => ReturnType<typeof testVerdict>;
  highlighted: Set<string>;
  answer: string;
  whyNone: string[];
  familyBreakdown: string;
}) {
  const [hover, setHover] = useState<string | null>(null);
  const axisMax = data.axisMax;
  const channelMedian = data.channel.stats.median;
  const hasChannelMedian = data.channel.stats.n > 0;
  const tests = data.topicTests;
  const testsShown = tests !== null && !tests.stale;
  const family = tests?.method.holm_family_size ?? 0;
  const alpha = tests?.method.conclusion_alpha;
  const minPosts = tests?.method.min_posts_to_compare ?? data.summary.min_posts_to_compare;
  const anyStanding = data.topics.some((t) => {
    const v = verdictOf(t);
    return v === "higher" || v === "lower";
  });
  const hovered = data.topics.find((t) => t.id === hover) ?? null;
  // "closest call" = p thô nhỏ nhất trong các topic đủ bài — cùng định nghĩa với noneStandOutReason
  const closest =
    testsShown && whyNone.length > 0
      ? data.topics
          .map((t) => ({ t, row: tests.engagement[t.id] }))
          .filter(
            ({ row }) =>
              row !== undefined &&
              !row.insufficient_data &&
              row.p_value !== null &&
              row.p_value_holm !== null &&
              row.effect_size !== null,
          )
          .reduce<{ t: TopicView; row: TopicComparisonRow } | null>(
            (best, cur) => (best === null || cur.row.p_value! < best.row.p_value! ? cur : best),
            null,
          )
      : null;
  const rowOf = (t: TopicView) => (testsShown ? tests.engagement[t.id] : undefined);
  const missingReason = !tests
    ? data.topicTestsStatus === "not-run"
      ? "tests have not run yet"
      : "tests could not be loaded"
    : tests.stale
      ? "hidden: tests belong to an earlier clustering run"
      : "not tested";
  const resultText = (t: TopicView) => {
    const v = verdictOf(t);
    return v === "not tested" ? missingReason : verdictParts(v, minPosts, noun).text;
  };
  // Câu trả lời của /topics nói cùng nhãn với bảng ("significantly different … after correction"),
  // không "can be told apart" của landing (copy-reviewer 2026-10-29; landing giữ chữ đã duyệt)
  // "large enough to conclude on": đúng cả khi 1 topic nhỏ (n < ngưỡng) lọt dưới α sau hiệu chỉnh
  // — topic đó không bao giờ được kết luận (copy-reviewer 2026-10-29)
  const shownAnswer =
    testsShown && !anyStanding
      ? `For now, no topic large enough to conclude on has an engagement rate significantly different from the rest of the channel (corrected for all ${family} tests).`
      : answer;

  const points: (string | null)[] = !tests
    ? [
        data.topicTestsStatus === "not-run"
          ? "The per-topic tests have not run on any clustering yet; they run in the daily NLP job after each clustering."
          : "The per-topic tests could not be loaded right now, so only the medians and spread are shown. Reload in a moment.",
      ]
    : tests.stale
      ? [
          `Effect sizes and p-values are hidden: topics were re-clustered after the last tests ran${
            tests.computedAt ? ` on ${testTimes(tests.computedAt, null)}` : ""
          }.`,
          `Those results describe an older grouping of ${noun.many}; they return once the tests are rerun on the current topics.`,
        ]
      : [
          anyStanding
            ? `This is a lead, not a finding: it holds for the current topics, which are re-clustered as new ${noun.many} arrive.`
            : null,
          `Each topic is compared with **every other ${noun.one}**, unclustered ones included, not with the channel median.`,
          anyStanding ? `p-values are corrected for all ${family} tests${familyBreakdown}.` : null,
          tests.computedAt ? `Tests ran ${testTimes(tests.computedAt, tests.snapshotAsOf)}.` : null,
          `The medians and dots (one per ${noun.one}) use the latest data.`,
        ];

  // Dòng đọc khi hover/focus: mỗi ý 1 dòng (ux-reviewer S4), không thay chú giải (S5)
  // Chưa chọn dòng nào → hiện sẵn closest call (dòng đáng đọc nhất), không để hộp trống (Thy 2026-10-29)
  const reading = hovered ?? closest?.t ?? null;
  const hoveredRow = reading ? rowOf(reading) : undefined;
  const readLines: string[] = !reading
    ? ["Hover or focus a row to read its numbers here."]
    : reading.stats.n === 0
      ? [`${reading.name}: no ${noun.many} with recorded views (n = 0).`]
      : [
          reading.name,
          `Median ${pct(reading.stats.median)} · middle half (IQR) ${pct(reading.stats.iqr_low)} to ${pct(reading.stats.iqr_high)} · n = ${reading.stats.n}`,
          hoveredRow && hoveredRow.effect_size !== null
            ? `Cliff's δ ${signed(hoveredRow.effect_size)}${
                hoveredRow.effect_size_ci_low !== null && hoveredRow.effect_size_ci_high !== null
                  ? ` (95% CI ${signed(hoveredRow.effect_size_ci_low)} to ${signed(hoveredRow.effect_size_ci_high)}, unadjusted)`
                  : ""
              }: a random ${noun.one} from this topic beats one from the rest about ${winShare(hoveredRow.effect_size)}% of the time`
            : "",
          hoveredRow && hoveredRow.p_value_holm !== null
            ? `Corrected p ${formatP(hoveredRow.p_value_holm)}${hoveredRow.p_value !== null ? ` (before correction ${formatP(hoveredRow.p_value)})` : ""} · ${resultText(reading)}`
            : reading.stats.insufficient_data
              ? tooFewLabel(noun, minPosts)
              : "",
          tests ? historySentence(tests.engagement[reading.id], tests.method, tests.stale, noun) : "",
        ].filter(Boolean);

  const strip = (t: TopicView | null, dots: Dot[], isLead: boolean, isHover: boolean, noise = false) => {
    const stats = t ? t.stats : data.noise.stats;
    const showStats = stats !== null && stats.n > 0;
    return (
      <div className="relative h-10" aria-hidden="true">
        {hasChannelMedian ? (
          <div
            className="absolute inset-y-0 w-0 border-l-[1.5px] border-dashed border-text-primary"
            style={{ left: axisPct(channelMedian, axisMax) }}
          />
        ) : null}
        {showStats ? (
          <div
            className={`absolute top-[13px] h-3.5 rounded ${isLead ? "bg-amber-soft" : "bg-bg-surface"}`}
            style={{ left: axisPct(stats.iqr_low, axisMax), width: axisPct(stats.iqr_high - stats.iqr_low, axisMax) }}
          />
        ) : null}
        {dots.map((dot, i) => (
          <div
            key={i}
            className={`absolute box-border h-1.5 w-1.5 -translate-x-1/2 -translate-y-1/2 rounded-full ${
              noise
                ? "border-[1.5px] border-chart-dot"
                : isLead
                  ? "bg-amber-600"
                  : isHover
                    ? "bg-text-primary"
                    : "bg-chart-dot"
            }`}
            style={dot}
          />
        ))}
        {showStats ? (
          <div
            className={`absolute top-[9px] h-[22px] w-[3px] -translate-x-1/2 rounded-sm ${
              noise ? "bg-text-muted" : isLead ? "bg-amber-600" : "bg-text-primary"
            }`}
            style={{ left: axisPct(stats.median, axisMax) }}
          />
        ) : null}
      </div>
    );
  };
  const axis = (
    <div className="relative h-4" aria-hidden="true">
      {ticks(axisMax).map((tick) => (
        <span
          key={tick}
          className={`absolute -translate-x-1/2 ${TYPE.mono} text-text-muted`}
          style={{ left: axisPct(tick, axisMax) }}
        >
          {tick}%
        </span>
      ))}
    </div>
  );
  const cellTone = (t: TopicView, isLead: boolean) =>
    isLead ? "text-amber-700" : t.stats.insufficient_data ? "text-text-muted" : "text-text-primary";

  return (
    <Section
      id="engagement"
      n="03"
      short={sectionShort("engagement")}
      title={APP_QUESTION}
      purpose="Tests whether any topic's content units get a different engagement rate from the rest of the channel, with the evidence for every topic."
    >
      <AnswerRow
        answer={shownAnswer}
        below={
          whyNone.length > 0 ? (
            <div className="flex flex-col gap-2">
              <h4 className={`m-0 ${TYPE.h4}`}>Why no topic stands out yet</h4>
              <Bullets items={whyNone} />
            </div>
          ) : null
        }
        points={points}
        keyNumbers={[
          {
            value: hasChannelMedian ? pct(channelMedian) : "—",
            label: "channel median engagement rate",
            note: "The dashed line on the chart: a reference, not the comparison group.",
            term: "median",
          },
          {
            value: count(data.channel.stats.n),
            label: `${noun.many} with recorded views`,
            // cùng tập với `channel.stats.n` (cả unit không chữ / đăng sau lần gom cụm) — UI-0011-excluded
            note:
              data.channel.excluded > 0
                ? `${data.channel.excluded} of ${count(data.channel.total)} excluded: no views recorded${
                    data.sameExcludedPosts ? " (the same ones have no text, so they are in no topic)" : ""
                  }.`
                : `Every ${noun.one} has recorded views.`,
            term: "recorded-views",
          },
          ...(closest
            ? [
                {
                  value: signed(closest.row.effect_size!),
                  label: "Cliff's δ of the closest call (smallest p)",
                  note: `${closest.t.name}: its ${noun.many} beat the rest in about ${winShare(closest.row.effect_size!)}% of pairs.`,
                  term: "cliffs-delta",
                },
                {
                  value: `${formatP(closest.row.p_value!)} → ${formatP(closest.row.p_value_holm!)}`,
                  label: "its p, before → after correction",
                  note: `Holm multiplies the smallest of the ${family} p-values by ${family}, the next smallest by ${family - 1}, and so on.`,
                  term: "holm",
                },
              ]
            : []),
        ]}
      />

      <SubSection
        title={`Engagement rate of every ${noun.one}, by topic`}
        note={
          <>
            Each row is one topic: its dots, its middle half and median, then the test against the rest of the
            channel. Hover or focus a row to read it in full · <TermLink term="rates">how the rate is computed</TermLink>
          </>
        }
      >
        {/* chú giải luôn hiện, sát biểu đồ (design-system §9) — lớp kỹ thuật (nền xám), 2 cột: dấu trên biểu
            đồ | nhãn dòng (cột Holm p, cột Stood out in) */}
        <div className="grid grid-cols-1 gap-x-10 gap-y-3 rounded-xl border border-border-hairline bg-bg-sunken px-5 py-4 lg:grid-cols-2">
          <div className="flex flex-col gap-1.5">
            <span className="text-[12px] font-semibold text-text-muted">Marks on the chart</span>
            <ul className="m-0 flex list-none flex-wrap items-center gap-x-5 gap-y-1.5 p-0 text-[13px] text-text-secondary">
              <li className="flex items-center gap-1.5">
                <span className="h-1.5 w-1.5 rounded-full bg-chart-dot" /> one {noun.one}
              </li>
              <li className="flex items-center gap-1.5">
                <span className="h-3 w-5 rounded bg-bg-surface ring-1 ring-border-hairline" /> middle half (IQR)
              </li>
              <li className="flex items-center gap-1.5">
                <span className="h-3.5 w-[3px] rounded-sm bg-text-primary" /> median
              </li>
              <li className="flex items-center gap-1.5">
                <span className="h-3.5 w-0 border-l-[1.5px] border-dashed border-text-primary" /> channel median
              </li>
              <li className="flex items-center gap-1.5">
                <span className="box-border h-1.5 w-1.5 rounded-full border-[1.5px] border-chart-dot" /> unclustered
              </li>
              {highlighted.size > 0 ? (
                <li className="flex items-center gap-1.5">
                  <span className="h-1.5 w-1.5 rounded-full bg-amber-600" />{" "}
                  {testsShown ? "topic that stood out above" : "highest median (not tested)"}
                </li>
              ) : null}
            </ul>
          </div>
          <div className="flex flex-col gap-1.5">
            <span className="text-[12px] font-semibold text-text-muted">Holm p and Stood out in columns</span>
            <ul className="m-0 flex list-none flex-col gap-1 p-0 text-[13px] text-text-secondary">
              <li className="flex items-center gap-1.5">
                <VerdictMark verdict="not distinguishable" /> not significant after correction
              </li>
              <li className="flex items-center gap-1.5">
                <VerdictMark verdict="too few posts" /> {tooFewLabel(noun, minPosts).replace(/^T/, "t")} (row in grey)
              </li>
              <li className="flex items-center gap-1.5">
                <span className="whitespace-nowrap text-text-primary">▲ above / ▼ below</span>: stood out in k of m
                re-clusterings, a record, not today&apos;s result
              </li>
            </ul>
          </div>
        </div>

        {/* ≥ md: bảng-biểu đồ */}
        <div className="hidden flex-col tabular-nums md:flex">
          <div className={`${APP_GRID} items-end border-b border-rule pb-2 ${TYPE.th}`}>
            <span>Topic</span>
            <span className="text-right">
              <TermLink term="median">n</TermLink>
            </span>
            {axis}
            <span className="text-right">
              <TermLink term="median">Median</TermLink>
            </span>
            <span className="text-right">
              <TermLink term="cliffs-delta">Cliff&apos;s δ</TermLink>
            </span>
            <span className="text-right">
              <TermLink term="holm">Holm p</TermLink>
            </span>
            <span className="whitespace-nowrap text-right">
              <TermLink term="stood-out">Stood out in</TermLink>
            </span>
          </div>
          {rows.map(({ topic, dots }) => {
            const isLead = highlighted.has(topic.id);
            const row = rowOf(topic);
            const delta = row?.effect_size ?? null;
            const pHolm = row?.p_value_holm ?? null;
            const tally = tests?.engagement[topic.id]?.history ?? null;
            const isHover = hover === topic.id;
            const tone = cellTone(topic, isLead);
            return (
              <div
                key={topic.id}
                tabIndex={0}
                role="group"
                aria-label={`${topic.name}, n ${topic.stats.n}, median ${topic.stats.n > 0 ? pct(topic.stats.median) : "not available"}, ${resultText(topic)}`}
                onMouseEnter={() => setHover(topic.id)}
                onMouseLeave={() => setHover(null)}
                onFocus={() => setHover(topic.id)}
                onBlur={() => setHover(null)}
                className={`${APP_GRID} min-h-10 items-center border-b border-bg-surface ${isHover ? "bg-bg-sunken" : ""}`}
              >
                <span className={`${TYPE.cell} py-1.5 ${isLead ? "font-semibold" : ""} ${tone}`}>{topic.name}</span>
                <span className={`text-right ${TYPE.mono} ${tone}`}>{topic.stats.n}</span>
                {strip(topic, dots, isLead, isHover)}
                <span className={`text-right ${TYPE.mono} font-medium ${tone}`}>
                  {topic.stats.n > 0 ? pct(topic.stats.median) : "—"}
                </span>
                <span className={`text-right ${TYPE.mono} ${delta === null ? "text-text-muted" : tone}`}>
                  {delta === null ? (
                    <>
                      <span aria-hidden="true">—</span>
                      <span className="sr-only">{missingReason}</span>
                    </>
                  ) : (
                    signed(delta)
                  )}
                </span>
                <span className={`flex items-baseline justify-end gap-1 ${TYPE.mono} ${pHolm === null ? "text-text-muted" : tone}`}>
                  {pHolm !== null ? <VerdictMark verdict={verdictOf(topic)} /> : null}
                  {pHolm === null ? (
                    <>
                      <span aria-hidden="true">—</span>
                      <span className="sr-only">{missingReason}</span>
                    </>
                  ) : (
                    formatP(pHolm)
                  )}
                </span>
                <span className={`text-right ${TYPE.mono} ${tally && tally.clusterings > 0 ? "text-text-primary" : "text-text-muted"}`}>
                  {tally && tally.clusterings > 0
                    ? `${tally.stood_out} of ${tally.clusterings}${tally.direction ? (tally.direction === "higher" ? " ▲" : " ▼") : ""}`
                    : "—"}
                </span>
              </div>
            );
          })}
          {data.noise.stats && data.noise.stats.n > 0 ? (
            <div className={`${APP_GRID} min-h-11 items-center border-b border-dashed border-rule bg-bg-sunken`}>
              <span className={`${TYPE.cell} text-text-muted`}>Unclustered</span>
              <span className={`text-right ${TYPE.mono} text-text-muted`}>{data.noise.stats.n}</span>
              {strip(null, noiseDots, false, false, true)}
              <span className={`text-right ${TYPE.mono} font-medium text-text-muted`}>{pct(data.noise.stats.median)}</span>
              <span className={`col-span-3 text-right ${TYPE.label}`}>described, not tested</span>
            </div>
          ) : null}
        </div>

        {/* < md: mỗi topic 1 thẻ, strip trải đủ bề rộng (ux-reviewer B9, phương án A) */}
        <ul className="m-0 flex list-none flex-col gap-3 p-0 md:hidden">
          {rows.map(({ topic, dots }) => {
            const isLead = highlighted.has(topic.id);
            const row = rowOf(topic);
            const tone = cellTone(topic, isLead);
            return (
              <li key={topic.id} className="flex flex-col gap-1 border-b border-bg-surface pb-3">
                <span className={`${TYPE.cell} font-semibold ${tone}`}>{topic.name}</span>
                <span className={`${TYPE.mono} text-text-secondary`}>
                  median {topic.stats.n > 0 ? pct(topic.stats.median) : "—"} · n {topic.stats.n}
                </span>
                {row && row.effect_size !== null ? (
                  <span className={`${TYPE.mono} text-text-secondary`}>
                    Cliff&apos;s δ {signed(row.effect_size)}
                    {row.effect_size_ci_low !== null && row.effect_size_ci_high !== null
                      ? ` (95% CI ${signed(row.effect_size_ci_low)} to ${signed(row.effect_size_ci_high)}, unadjusted)`
                      : ""}
                  </span>
                ) : null}
                <span className={`${TYPE.mono} text-text-secondary`}>
                  Holm p {row && row.p_value_holm !== null ? formatP(row.p_value_holm) : "—"}
                  {(() => {
                    // cùng chuỗi với cột desktop (▲/▼; "—" khi chưa từng đủ bài)
                    const tally = tests?.engagement[topic.id]?.history ?? null;
                    return tally && tally.clusterings > 0
                      ? ` · stood out in ${tally.stood_out} of ${tally.clusterings}${tally.direction ? (tally.direction === "higher" ? " ▲" : " ▼") : ""}`
                      : " · stood out in —";
                  })()}
                </span>
                {verdictOf(topic) === "not tested" ? (
                  <span className={`${TYPE.cell} text-text-muted`}>{missingReason}</span>
                ) : (
                  <VerdictLabel verdict={verdictOf(topic)} minPosts={minPosts} noun={noun} />
                )}
                {axis}
                {strip(topic, dots, isLead, false)}
              </li>
            );
          })}
          {data.noise.stats && data.noise.stats.n > 0 ? (
            <li className="flex flex-col gap-1 rounded-lg bg-bg-sunken px-2 pb-3 pt-2">
              <span className={`${TYPE.cell} font-semibold text-text-muted`}>Unclustered</span>
              <span className={`${TYPE.mono} text-text-secondary`}>
                median {pct(data.noise.stats.median)} · n {data.noise.stats.n} · described, not tested
              </span>
              {axis}
              {strip(null, noiseDots, false, false, true)}
            </li>
          ) : null}
        </ul>

        <div className="hidden flex-col gap-0.5 rounded-xl border border-border-hairline px-4 py-3 md:flex" aria-live="polite">
          <span className={TYPE.label}>
            {hovered ? "Selected row" : reading ? "Closest call · hover or focus another row to read it" : "Selected row"}
          </span>
          {readLines.map((line, i) => (
            <span key={i} className={`text-[13px] leading-[1.55] ${i === 0 && reading ? "font-semibold text-text-primary" : "text-text-secondary"}`}>
              {line}
            </span>
          ))}
        </div>
      </SubSection>

      <MethodSection
        steps={[
          {
            title: "Describe",
            plain: `Median and middle half (IQR) of the engagement rate in each topic, ${noun.many} with recorded views only. Each dot is one ${noun.one}.`,
            formula: "engagement rate = (likes + replies + reposts + quotes) ÷ views × 100",
          },
          {
            title: "Compare",
            plain: tests
              ? `Each topic against the rest of the channel: two-sided Brunner-Munzel test, p from ${count(tests.method.n_permutations)} random reshuffles (fixed seed). Effect size: Cliff's δ, with a 95% CI from the same reshuffles, unadjusted.`
              : "Each topic against the rest of the channel: Brunner-Munzel permutation test and Cliff's δ. Results are not available right now.",
            formula: ["δ = P(topic > rest) − P(topic < rest)", "share of pairs won = (1 + δ) ÷ 2"],
          },
          {
            title: "Correct",
            plain: tests
              ? `Holm's correction across all ${family} tests on this page${familyBreakdown ? ` (${data.topics.length} topics × engagement, share rate, conversation)` : ""}, not only the engagement ones shown here.`
              : "Holm's correction across every topic × engagement, share rate and conversation.",
          },
          {
            title: "Decide",
            plain: tests
              ? `A topic is named in the answer only when its corrected p is below ${alpha} and it has at least ${minPosts} ${noun.many} with recorded views. Medians only describe.`
              : `A higher median is a description, not a tested difference.`,
          },
        ]}
        limits={
          tests
            ? [
                "Every comparison is **exploratory**: it depends on where the topic boundaries fall.",
                `Topics are re-clustered daily with a fixed seed; a few new ${noun.many} or another seed can redraw them, and earlier results have appeared and disappeared.`,
                "A result becomes a finding only after it passes **a stability rule across random seeds**; that rule is not set yet.",
                `The “stood out in” column is a record, not that rule. It counts the ${tests.history ? `${tests.history.clusterings_compared} ${tests.history.clusterings_compared === 1 ? "clustering" : "clusterings"}` : "clusterings"}${tests.history?.since ? ` tested since ${parisDate(tests.history.since)}` : ""}, leaving out those that gave a topic too few ${noun.many} to test.`,
                `The clusterings share most of their ${noun.many}, so they are not independent tests. After a merge or split, a topic may count as new and its count starts again.`,
                "A topic that stood out both ways shows the direction of its current δ, or, while tests are hidden, the direction it stood out in more often.",
                `The CI is unadjusted, so it can exclude 0 while the corrected p stays at ${alpha} or more. Corrected p-values are capped at 1.`,
                `With so few ${noun.many} per topic, only very large differences can be detected: **“not significant” does not mean “no difference”** (even at p = 1.000).`,
                "A gap would be **an association, not an effect** of the topic: topics differ in when they were posted, and the channel's audience changed over time.",
              ]
            : [`Topics with fewer than ${minPosts} ${noun.many} with recorded views are shown in grey and read as indicative only.`]
        }
        more={
          <>
            Every symbol is explained in{" "}
            <a href="#term-rest" className="font-medium text-amber-700 underline underline-offset-4">
              Comparing a topic with the rest of the channel
            </a>
            .
          </>
        }
      />
    </Section>
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
