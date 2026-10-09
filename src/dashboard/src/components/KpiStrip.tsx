import type { ReactNode } from "react";

import type { DistributionStats, WindowAnalytics } from "@/lib/api";
import { DistributionCaption, hasPosts } from "./DistributionCaption";

function formatNumber(n: number): string {
  return n.toLocaleString("en-US");
}

function rateValue(stats: DistributionStats): string {
  return hasPosts(stats) ? `${stats.median.toFixed(2)}%` : "—";
}

// IQR và n trên 2 dòng (`split`) — 1 dòng làm dải KPI tràn ngang ở 1160px
function statCaption(stats: DistributionStats): ReactNode {
  return <DistributionCaption stats={stats} split />;
}

// Hàng ngang phẳng, không bọc card (docs/claude/design-system.md §6). 3 index
// cuối hiện MEDIAN làm số chính (methodology Layer 2, không phải pooled ratio) —
// IQR/n đi kèm ở dòng mono bên dưới; không hiện mean (ADR-0023: phân phối lệch phải, mean bị vài
// bài đột biến kéo lên).
export function KpiStrip({ data }: { data: WindowAnalytics | null }) {
  const items: { label: string; value: string; caption: ReactNode; dot: boolean }[] = [
    {
      label: "Views",
      value: data ? formatNumber(data.views) : "—",
      caption: "Σ daily views",
      dot: true,
    },
    {
      label: "Content units",
      value: data ? formatNumber(data.content_unit_count) : "—",
      caption:
        data && data.excluded_no_views > 0
          ? `root posts in window · ${data.excluded_no_views} without views, left out of rates`
          : "root posts in window",
      dot: false,
    },
    {
      label: "Interactions",
      value: data ? formatNumber(data.interactions) : "—",
      caption: "likes + replies + reposts + quotes",
      dot: false,
    },
    {
      label: "Engagement",
      value: data ? rateValue(data.engagement) : "—",
      caption: data ? statCaption(data.engagement) : "median per-post rate",
      dot: true,
    },
    {
      label: "Share rate",
      value: data ? rateValue(data.share_rate) : "—",
      caption: data ? statCaption(data.share_rate) : "median per-post rate",
      dot: false,
    },
    {
      label: "Conversation",
      value: data ? rateValue(data.conversation) : "—",
      caption: data ? statCaption(data.conversation) : "median per-post rate",
      dot: false,
    },
  ];

  return (
    <section className="flex gap-8 overflow-x-auto border-b border-border-hairline px-1 py-6">
      {items.map((item) => (
        <div key={item.label} className="flex min-w-[150px] flex-none flex-col gap-1">
          <span className="flex items-center gap-1.5 text-xs font-medium text-text-muted">
            {item.dot && <span className="h-1.5 w-1.5 rounded-full bg-amber-600" aria-hidden="true" />}
            {item.label}
          </span>
          <span className="text-[28px] font-bold tracking-tight tabular-nums text-text-primary">
            {item.value}
          </span>
          <span className="font-mono text-[11px] text-text-muted">{item.caption}</span>
        </div>
      ))}
    </section>
  );
}
