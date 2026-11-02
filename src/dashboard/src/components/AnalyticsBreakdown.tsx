"use client";

import { useEffect, useState } from "react";
import { getAnalyticsOverview, type AnalyticsOverview, type TopPostEntry } from "@/lib/api";
import { AnswerRow, LoadError, MethodSection, Section, SubSection, ToggleGroup, topicOfUnit, TYPE, UnitText, type KeyNumber } from "@/components/AppBlock";
import { hasPosts, rateNote } from "@/components/DistributionCaption";
import { PostingTimeHeatmap } from "@/components/PostingTimeHeatmap";
import { ANALYTICS_SECTIONS, shortOf } from "@/lib/appSections";
import { formatPostDateTimeParis } from "@/lib/dates";
import { count, pct } from "@/lib/landing";

type MetricKey = "engagement" | "share" | "conversation";

// Mỗi tab = 1 tỉ lệ; tên tab, tên cột và công thức cùng một nguồn (copy-reviewer 2026-10-31: tab/cột/KPI gọi 3 kiểu)
// `digits`: 2 cho engagement, 3 cho share + conversation (cùng quy ước bảng so sánh của /topics)
const RATES: { key: MetricKey; label: string; field: keyof TopPostEntry["metrics"]; formula: string; digits: number }[] = [
  { key: "engagement", label: "Engagement rate", field: "engagement_rate", formula: "(likes + replies + reposts + quotes) ÷ views × 100", digits: 2 },
  { key: "share", label: "Share rate", field: "share_rate", formula: "(reposts + quotes) ÷ views × 100", digits: 3 },
  { key: "conversation", label: "Conversation rate", field: "conversation_rate", formula: "replies ÷ views × 100", digits: 3 },
];

function truncate(text: string, max: number): string {
  return text.length > max ? `${text.slice(0, max)}…` : text;
}

