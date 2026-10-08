// Types khớp 1:1 với response model của src/main.py (FastAPI) — xem
// ContentUnitOut / TopicOut trong file đó. Toàn bộ copy hướng ra UI là tiếng Anh
// (quy tắc tuyệt đối trong CLAUDE.md).

export interface ContentUnitMetrics {
  popularity_index: number;
  engagement_rate: number;
  share_rate: number;
  conversation_rate: number;
}

export interface TopicLabel {
  topic_id: string;
  method: string;
  // cosine tới tâm cụm (không phải xác suất)
  centroid_similarity: number | null;
}

export interface ContentUnit {
  id: string;
  text: string | null;
  full_text: string;
  is_multi_post: boolean;
  continuation_count: number;
  timestamp: string | null;
  // null khi chưa có snapshot hoặc snapshot mới nhất views = 0 (ADR-0011)
  metrics: ContentUnitMetrics | null;
  topic: TopicLabel | null;
  umap: [number, number, number] | null;
}

export interface RepresentativePost {
  id: string;
  full_text: string;
  centroid_similarity: number | null;
}

export interface Topic {
  id: string;
  label_en: string;
  description_en: string | null;
  method: string;
  post_count: number;
  keywords: string[];
  // gần tâm nhất trước — để đọc, không phải đầu vào đặt tên của Claude
  representatives: RepresentativePost[];
  // mô tả, không kiểm định; cờ insufficient_data đọc thẳng từ backend
  engagement: DistributionStats;
  excluded_no_views: number;
}

export interface ReplyRoles {
  self_continuation: number;
  author_answer: number;
  outbound: number;
  unassigned: number;
}

export interface ClusterRun {
  run_at: string; // UTC — hiển thị theo Europe/Paris kèm nhãn múi giờ
  model_id: string;
  params: Record<string, string | number | boolean | null>;
  embedding_dim: number | null;
  n_units: number;
  n_clusters: number;
  n_noise: number;
  noise_ratio: number;
  dbcv: number | null; // validity_index
  ari_vs_previous: number | null;
  ari_clustered_only: number | null;
}

export interface PipelineSummary {
  content_units: number;
  units_without_text: number;
  reply_roles: ReplyRoles;
  latest_snapshot_at: string | null;
  latest_cluster_run: ClusterRun | null;
  noise_engagement: DistributionStats | null;
  noise_excluded_no_views: number;
  // ngưỡng mẫu nhỏ duy nhất của backend (MIN_N_PER_BUCKET) — UI ghi số này, không tự đặt ngưỡng
  min_posts_to_compare: number;
}

export interface TopPostEntry {
  id: string;
  text: string | null;
  timestamp: string;
  metrics: ContentUnitMetrics;
}

// Mirror của DistributionStatsOut (src/main.py) — median/mean cạnh nhau CỐ TÌNH
// (Narrative Layering Principle, docs/claude/data-model.md), kèm n/IQR/
// insufficient_data để UI không tuyên bố "tốt nhất" từ 1 tập quá ít bài. Dùng
// chung cho bucket giờ/thứ VÀ cho engagement/share_rate/conversation của 1 cửa sổ
// thời gian (WindowAnalytics bên dưới) — 1 shape, không lặp lại.
export interface DistributionStats {
  median: number;
  mean: number;
  n: number;
  iqr_low: number;
  iqr_high: number;
  insufficient_data: boolean;
}

export interface HourBucket {
  hour: number;
  stats: DistributionStats;
}

export interface WeekdayBucket {
  weekday: number; // 0=Monday .. 6=Sunday
  stats: DistributionStats;
}

export interface TimezoneEngagement {
  timezone: string;
  by_hour: HourBucket[];
  by_weekday: WeekdayBucket[];
}

export interface AnalyticsOverview {
  post_count: number;
  // ADR-0011: bài views = 0 (insight thiếu) — bị loại khỏi mọi phân phối rate, báo riêng
  excluded_no_views: number;
  // Engagement rate toàn kênh, tính theo từng root post — median là số chính
  engagement: DistributionStats;
  top_by_engagement: TopPostEntry[];
  top_by_share_rate: TopPostEntry[];
  top_by_conversation: TopPostEntry[];
  timezones: TimezoneEngagement[];
}

