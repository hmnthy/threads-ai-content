import type { DistributionStats } from "@/lib/api";

// Dòng phụ dùng chung cạnh 1 median (ADR-0023): "IQR a–b% · n=N", cờ mẫu nhỏ "too few posts to interpret",
// không hiện mean. n === 0 → câu "no posts…" (backend trả 0.0 cho tập rỗng — không vẽ IQR giả,
// .claude/rules/dashboard.md). Gom về 1 chỗ để 4 trang không tự dựng chuỗi lệch nhau.

export const TOO_FEW_POSTS = "too few posts to interpret";
export const NO_POSTS = "no posts with recorded views";
const IQR_TITLE = "interquartile range: the range the middle 50% of posts fall in";

export function hasPosts(stats: DistributionStats | null | undefined): stats is DistributionStats {
  return stats != null && stats.n > 0;
}

export function formatIqrRange(stats: DistributionStats): string {
  return `${stats.iqr_low.toFixed(2)}–${stats.iqr_high.toFixed(2)}%`;
}

// Bản chuỗi thuần — cho `aria-live`, mô tả ô heatmap (không chứa được <abbr>)
export function distributionCaptionText(stats: DistributionStats): string {
  if (!hasPosts(stats)) return NO_POSTS;
  const flag = stats.insufficient_data ? ` · ${TOO_FEW_POSTS}` : "";
  return `IQR ${formatIqrRange(stats)} · n=${stats.n}${flag}`;
}

export function Iqr() {
  return (
    <abbr title={IQR_TITLE} className="cursor-help underline decoration-dotted underline-offset-2">
      IQR
    </abbr>
  );
}

// `split` = xuống dòng giữa IQR và n (dải KPI hẹp — 1 dòng làm dải tràn ngang ở 1160px)
export function DistributionCaption({
  stats,
  split = false,
}: {
  stats: DistributionStats;
  split?: boolean;
}) {
  if (!hasPosts(stats)) return <>{NO_POSTS}</>;
  const flag = stats.insufficient_data ? ` · ${TOO_FEW_POSTS}` : "";
  return (
    <>
      <Iqr /> {formatIqrRange(stats)}
      {split ? <br /> : " · "}n={stats.n}
      {flag}
    </>
  );
}