// Trang /analytics theo khuôn khối chung (Thy 2026-10-31): 01 xếp hạng theo tỉ lệ (không phải kiểm định), 02 giờ và
// ngày đăng (mô tả). Bảng xếp hạng chỉ gồm content unit có views ≥ sàn (ADR-0023 1f, sàn tính ở backend)
export function AnalyticsBreakdown({
  topicOf,
  topicCount,
  minPosts,
}: {
  topicOf: Record<string, string | null> | null;
  topicCount: number | null;
  minPosts: number | null;
}) {
  const [data, setData] = useState<AnalyticsOverview | null>(null);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [active, setActive] = useState<MetricKey>("engagement");

  useEffect(() => {
    getAnalyticsOverview()
      .then((overview) => {
        setData(overview);
        setFailed(false);
      })
      .catch((err: unknown) => {
        console.error("analytics: could not load data", err);
        setFailed(true);
      });
  }, [attempt]);

  if (failed) {
    // Câu cho người xem + nút thử lại (ux-reviewer S12, N9)
    return <LoadError onRetry={() => setAttempt((n) => n + 1)} />;
  }
  if (data === null) {
    return <div className="rounded-xl border border-border-hairline bg-bg-card p-6 text-[15px] text-text-secondary">Loading analytics…</div>;
  }

  const rate = RATES.find((item) => item.key === active)!;
  const list = active === "engagement" ? data.top_by_engagement : active === "share" ? data.top_by_share_rate : data.top_by_conversation;
  // Phân phối toàn kênh của đúng tỉ lệ đang chọn (ADR-0031) — câu trả lời so top với kênh
  const channel = active === "engagement" ? data.engagement : active === "share" ? data.share_rate : data.conversation;
  const high = list.length > 0 ? list[0].metrics[rate.field] : null;
  const low = list.length > 0 ? list[list.length - 1].metrics[rate.field] : null;
  const maxValue = Math.max(...list.map((entry) => entry.metrics[rate.field]), 0.0001);
  // views là số nguyên: ≥ P25 (VD 1,755.5) ⇔ ≥ làm tròn lên
  const floor = data.views_floor === null ? null : Math.ceil(data.views_floor);
  const ranked = data.post_count - data.below_views_floor;

  const numbers: KeyNumber[] = [
    {
      value: count(data.post_count),
      label: "content units with recorded views",
      note:
        data.excluded_no_views > 0
          ? `${data.excluded_no_views} of ${count(data.post_count + data.excluded_no_views)} excluded: no views recorded.`
          : undefined,
    },
    ...(floor === null
      ? []
      : [
          {
            value: count(ranked),
            label: "ranked",
            note: `At least ${count(floor)} views each.`,
            share: { part: ranked, whole: data.post_count, of: count(data.post_count) },
          },
        ]),
    {
      value: hasPosts(channel) ? pct(channel.median, rate.digits) : "—",
      label: `channel median ${rate.label.toLowerCase()}`,
      note: rateNote(channel, rate.digits, "No content unit has recorded views yet."),
    },
  ];

  return (
    <div className="flex flex-col gap-10">
      <Section
        id="ranking"
        n="01"
        short={shortOf(ANALYTICS_SECTIONS, "ranking")}
        title="Which content units rank highest on each rate?"
        purpose="Every content unit collected so far (no time window) with enough views to compare, sorted by the rate you choose."
      >
        <AnswerRow
          answer={
            high === null || low === null
              ? "No content unit has recorded views yet."
              : `By ${rate.label.toLowerCase()}, ${
                  // 1 dòng hoặc min = max: không viết "from X to X" (code-reviewer)
                  list.length === 1
                    ? `the only ranked content unit has ${pct(high, rate.digits)}`
                    : pct(low, rate.digits) === pct(high, rate.digits)
                      ? `the top ${list.length} all have ${pct(high, rate.digits)}`
                      : `the top ${list.length} range from ${pct(low, rate.digits)} to ${pct(high, rate.digits)}`
                }${
                  hasPosts(channel)
                    ? `, against a median of ${pct(channel.median, rate.digits)} across all ${count(channel.n)} content units with recorded views`
                    : ""
                }.`
          }
          points={[
            "A **ranking, not a test**: a higher rate here does not show that a content unit differs from the rest of the channel.",
            floor === null
              ? "Every content unit with recorded views is ranked: there are too few yet to set a minimum number of views."
              : `**${count(ranked)} of ${count(data.post_count)}** content units with recorded views have at least ${count(floor)} views and are ranked.`,
            floor === null
              ? null
              : `The cut-off is the **25th percentile of views** among content units with recorded views, recomputed as new views come in; the ${count(data.below_views_floor)} below it are left out.`,
            "Below the cut-off, a few interactions move a rate too much for a fair comparison.",
          ]}
          keyNumbers={numbers}
        />
        <SubSection
          title={`Top ${list.length} by ${rate.label.toLowerCase()}`}
          note={`${rate.label} = ${rate.formula}`}
          action={<ToggleGroup label="Rate to rank by" options={RATES} value={active} onChange={setActive} />}
        >
          <TopTable
            entries={list}
            field={rate.field}
            rateLabel={rate.label}
            digits={rate.digits}
            maxValue={maxValue}
            topicOf={topicOf}
            topicCount={topicCount}
          />
        </SubSection>
        <MethodSection
          steps={[
            {
              title: "Rates",
              plain: "The opening post's interactions divided by its views.",
              formula: RATES.map((item) => `${item.label.toLowerCase()} = ${item.formula}`),
            },
            {
              title: "Median and middle half",
              plain: "The median is the rate of the middle content unit once they are sorted by that rate. The middle half runs from the 25th to the 75th percentile (Q₁ to Q₃); its width, Q₃ − Q₁, is the interquartile range (IQR); this page shows the range itself, Q₁ to Q₃.",
              formula: ["middle half = [ Q_1 , Q_3 ]", "IQR = Q_3 − Q_1"],
            },
            {
              title: "Views cut-off",
              plain: "Only content units with at least as many views as the 25th percentile are ranked. The percentile is taken over content units with recorded views and recomputed whenever views are re-read.",
              formula: "cut-off = P_25( views )",
            },
            {
              title: "Ranking",
              plain: "Content units at or above the cut-off, sorted by the chosen rate; the table shows the top of the list. Each bar's length is its rate divided by the largest rate in the list.",
              formula: "bar = rate ÷ max(rate in the list)",
            },
          ]}
          limits={[
            "A ranking describes the content units; it **does not test** whether a rate differs from the rest of the channel.",
            "Views and interactions are counted to date, so older content units have had more time to collect them.",
            "The cut-off moves as new views come in, so a content unit near it can enter or leave the ranking.",
          ]}
        />
      </Section>

      <Section
        id="posting-time"
        n="02"
        short={shortOf(ANALYTICS_SECTIONS, "posting-time")}
        title="How does engagement rate vary with posting hour and weekday?"
        purpose="The same content units placed on a Paris or a Vietnam clock; every cell shows a median and how many content units it rests on."
      >
        <PostingTimeHeatmap
          timezones={data.timezones}
          excludedNoViews={data.excluded_no_views}
          totalUnits={data.post_count + data.excluded_no_views}
          minPosts={minPosts}
        />
      </Section>
    </div>
  );
}