export interface DailyViewsPoint {
  date: string; // "YYYY-MM-DD"
  views: number;
}

export interface DailyViewsSeries {
  points: DailyViewsPoint[];
  min_date: string | null;
  max_date: string | null;
}

// Hero band + KPI strip + top content units cho Timeline Brush (Overview) — tính
// lại từ data thật CHỈ trong [start, end] mỗi khi cửa sổ đổi. `views` = tổng
// account-level daily views trong cửa sổ (gồm views từ replies) — KHÁC
// `top_content_units[].metrics.popularity_index` (post-level, per content unit).
// `engagement`/`share_rate`/`conversation` là median+mean CỦA TỪNG POST trong cửa
// sổ — KHÔNG phải pooled ratio Σinteractions/Σviews (xem src/analysis/stats.py).
export interface WindowAnalytics {
  start: string;
  end: string;
  views: number;
  content_unit_count: number;
  // ADR-0011: bài trong cửa sổ có views = 0 — loại khỏi engagement/share_rate/conversation
  excluded_no_views: number;
  interactions: number;
  engagement: DistributionStats;
  share_rate: DistributionStats;
  conversation: DistributionStats;
  top_content_units: TopPostEntry[];
}

// FastAPI backend base URL — mặc định trỏ localhost:8000 (uvicorn src.main:app),
// override qua NEXT_PUBLIC_API_BASE_URL nếu chạy ở port/host khác.
const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

// Mirror của ReachTiersOut (src/main.py, ADR-0012) — tầng reach toàn lịch sử kênh.
// "Top 20% reach" = top_20, "Above median reach" = above_median; xếp theo
// relative_reach (views ÷ median views các bài đăng ngay trước), views thô chỉ tham chiếu.
export type ReachStatus =
  | "top_20"
  | "above_median"
  | "below_median"
  | "still_growing"
  | "no_baseline"
  | "maturity_unknown";

export interface ReachPost {
  id: string;
  timestamp: string;
  views: number;
  baseline_views: number | null;
  relative_reach: number | null;
  status: ReachStatus;
}

export interface ReachTiers {
  baseline_window: number;
  baseline_min_prior: number;
  maturity: { days: number | null; n_curves: number };
  p50_ratio: number | null;
  p80_ratio: number | null;
  p50_views: number | null;
  p80_views: number | null;
  n_tiered: number;
  insufficient_data: boolean;
  excluded_no_views: number;
  counts: Record<ReachStatus, number>;
  posts: ReachPost[];
}

async function fetchJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Request to ${path} failed with status ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export function getContentUnits(): Promise<ContentUnit[]> {
  return fetchJson<ContentUnit[]>("/content-units");
}

export function getTopics(): Promise<Topic[]> {
  return fetchJson<Topic[]>("/topics");
}

export function getPipelineSummary(): Promise<PipelineSummary> {
  return fetchJson<PipelineSummary>("/pipeline/summary");
}

export function getAnalyticsOverview(): Promise<AnalyticsOverview> {
  return fetchJson<AnalyticsOverview>("/analytics/overview");
}

export function getReachTiers(): Promise<ReachTiers> {
  return fetchJson<ReachTiers>("/analytics/reach");
}

// Toàn bộ lịch sử đã ingest — gọi 1 lần khi trang load để vẽ chart nền + biên rail
// của Timeline Brush. KHÔNG gọi lại khi kéo cửa sổ (chỉ getWindowAnalytics làm vậy).
export function getDailyViewsSeries(): Promise<DailyViewsSeries> {
  return fetchJson<DailyViewsSeries>("/analytics/daily-views");
}

// start/end dạng "YYYY-MM-DD" (inclusive cả 2 đầu, khớp query param của FastAPI).
export function getWindowAnalytics(start: string, end: string): Promise<WindowAnalytics> {
  const params = new URLSearchParams({ start, end });
  return fetchJson<WindowAnalytics>(`/analytics/window?${params.toString()}`);
}

export const WEEKDAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"] as const;
