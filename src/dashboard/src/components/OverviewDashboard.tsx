"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { getDailyViewsSeries, getWindowAnalytics, type DailyViewsSeries, type WindowAnalytics } from "@/lib/api";
import { HeroBand } from "@/components/HeroBand";
import { KpiStrip } from "@/components/KpiStrip";
import { MetricArchitectureGrid } from "@/components/MetricArchitectureGrid";
import { TimelineBrush } from "@/components/TimelineBrush";
import { TopContentList } from "@/components/TopContentList";

// Đúng thứ tự dọc Tầng A (docs/claude/design-system.md §7): topbar/tab pill nằm
// trong Nav.tsx (layout.tsx) — component này chỉ phụ trách từ hero band trở
// xuống: hero → chart+brush → KPI strip → metric architecture → top content units.
export function OverviewDashboard() {
  const [series, setSeries] = useState<DailyViewsSeries | null>(null);
  const [seriesError, setSeriesError] = useState<string | null>(null);
  const [windowData, setWindowData] = useState<WindowAnalytics | null>(null);
  const [windowLoading, setWindowLoading] = useState(false);
  const requestSeq = useRef(0);

  useEffect(() => {
    getDailyViewsSeries()
      .then(setSeries)
      .catch((err: unknown) => {
        setSeriesError(err instanceof Error ? err.message : "Failed to load data from the API.");
      });
  }, []);

  const handleWindowCommit = useCallback((start: string, end: string) => {
    const seq = ++requestSeq.current;
    setWindowLoading(true);
    getWindowAnalytics(start, end)
      .then((data) => {
        if (seq === requestSeq.current) setWindowData(data);
      })
      .catch(() => {
        // Rail/chart vẫn hoạt động dù 1 lần fetch KPI lỗi — giữ windowData cũ,
        // không crash cả trang vì 1 request window đơn lẻ fail.
      })
      .finally(() => {
        if (seq === requestSeq.current) setWindowLoading(false);
      });
  }, []);

  if (seriesError !== null) {
    return (
      <div className="rounded-xl border border-border-hairline bg-bg-card p-6 text-negative">
        Could not reach the API at the configured base URL. Is `uvicorn src.main:app` running? (
        {seriesError})
      </div>
    );
  }

  if (series === null) {
    return (
      <div className="flex flex-col gap-4">
        <div className="h-[140px] animate-pulse rounded-[20px] bg-bg-surface" />
        <div className="h-[320px] animate-pulse rounded-xl bg-bg-surface" />
      </div>
    );
  }

  // Chỉ dim phần phụ thuộc windowData khi đang chờ fetch — rail/chart của
  // TimelineBrush không dim, luôn bám tay theo thời gian thực (§5/§8 Motion).
  return (
    <div className="flex flex-col gap-5">
      <div style={{ opacity: windowLoading ? 0.85 : 1, transition: "opacity 150ms ease-out" }}>
        <HeroBand data={windowData} />
      </div>
      <TimelineBrush points={series.points} onWindowCommit={handleWindowCommit} />
      <div
        className="flex flex-col gap-5"
        style={{ opacity: windowLoading ? 0.85 : 1, transition: "opacity 150ms ease-out" }}
      >
        <KpiStrip data={windowData} />
        <MetricArchitectureGrid />
        <TopContentList data={windowData} />
      </div>
    </div>
  );
}