function TopTable({
  entries,
  field,
  rateLabel,
  digits,
  maxValue,
  topicOf,
  topicCount,
}: {
  entries: TopPostEntry[];
  field: keyof TopPostEntry["metrics"];
  rateLabel: string;
  digits: number;
  maxValue: number;
  topicOf: Record<string, string | null> | null;
  topicCount: number | null;
}) {
  if (entries.length === 0) {
    return <p className={`m-0 ${TYPE.body}`}>No content unit has recorded views yet.</p>;
  }
  const rows = entries.map((entry, index) => {
    const value = entry.metrics[field];
    const topic = topicOfUnit(topicOf, entry.id);
    return {
      entry,
      rank: (index + 1).toString().padStart(2, "0"),
      value,
      width: maxValue > 0 ? Math.max((value / maxValue) * 100, 2) : 0,
      text: entry.text === null ? null : truncate(entry.text, 110),
      topic,
    };
  });
  const bar = (width: number) => (
    <span aria-hidden="true" className="h-1.5 w-16 overflow-hidden rounded-full bg-bg-surface">
      <span className="block h-full rounded-full bg-amber-fill" style={{ width: `${width}%` }} />
    </span>
  );
  return (
    <>
      {/* Dưới sm: mỗi dòng một thẻ xếp dọc như danh sách Overview — không phải cuộn ngang mới thấy views, ngày
          (ux-reviewer N4) */}
      <ol className="m-0 flex list-none flex-col p-0 sm:hidden">
        {rows.map((row) => (
          <li key={row.entry.id} className="flex flex-col gap-2 border-t border-border-hairline py-3 first:border-t-0">
            <span className="flex items-center gap-3">
              <span className={`${TYPE.mono} text-text-muted`}>{row.rank}</span>
              {bar(row.width)}
              <span className={`${TYPE.mono} font-semibold text-text-primary`}>{pct(row.value, digits)}</span>
            </span>
            <UnitText text={row.text} topic={row.topic} topicCount={topicCount} size="cell" />
            <span className={`${TYPE.mono} text-text-secondary`}>
              {/* "· Paris time" như mọi dòng dữ liệu; tiêu đề bảng dùng "(Paris time)" (Thy 2026-11-02) */}
              {count(row.entry.metrics.popularity_index)} views · {formatPostDateTimeParis(row.entry.timestamp)}{" "}
              <span className="whitespace-nowrap">· Paris time</span>
            </span>
          </li>
        ))}
      </ol>
      {/* Từ sm: bảng; cuộn ngang được khi hẹp → chọn được bằng bàn phím (axe scrollable-region-focusable) */}
      <div
        className="hidden overflow-x-auto sm:block"
        tabIndex={0}
        role="region"
        aria-label={`Top content units by ${rateLabel.toLowerCase()}`}
      >
        <table className="w-full min-w-[640px] border-collapse">
          <thead>
            {/* align-bottom: tiêu đề 1 dòng và 2 dòng chung đường chân, sát hàng số liệu (ux-reviewer L3) */}
            <tr className="border-b border-border-hairline text-left align-bottom">
              <th scope="col" className={`py-2.5 pr-3 ${TYPE.th}`}>#</th>
              <th scope="col" className={`py-2.5 pr-4 ${TYPE.th}`}>{rateLabel}</th>
              <th scope="col" className={`py-2.5 pr-4 ${TYPE.th}`}>Content unit</th>
              <th scope="col" className={`py-2.5 pr-4 text-right ${TYPE.th}`}>Views</th>
              <th scope="col" className={`py-2.5 ${TYPE.th}`}>Published (Paris time)</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.entry.id} className="border-t border-border-hairline align-baseline hover:bg-bg-sunken">
                <td className={`py-3 pr-3 ${TYPE.mono} text-text-muted`}>{row.rank}</td>
                <td className="py-3 pr-4">
                  <span className="flex items-center gap-2">
                    {bar(row.width)}
                    <span className={`${TYPE.mono} font-semibold text-text-primary`}>{pct(row.value, digits)}</span>
                  </span>
                </td>
                <td className="max-w-[440px] py-3 pr-4">
                  <UnitText text={row.text} topic={row.topic} topicCount={topicCount} size="cell" />
                </td>
                <td className={`py-3 pr-4 text-right ${TYPE.mono} text-text-secondary`}>
                  {count(row.entry.metrics.popularity_index)}
                </td>
                <td className={`whitespace-nowrap py-3 ${TYPE.mono} text-text-secondary`}>
                  {formatPostDateTimeParis(row.entry.timestamp)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
