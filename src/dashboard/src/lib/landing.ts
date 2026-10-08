// Dữ liệu hiển thị của landing (tầng B) — dựng từ API thật, không số nào gõ cứng
// (docs/design/landing-handoff.md §0, §4). Chỉ đếm, sắp xếp và đổi đơn vị hiển thị ở đây;
// median/IQR/n/cờ insufficient_data luôn lấy từ backend (UI-L20260903-small-n-flag).
import type {
  AnalyticsOverview,
  ContentUnit,
  DistributionStats,
  PipelineSummary,
  Topic,
} from "@/lib/api";

// Bài minh hoạ của hero — lựa chọn thiết kế của mockup (post 17939285085325700), không phải số liệu
export const HERO_POST_ID = "17939285085325700";
export const HERO_QUESTION =
  'Did "8 kinh nghiệm sau 8 năm ở Pháp" (8 lessons from 8 years in France) do better than the channel\'s usual post?';

export interface TopicView {
  id: string;
  name: string;
  postCount: number;
  keywords: string[];
  representatives: { id: string; text: string; similarity: number | null }[];
  stats: DistributionStats;
  excluded: number;
  rates: number[]; // engagement % của các bài đo được trong topic (chấm trên strip)
}

export interface HeroPost {
  id: string;
  rate: number;
  firstLine: string;
  topicId: string | null;
  similarity: number | null;
  nearestToCentre: boolean; // bài đứng đầu danh sách bài gần tâm của topic
}

export interface LandingData {
  snapshotDate: string | null;
  firstPostAt: string | null; // bài sớm nhất trong DB — "since <tháng năm>" (không nói "toàn lịch sử")
  axisMax: number; // biên phải trục engagement % của mọi strip
  channel: {
    rates: number[];
    stats: DistributionStats;
    excluded: number;
    total: number; // bài đo được + bài bị loại (mẫu số của dòng loại)
  };
  hero: HeroPost | null;
  heroFound: boolean; // bài hero có trong DB (dù chưa có views) — để báo đúng lý do khi trống
  topics: TopicView[]; // nhiều bài trước
  // A4: 6 bài không chữ và 6 bài không views là CÙNG 6 bài? Code không bảo đảm điều đó
  // (UI-0011-two-exclusions) nên chỉ gộp thành 1 dòng khi kiểm thấy 2 tập trùng nhau
  sameExcludedPosts: boolean;
  noise: { rates: number[]; stats: DistributionStats | null; excluded: number };
  mapPoints: { x: number; y: number; topicId: string | null }[]; // UMAP dim 1–2, chuẩn hoá 0–100
  summary: PipelineSummary;
}

export function firstLine(text: string, max = 110): string {
  const line = text.trim().split("\n")[0].trim();
  return line.length > max ? `${line.slice(0, max).trimEnd()}…` : line;
}

export function pct(value: number, digits = 2): string {
  return `${value.toFixed(digits)}%`;
}

export function count(value: number): string {
  return value.toLocaleString("en-US");
}

