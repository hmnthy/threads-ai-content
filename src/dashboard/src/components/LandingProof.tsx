"use client";

import { useMemo, useState } from "react";
import type { TopicComparisonRow } from "@/lib/api";
import { AnswerRow, Bullets, H, MethodSection, Section, SubSection, TermLink, TermMore, TYPE } from "@/components/AppBlock";
import { VerdictLabel, VerdictMark, tooFewLabel, verdictParts } from "@/components/Verdict";
import { formatIqrRange } from "@/components/DistributionCaption";
import { sectionShort } from "@/lib/topicSections";
import {
  andList,
  axisPct,
  count,
  familyBreakdown as holmBreakdown,
  formatP,
  historySentence,
  noneStandOutReason,
  parisDate,
  pct,
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

// Panel "topic so với phần còn lại của kênh" (/topics khối 03 + Proof của landing). Median/IQR/n theo topic là số
// thật từ API (mô tả, dữ liệu mới nhất); Cliff's δ + p Holm đọc `/topics/comparisons` — tính trong job NLP sau mỗi lần
// gom cụm, mang mốc giờ riêng (ADR-0023). Họ Holm = mọi phép so có p xác định trên trang Topics (mọi topic ×
// engagement / share_rate / conversation), kích thước họ đọc từ API (`holm_family_size`), không tự nhân. Không tải
// được / chưa chạy lần nào → ô "—" + câu nói đúng lý do (`topicTestsStatus`); kết quả thuộc lần gom cụm cũ → API ẩn
// δ/p, ô "—" kèm lý do (Thy chốt D3).
// Panel engagement — MỘT component cho /topics và landing (Thy 2026-11-01, ADR-0032: landing dùng lại bản /topics,
// hình khối theo `LandingBlocks` của AppBlock). Câu trả lời sinh từ dữ liệu; phép so 2 phía nên câu hỏi là "differ"
// (Thy chốt 2026-10-29 (c)), trên cả landing
export function TopicEngagementPanel({ data, noun }: { data: LandingData; noun: Noun }) {
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

  const anyFlagged = data.topics.some((t) => t.stats.insufficient_data);
  const names = (list: TopicView[]) => andList(list.map((t) => t.name));
  // "9 topics ×" chỉ khi họ đúng bằng số topic × 3 chỉ số (helper chung `familyBreakdown`)
  const familyBreakdown =
    tests && holmBreakdown(tests, data.topics.length)
      ? `: ${data.topics.length} topics × 3 rates (engagement, share and conversation rate)`
      : "";
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
  // Thy 2026-10-29: không topic nào đạt thì giải thích vì sao bằng số của chính lần kiểm định,
  // thành khối riêng ngay dưới câu trả lời — không ẩn, không chìm trong dòng phụ
  const whyNone =
    testsShown && higher.length + lower.length === 0 ? noneStandOutReason(tests, data.topics, noun, "shown in grey", true) : [];

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

// Trình bày theo luật "trình bày như nhà nghiên cứu NLP" (Thy 2026-10-29): đầu khối 2 cột (ý chính + số chính), chú
// giải biểu đồ luôn hiện, tên topic không cắt, header link tới định nghĩa, dòng ít bài dùng chữ muted thay độ mờ,
// dòng đọc khi hover có vùng riêng xếp dọc, < md mỗi topic 1 thẻ (không cuộn ngang). Phép so 2 phía nên hỏi
// "differ", không "higher" (Thy chốt 2026-10-29 (c); landing theo từ 2026-11-01, ADR-0032)
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
  // Số phép kiểm engagement thật = dòng có p xác định (topic quá ít bài không được kiểm — code-reviewer PR 2b)
  const engagementTests = tests ? Object.values(tests.engagement).filter((row) => row.p_value !== null).length : 0;
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
          `Each topic is compared with **every other ${noun.one}**, unclustered ones included, not with the channel median; the dashed line on the chart marks that median as a reference only.`,
          // Chuyển từ ghi chú hộp Key numbers (ux-reviewer N12: 3 ý dồn trong 1 ghi chú 13px) — UI-0011-excluded
          data.channel.excluded > 0
            ? `${data.channel.excluded} of ${count(data.channel.total)} excluded: no views recorded${
                data.sameExcludedPosts ? " (the same ones have no text, so they are in no topic)" : ""
              }.`
            : null,
          anyStanding ? `p-values are Holm-corrected across all ${family} tests${familyBreakdown}.` : null,
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
              {/* `below` nằm ngoài lưới, ngay dưới tiêu đề khối h2: tag h3, vai box-title (T5) */}
              <H level={3} role="box-title" className={TYPE.h4}>
                Why no topic stands out yet
              </H>
              <Bullets items={whyNone} />
            </div>
          ) : null
        }
        points={points}
        keyNumbers={[
          // Một kết quả thống kê = một dòng (ADR-0030 K5): median kênh là số, IQR + n + phần bị loại ở ghi chú. n cùng
          // tập với `channel.stats.n` (cả unit không chữ / đăng sau lần gom cụm) — UI-0011-excluded
          {
            value: hasChannelMedian ? pct(channelMedian) : "—",
            label: "channel median engagement rate",
            note: hasChannelMedian
              ? `Middle half ${formatIqrRange(data.channel.stats)} (IQR) · n = ${count(data.channel.stats.n)} ${noun.many} with recorded views.`
              : `No ${noun.one} has recorded views yet.`,
            term: "median",
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
            <span className={TYPE.th}>Marks on the chart</span>
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
            <span className={TYPE.th}>The “Holm p” and “Stood out in” columns</span>
            {/* Đủ 3 nhãn kết quả như chú giải khối 04, kể cả ▲/▼ của cột Holm p (ux-reviewer B1: thiếu ▲ hôm nay, còn
                dòng ▲ duy nhất lại nói về lịch sử) */}
            <ul className="m-0 flex list-none flex-col gap-1 p-0 text-[13px] text-text-secondary">
              <li className="flex items-center gap-1.5">
                <VerdictMark verdict="higher" /> Holm p: stood out above (▲) or below (▼) after correction, today
              </li>
              <li className="flex items-center gap-1.5">
                <VerdictMark verdict="not distinguishable" /> Holm p: not significant after correction
              </li>
              <li className="flex items-center gap-1.5">
                <VerdictMark verdict="too few posts" /> Holm p: {tooFewLabel(noun, minPosts).replace(/^T/, "t")} (row in grey)
              </li>
              {/* Không flex: phần chữ sau nhãn là một luồng chữ, không thành cột thứ 2 bắt đầu bằng ":" (ux-reviewer) */}
              <li>
                <span className="whitespace-nowrap text-text-primary">k of m ▲ / ▼</span>: “Stood out in” counts past
                re-clusterings where the topic stood out, a record, not today&apos;s result
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
              ? `Holm's correction across all ${family} tests${familyBreakdown ? ` (${data.topics.length} topics × engagement, share and conversation rate)` : ""}, not only the ${
                  // Kết quả cũ (stale): API trả p = null dù phép kiểm đã chạy → không đếm (code-reviewer PR 2b lượt 2)
                  tests.stale || engagementTests === 0
                    ? "engagement ones"
                    : `${engagementTests} engagement ${engagementTests === 1 ? "test" : "tests"} shown here`
                }.`
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
            <TermMore term="rest">
              Comparing a topic with the rest of the channel
            </TermMore>
            .
          </>
        }
      />
    </Section>
  );
}
