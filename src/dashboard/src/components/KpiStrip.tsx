import type { DistributionStats, WindowAnalytics } from "@/lib/api";

function formatNumber(n: number): string {
  return n.toLocaleString("en-US");
}

function statCaption(stats: DistributionStats): string {
  return `mean ${stats.mean.toFixed(2)}% · n=${stats.n}${
    stats.insufficient_data ? " (insufficient data)" : ""
  }`;
}

// Hàng ngang phẳng, không bọc card (docs/claude/design-system.md §6). 3 index
// cuối hiện MEDIAN làm số chính (methodology Layer 2, không phải pooled ratio) —
// mean/n đi kèm ở dòng mono bên dưới, "2 con số nên đi cùng nhau".
export function KpiStrip({ data }: { data: WindowAnalytics | null }) {
  const items = [
    {
      label: "Views",
      value: data ? formatNumber(data.views) : "—",
      caption: "Σ daily views",
      dot: true,
    },
    {
      label: "Content units",
      value: data ? formatNumber(data.content_unit_count) : "—",
      caption: "root posts in window",
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
      value: data ? `${data.engagement.median.toFixed(2)}%` : "—",
      caption: data ? statCaption(data.engagement) : "median per-post rate",
      dot: true,
    },
    {
      label: "Virality",
      value: data ? `${data.virality.median.toFixed(2)}%` : "—",
      caption: data ? statCaption(data.virality) : "median per-post rate",
      dot: false,
    },
    {
      label: "Conversation",
      value: data ? `${data.conversation.median.toFixed(2)}%` : "—",
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
