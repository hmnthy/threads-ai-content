import type { DistributionStats } from "@/lib/api";

// Dòng phụ dùng chung cạnh 1 median (ADR-0023): "Middle half a–b% (IQR) · n = N" (cùng chữ với hộp Key numbers —
// copy-reviewer lượt 4: IQR là độ rộng, khoảng in ra là "middle half"), cờ mẫu nhỏ "too few content units to interpret",
// không hiện mean. n === 0 → câu "no content units…" (backend trả 0.0 cho tập rỗng — không vẽ IQR giả,
// .claude/rules/dashboard.md). Gom về 1 chỗ để 4 trang không tự dựng chuỗi lệch nhau.

export const TOO_FEW_POSTS = "too few content units to interpret";
export const NO_POSTS = "no content units with recorded views";
const IQR_TITLE = "interquartile range: the range the middle 50% of content units fall in";

export function hasPosts(stats: DistributionStats | null | undefined): stats is DistributionStats {
  return stats != null && stats.n > 0;
}

// `digits`: 2 cho engagement rate, 3 cho share rate + conversation rate (cùng quy ước bảng so sánh của /topics)
export function formatIqrRange(stats: DistributionStats, digits = 2): string {
  return `${stats.iqr_low.toFixed(digits)}–${stats.iqr_high.toFixed(digits)}%`;
}

// Ghi chú của 1 median trong hộp Key numbers (K5: median là số, IQR + n ở ghi chú) — dùng chung Overview + Analytics;
// `empty` = câu khi n = 0 (khác nhau theo tập: cửa sổ hay cả kênh). Cờ mẫu nhỏ đọc như dòng phụ của dải hero —
// cùng 1 tập không được nói khác nhau về độ tin cậy ở 2 chỗ (code-reviewer lượt 2)
export function rateNote(stats: DistributionStats, digits: number, empty: string): string {
  if (!hasPosts(stats)) return empty;
  const flag = stats.insufficient_data ? ` · ${TOO_FEW_POSTS}` : "";
  return `Middle half ${formatIqrRange(stats, digits)} (IQR) · n = ${stats.n.toLocaleString("en-US")} content units with recorded views${flag}.`;
}

// Bản chuỗi thuần — cho `aria-live`, mô tả ô heatmap (không chứa được <abbr>)
export function distributionCaptionText(stats: DistributionStats): string {
  if (!hasPosts(stats)) return NO_POSTS;
  const flag = stats.insufficient_data ? ` · ${TOO_FEW_POSTS}` : "";
  return `middle half ${formatIqrRange(stats)} (IQR) · n = ${stats.n}${flag}`;
}

export function Iqr() {
  return (
    <abbr title={IQR_TITLE} className="cursor-help underline decoration-dotted underline-offset-2">
      IQR
    </abbr>
  );
}

// `split` = xuống dòng giữa IQR và n (ô hẹp — 1 dòng làm khung tràn ngang ở 1160px)
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
      Middle half {formatIqrRange(stats)} (<Iqr />)
      {split ? <br /> : " · "}n = {stats.n}
      {flag}
    </>
  );
}
