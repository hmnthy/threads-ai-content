import type { WindowAnalytics } from "@/lib/api";
import { daysBetweenInclusive } from "@/lib/dates";

function formatNumber(n: number): string {
  return n.toLocaleString("en-US");
}

// Số headline = MEDIAN engagement rate của cửa sổ (không phải pooled ratio
// Σinteractions/Σviews mà mockup UI tự vẽ) — đúng methodology đã chốt (Layer 2,
// docs/claude/data-model.md). Mean/n đi kèm ngay dưới, "2 con số nên đi cùng
// nhau" thay vì chỉ hiện công thức tĩnh.
export function HeroBand({ data }: { data: WindowAnalytics | null }) {
  const engagement = data?.engagement;

  return (
    <section
      className="flex flex-wrap items-end justify-between gap-8 rounded-[20px] px-8 py-7"
      style={{
        background: "linear-gradient(135deg, #7C2D12 0%, #B45309 52%, #9A3412 100%)",
      }}
    >
      <div className="flex min-w-0 flex-col gap-2">
        <span className="text-xs font-semibold tracking-wide text-[#FFF6EC]">
          Engagement rate (median) · selected window
        </span>
        <span className="text-[56px] leading-none font-bold tracking-tight text-white tabular-nums">
          {engagement ? `${engagement.median.toFixed(2)}%` : "—"}
        </span>
        <span className="font-mono text-xs text-[#FFF6EC]">
          {engagement
            ? `mean ${engagement.mean.toFixed(2)}% · n=${engagement.n}${
                engagement.insufficient_data ? " (insufficient data)" : ""
              }`
            : "(likes + replies + reposts + quotes) / views × 100"}
        </span>
      </div>
      <div className="flex flex-wrap gap-8">
        <HeroStat label="Views" value={data ? formatNumber(data.views) : "—"} />
        <HeroStat label="Content units" value={data ? formatNumber(data.content_unit_count) : "—"} />
        <HeroStat
          label="Window"
          value={data ? `${daysBetweenInclusive(data.start, data.end)}d` : "—"}
        />
      </div>
    </section>
  );
}

function HeroStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-xs font-medium text-[#FFF6EC]">{label}</span>
      <span className="text-2xl font-bold text-white tabular-nums">{value}</span>
    </div>
  );
}