// run_at lưu UTC → hiển thị Europe/Paris (có giờ mùa hè), luôn kèm nhãn múi giờ (UI-0017-run-time)
export function parisTime(iso: string): string {
  const parts: Record<string, string> = {};
  for (const part of new Intl.DateTimeFormat("en-GB", {
    timeZone: "Europe/Paris",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(new Date(iso))) {
    parts[part.type] = part.value;
  }
  return `${parts.year}-${parts.month}-${parts.day} ${parts.hour}:${parts.minute} Paris time`;
}

// "April 2025", "7 Oct 2026" — ngày theo Europe/Paris như mọi mốc khác trên trang
export function monthYear(iso: string): string {
  return new Intl.DateTimeFormat("en-GB", {
    timeZone: "Europe/Paris",
    month: "long",
    year: "numeric",
  }).format(new Date(iso));
}

export function dayMonthYear(iso: string): string {
  return new Intl.DateTimeFormat("en-GB", {
    timeZone: "Europe/Paris",
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(new Date(iso));
}

// Thứ hạng so với các bài KHÁC (bài không so với chính nó): số bài thấp hơn và % trên số bài
// còn lại. % làm tròn XUỐNG để câu "higher than X%" luôn đúng — làm tròn gần nhất có thể biến
// 49,7% thành "50%" ở nhánh dưới median và đọc như mâu thuẫn.
export function rankAmongOthers(
  rates: number[],
  rate: number,
): { below: number; others: number; share: number } {
  const below = rates.filter((value) => value < rate).length;
  const others = rates.includes(rate) ? rates.length - 1 : rates.length;
  return { below, others, share: others > 0 ? Math.floor((below * 100) / others) : 0 };
}

export function buildLandingData(
  units: ContentUnit[],
  topics: Topic[],
  overview: AnalyticsOverview,
  summary: PipelineSummary,
): LandingData {
  const measurable = units.filter((unit) => unit.metrics !== null);
  const rateOf = new Map(measurable.map((unit) => [unit.id, unit.metrics!.engagement_rate]));
  const ratesWhere = (keep: (unit: ContentUnit) => boolean) =>
    measurable.filter(keep).map((unit) => unit.metrics!.engagement_rate);

  const topicViews: TopicView[] = topics
    .filter((topic) => topic.method === "cluster")
    .map((topic) => ({
      id: topic.id,
      name: topic.label_en,
      postCount: topic.post_count,
      keywords: topic.keywords,
      representatives: topic.representatives.map((rep) => ({
        id: rep.id,
        text: firstLine(rep.full_text),
        similarity: rep.centroid_similarity,
      })),
      stats: topic.engagement,
      excluded: topic.excluded_no_views,
      rates: ratesWhere((unit) => unit.topic?.topic_id === topic.id),
    }))
    .sort((a, b) => b.postCount - a.postCount);

  const heroUnit = units.find((unit) => unit.id === HERO_POST_ID);
  const heroRate = heroUnit ? rateOf.get(heroUnit.id) : undefined;
  const heroTopicId = heroUnit?.topic?.topic_id ?? null;
  const hero: HeroPost | null =
    heroUnit && heroRate !== undefined
      ? {
          id: heroUnit.id,
          rate: heroRate,
          firstLine: firstLine(heroUnit.full_text),
          topicId: heroTopicId,
          similarity: heroUnit.topic?.centroid_similarity ?? null,
          nearestToCentre:
            topicViews.find((topic) => topic.id === heroTopicId)?.representatives[0]?.id ===
            heroUnit.id,
        }
      : null;

  // Bài nhiễu = đã embed (có toạ độ UMAP) nhưng không thuộc topic nào
  const noiseRates = ratesWhere((unit) => unit.topic === null && unit.umap !== null);

  const placed = units.filter((unit) => unit.umap !== null);
  const xs = placed.map((unit) => unit.umap![0]);
  const ys = placed.map((unit) => unit.umap![1]);
  const scale = (value: number, values: number[]) => {
    const lo = Math.min(...values);
    const span = Math.max(...values) - lo || 1;
    return ((value - lo) / span) * 100;
  };

  const allRates = measurable.map((unit) => unit.metrics!.engagement_rate);
  const noText = units.filter((unit) => !unit.full_text.trim()).map((unit) => unit.id);
  const noViews = new Set(units.filter((unit) => unit.metrics === null).map((unit) => unit.id));
  const sameExcludedPosts =
    noText.length > 0 &&
    noText.length === summary.units_without_text &&
    noViews.size === overview.excluded_no_views &&
    noText.length === noViews.size &&
    noText.every((id) => noViews.has(id));
  return {
    // ngày theo giờ Paris, cùng múi với mốc "clustered … Paris time" trên trang
    snapshotDate: summary.latest_snapshot_at ? parisTime(summary.latest_snapshot_at).slice(0, 10) : null,
    firstPostAt: units.reduce<string | null>(
      (min, unit) =>
        unit.timestamp && (min === null || unit.timestamp < min) ? unit.timestamp : min,
      null,
    ),
    // trục chung: bài cao nhất + lề 0.2 điểm cho chấm, làm tròn lên bội 0.2 (mockup: 5.6 cho max 5.38)
    axisMax: Math.ceil((Math.max(...allRates, 1) + 0.2) * 5) / 5,
    channel: {
      rates: allRates,
      stats: overview.engagement,
      excluded: overview.excluded_no_views,
      total: overview.post_count + overview.excluded_no_views,
    },
    hero,
    heroFound: heroUnit !== undefined,
    sameExcludedPosts,
    topics: topicViews,
    noise: {
      rates: noiseRates,
      stats: summary.noise_engagement,
      excluded: summary.noise_excluded_no_views,
    },
    mapPoints: placed.map((unit) => ({
      x: scale(unit.umap![0], xs),
      y: scale(unit.umap![1], ys),
      topicId: unit.topic?.topic_id ?? null,
    })),
    summary,
  };
}

export interface SwarmDot {
  x: number; // px trong bề rộng `width`
  y: number; // px
  index: number; // vị trí trong mảng giá trị đầu vào
}

// Xếp chấm theo giá trị tăng dần: thử y = tâm, tâm±step, tâm±2step… lấy chỗ đầu tiên không
// chạm chấm đã đặt (khoảng cách ≥ minDist). Hết chỗ thì đặt ở tâm — không bỏ chấm nào.
export function swarm(
  values: number[],
  opts: { width: number; axisMax: number; cy: number; step: number; minDist: number; tries: number },
): SwarmDot[] {
  const order = values.map((value, index) => ({ value, index })).sort((a, b) => a.value - b.value);
  const placed: SwarmDot[] = [];
  for (const { value, index } of order) {
    const x = (value / opts.axisMax) * opts.width;
    let y = opts.cy;
    for (let k = 0; k < opts.tries; k++) {
      const candidate = opts.cy + (k === 0 ? 0 : (k % 2 ? 1 : -1) * Math.ceil(k / 2) * opts.step);
      if (placed.every((p) => (p.x - x) ** 2 + (p.y - candidate) ** 2 >= opts.minDist ** 2)) {
        y = candidate;
        break;
      }
    }
    placed.push({ x, y, index });
  }
  return placed;
}

// Strip 1 hàng (bảng topic, CMI, ô "This post"): toạ độ x theo % để co giãn theo cột
export function rowSwarm(
  values: number[],
  axisMax: number,
  cy: number,
  step: number,
  minDist = 6.5,
  width = 700,
): { left: string; top: string }[] {
  return swarm(values, { width, axisMax, cy, step, minDist, tries: 9 }).map((dot) => ({
    left: `${(dot.x / width) * 100}%`,
    top: `${dot.y}px`,
  }));
}

export function axisPct(value: number, axisMax: number): string {
  return `${(value / axisMax) * 100}%`;
}

export function ticks(axisMax: number): number[] {
  return Array.from({ length: Math.floor(axisMax) + 1 }, (_, i) => i);
}
