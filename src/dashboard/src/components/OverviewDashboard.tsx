"use client";

import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { getDailyViewsSeries, getWindowAnalytics, type DailyViewsSeries, type DistributionStats, type WindowAnalytics } from "@/lib/api";
import { AnswerRow, LoadError, MethodSection, Section, type KeyNumber } from "@/components/AppBlock";
import { formatIqrRange, hasPosts, rateNote, TOO_FEW_POSTS } from "@/components/DistributionCaption";
import { HeroBand } from "@/components/HeroBand";
import { MetricArchitectureGrid } from "@/components/MetricArchitectureGrid";
import { TimelineBrush } from "@/components/TimelineBrush";
import { TopContentList } from "@/components/TopContentList";
import { OVERVIEW_SECTIONS, shortOf } from "@/lib/appSections";
import { count, pct } from "@/lib/landing";
import { daysBetweenInclusive, formatFullDate } from "@/lib/dates";

// Trang /overview theo khuôn khối chung (Thy 2026-10-31: làm như /topics): mỗi khối = số + tiêu đề h2 + câu mục
// đích → câu trả lời + ý chính + Key numbers → bằng chứng → "Method and limits" mở sẵn. Dải hero gradient (chữ ký
// tầng A, design-system §2.5) là bằng chứng chính của khối 01; dải số cũ dưới hero bỏ vì lặp số của hero (ux-reviewer Q2, ADR-0031)
export function OverviewDashboard({
  topicOf,
  topicCount,
  channelEngagement,
  firstPostDate,
  dayMismatch,
}: {
  topicOf: Record<string, string | null> | null;
  topicCount: number | null;
  channelEngagement: DistributionStats | null;
  firstPostDate: string | null;
  dayMismatch: { count: number; total: number } | null;
}) {
  const [series, setSeries] = useState<DailyViewsSeries | null>(null);
  const [seriesError, setSeriesError] = useState<string | null>(null);
  const [windowData, setWindowData] = useState<WindowAnalytics | null>(null);
  const [windowLoading, setWindowLoading] = useState(false);
  const [windowFailed, setWindowFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const requestSeq = useRef(0);
  // Cửa sổ vừa yêu cầu — nút thử lại gọi lại đúng cửa sổ này khi lần tải đầu tiên lỗi (chưa có số nào để giữ)
  const lastWindow = useRef<[string, string] | null>(null);
  // Chuỗi views theo ngày bắt đầu từ ngày có content unit đầu tiên (Thy 2026-11-01): đoạn trước đó không có bài nên
  // không hiện; thiếu ngày đầu hoặc cắt còn < 2 điểm → giữ cả chuỗi
  const points = useMemo(() => {
    if (series === null) return null;
    if (firstPostDate === null) return series.points;
    // Nhãn chuỗi = ngày Pacific mà điểm đo, ngày đăng = ngày Paris (ADR-0034): bài đầu tiên đăng tối giờ Paris nên
    // views của nó nằm ở chính ngày đó. Bài đăng 0h–9h sáng Paris thì views rơi vào ngày Pacific trước — giới hạn ADR
    const cut = series.points.filter((point) => point.date >= firstPostDate);
    return cut.length >= 2 ? cut : series.points;
  }, [series, firstPostDate]);

  useEffect(() => {
    getDailyViewsSeries()
      .then((loaded) => {
        setSeries(loaded);
        setSeriesError(null);
      })
      .catch((err: unknown) => {
        // Chi tiết lỗi ở console, log 1 lần ở đây (không trong render)
        console.error("overview: could not load daily views", err);
        setSeriesError(err instanceof Error ? err.message : "unknown error");
      });
  }, [attempt]);

  const handleWindowCommit = useCallback((start: string, end: string) => {
    const seq = ++requestSeq.current;
    lastWindow.current = [start, end];
    setWindowLoading(true);
    setWindowFailed(false);
    getWindowAnalytics(start, end)
      .then((data) => {
        if (seq === requestSeq.current) {
          setWindowData(data);
          setWindowFailed(false);
        }
      })
      .catch((err: unknown) => {
        // Rail/chart vẫn chạy; báo rõ số đang hiện là của cửa sổ trước, không im lặng (ux-reviewer N9)
        console.error("overview: could not load the window", err);
        if (seq === requestSeq.current) setWindowFailed(true);
      })
      .finally(() => {
        if (seq === requestSeq.current) setWindowLoading(false);
      });
  }, []);

  if (seriesError !== null) {
    // Câu cho người xem + nút thử lại (ux-reviewer S12, N9); chi tiết lỗi đã log ở .catch
    return <LoadError onRetry={() => setAttempt((n) => n + 1)} />;
  }

  if (series === null || points === null) {
    return (
      <div className="flex flex-col gap-4">
        <div className="h-[140px] animate-pulse rounded-[20px] bg-bg-surface" />
        <div className="h-[320px] animate-pulse rounded-xl bg-bg-surface" />
      </div>
    );
  }

  // Chỉ mờ phần phụ thuộc cửa sổ khi đang chờ fetch — rail/chart của TimelineBrush luôn bám tay (§5/§8 Motion)
  const dim = { opacity: windowLoading ? 0.85 : 1, transition: "opacity 150ms ease-out" };
  return (
    <div className="flex flex-col gap-10">
      <Section
        id="window"
        n="01"
        short={shortOf(OVERVIEW_SECTIONS, "window")}
        title="How did the channel do in the window you choose?"
        purpose="Drag the window on the chart just below, or pick a preset: every number in blocks 01 and 02 is recomputed for that window."
      >
        {/* Biểu đồ + thanh kéo ngay dưới đầu khối (Thy 2026-11-01): kéo tới đâu, số ngay bên dưới đổi theo — không phải
            cuộn lên xem lại. Sau đó: dải hero → câu trả lời + Key numbers → Method */}
        <TimelineBrush points={points} onWindowCommit={handleWindowCommit} />
        <div style={dim}>
          <HeroBand data={windowData} />
        </div>
        {/* Lỗi lần đầu (chưa có cửa sổ trước) → LoadError + thử lại đúng cửa sổ đó; lỗi sau đó → số cũ vẫn hiện,
            báo rõ (code-reviewer: không nói "previous" khi chưa có, không kẹt "Loading") */}
        {windowFailed && windowData === null ? (
          <LoadError
            what="The numbers for this window could not be loaded."
            onRetry={() => {
              if (lastWindow.current) handleWindowCommit(...lastWindow.current);
            }}
          />
        ) : windowFailed ? (
          <p role="alert" className="m-0 text-[13px] leading-[1.55] text-negative">
            The latest window could not be loaded; the numbers below are still for the previous one. Move the window to try again.
          </p>
        ) : null}
        {/* Chưa có số nào (lần đầu lỗi): không hiện câu "Loading…" cạnh LoadError (code-reviewer lượt 2) */}
        {windowFailed && windowData === null ? null : (
          <div style={dim}>
            <AnswerRow
              answer={windowAnswer(windowData, channelEngagement)}
              points={windowPoints(windowData, channelEngagement)}
              keyNumbers={windowNumbers(windowData)}
            />
          </div>
        )}
        <MethodSection
          steps={[
            {
              title: "Window",
              plain: "The days between the two handles, both included. The chart starts at the channel's first content unit; earlier days, with no content units yet, are not shown. The presets select the last 30, 60 or 90 days with account views; Peak week selects the 7 consecutive days with the most account views.",
            },
            {
              title: "Account views",
              plain: "The whole account's daily views as Threads reports them, summed over the window (V: views in the window; d: each day in it). They are not the views of the content units listed in block 02.",
              formula: "V = Σ_d views_d",
            },
            {
              title: "Which day",
              plain: "The Threads API gives the account's views only as one total per day, and its days run on Pacific time (California). So each chart day starts at midnight Pacific, which is 9 am in Paris for most of the year. A content unit falls in a window by the day it was published in Paris time: the date printed under it in block 02.",
              formula: [
                "chart day = calendar date in America/Los\\_Angeles",
                "content unit day = publish date in Europe/Paris",
                "unit in window when start ≤ content unit day ≤ end   (start, end = chart days at the two handles)",
              ],
            },
            {
              title: "Rates",
              plain: "Each rate divides the opening post's interactions by its views, so content units with few and many views can be compared on the same scale.",
              formula: [
                "engagement rate = (likes + replies + reposts + quotes) ÷ views × 100",
                "share rate = (reposts + quotes) ÷ views × 100",
                "conversation rate = replies ÷ views × 100",
              ],
            },
            {
              title: "Median and middle half",
              plain: "The median is the rate of the middle content unit once they are sorted by that rate. The middle half runs from the 25th to the 75th percentile (Q₁ to Q₃); its width, Q₃ − Q₁, is the interquartile range (IQR); this page shows the range itself, Q₁ to Q₃.",
              formula: ["middle half = [ Q_1 , Q_3 ]", "IQR = Q_3 − Q_1"],
            },
          ]}
          limits={[
            "Content units **without recorded views** are left out of every rate: no recorded views is not a 0% rate.",
            "Interactions and views are **counted to date**, so a content unit published early in the window has had more time to collect them.",
            "Views and interactions are re-read from Threads every 4 hours, only while the collecting laptop is awake, so numbers can be up to a day old; the time at the top of the page says when they were last read.",
            "Content units published after the last day on the chart are in no window yet.",
            `A content unit published **between midnight and 9 am Paris time** (8 am for a few weeks a year) is counted on its Paris date, but the account's views from those first hours land on the chart day before. This only matters at the edges of a window.${
              dayMismatch && dayMismatch.total > 0
                ? ` So far, it applies to ${count(dayMismatch.count)} of the ${count(dayMismatch.total)} content units collected, with or without recorded views.`
                : ""
            }`,
            "A window of a few days holds few content units: read n before reading a median.",
          ]}
        />
      </Section>
      {windowFailed && windowData === null ? null : (
        <div style={dim}>
          <TopContentList data={windowData} topicOf={topicOf} topicCount={topicCount} />
        </div>
      )}
      <MetricArchitectureGrid />
    </div>
  );
}

// Mốc so = median của mọi content unit đã thu (Thy 2026-11-01); chưa kiểm định nên câu ghi "not tested", không
// nói cao/thấp hơn
function windowAnswer(data: WindowAnalytics | null, channel: DistributionStats | null): ReactNode {
  if (!data) return "Loading the selected window…";
  const span = `${formatFullDate(data.start)} to ${formatFullDate(data.end)}`;
  if (!hasPosts(data.engagement)) return `No content unit with recorded views was published from ${span}.`;
  const inWindow = `Content units published from ${span} have a median engagement rate of ${pct(data.engagement.median)}`;
  // Mẫu nhỏ: nêu n + cờ như dòng phụ của dải hero, bỏ vế so với kênh (code-reviewer: không nói quá dữ liệu)
  if (data.engagement.insufficient_data) return `${inWindow} (n = ${data.engagement.n}, ${TOO_FEW_POSTS}).`;
  return channel && hasPosts(channel)
    ? `${inWindow}; across all content units collected so far, it is ${pct(channel.median)} (not tested).`
    : `${inWindow}.`;
}

// Mốc toàn kênh kèm IQR + n và nghĩa của "not tested" (ux-reviewer lượt 4 N4/B3: số mốc không được trần)
function windowPoints(data: WindowAnalytics | null, channel: DistributionStats | null): ReactNode[] {
  if (!data) return [];
  return [
    `**${count(data.content_unit_count)} content units** were published in these ${daysBetweenInclusive(data.start, data.end)} days${
      data.excluded_no_views > 0 ? `; ${data.excluded_no_views} of ${count(data.content_unit_count)} excluded: no views recorded` : ""
    }.`,
    ...(channel && hasPosts(channel) && hasPosts(data.engagement) && !data.engagement.insufficient_data
      ? [
          `**All content units collected so far**: median ${pct(channel.median)}, middle half ${formatIqrRange(channel)} (IQR), n = ${count(channel.n)} content units with recorded views. This window is part of that set, and the gap between the two medians has not been tested, so it does not show a better or worse period.`,
        ]
      : []),
    "**Account views** in the band above are the whole account's daily views as Threads reports them, not the sum of the content units' views.",
    "Each rate shown is the **median across content units**, not a pooled total, so one breakout content unit cannot move it much.",
  ];
}

function windowNumbers(data: WindowAnalytics | null): KeyNumber[] | undefined {
  if (!data) return undefined;
  return [
    {
      value: hasPosts(data.share_rate) ? pct(data.share_rate.median, 3) : "—",
      label: "median share rate",
      note: rateNote(data.share_rate, 3, "No content unit with recorded views in this window."),
    },
    {
      value: hasPosts(data.conversation) ? pct(data.conversation.median, 3) : "—",
      label: "median conversation rate",
      note: rateNote(data.conversation, 3, "No content unit with recorded views in this window."),
    },
    {
      value: count(data.interactions),
      label: "interactions",
      note: "Likes, replies, reposts and quotes on the opening posts of content units published in the window, to date.",
    },
  ];
}
