import type { WindowAnalytics } from "@/lib/api";
import { daysBetweenInclusive, formatDateLabel } from "@/lib/dates";

function formatNumber(n: number): string {
  return n.toLocaleString("en-US");
}

// Content unit row — số thứ tự 2 chữ số, tiêu đề đầy đủ không cắt, bar 220px, số
// bên phải (docs/claude/design-system.md §6). Xếp theo popularity_index
// (post-level views) — KHÁC `data.views` ở hero/KPI strip (account-level).
export function TopContentList({ data }: { data: WindowAnalytics | null }) {
  const windowLabel = data
    ? `${formatDateLabel(data.start)} → ${formatDateLabel(data.end)} · ${daysBetweenInclusive(data.start, data.end)} days`
    : "—";

  const entries = data?.top_content_units ?? [];
  const maxViews = Math.max(...entries.map((entry) => entry.metrics.popularity_index), 1);

  return (
    <section className="flex flex-col gap-3 pt-10">
      <div className="flex flex-wrap items-baseline justify-between gap-4">
        <h2 className="text-xl font-bold tracking-tight text-text-primary">Top content units in window</h2>
        <span className="font-mono text-[13px] tabular-nums text-text-secondary">{windowLabel}</span>
      </div>
      <div className="overflow-hidden rounded-xl border border-border-hairline bg-bg-card">
        {entries.length === 0 ? (
          <div className="flex flex-col items-center gap-2 py-12">
            <span className="text-sm text-text-secondary">No content units published in this window</span>
          </div>
        ) : (
          entries.map((entry, i) => {
            const width = Math.max((entry.metrics.popularity_index / maxViews) * 100, 2);
            return (
              <div
                key={entry.id}
                className={`flex items-center gap-5 px-6 py-4.5 ${i > 0 ? "border-t border-border-hairline" : ""}`}
              >
                <span className="w-6 flex-none text-[13px] font-medium tabular-nums text-text-muted">
                  {String(i + 1).padStart(2, "0")}
                </span>
                <div className="flex min-w-0 flex-1 flex-col gap-1">
                  <span className="text-sm leading-normal text-text-primary">{entry.text ?? "(no text)"}</span>
                  <span className="text-xs tabular-nums text-text-muted">
                    {formatDateLabel(entry.timestamp.slice(0, 10))}
                  </span>
                </div>
                <span className="h-2 w-[220px] flex-none overflow-hidden rounded-full bg-bg-surface">
                  <span className="block h-full rounded-full bg-amber-fill" style={{ width: `${width}%` }} />
                </span>
                <span className="w-[88px] flex-none text-right text-[15px] font-semibold tabular-nums text-text-primary">
                  {formatNumber(entry.metrics.popularity_index)}
                </span>
              </div>
            );
          })
        )}
      </div>
    </section>
  );
}
