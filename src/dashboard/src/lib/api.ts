// Types khớp 1:1 với response model của src/main.py (FastAPI) — xem
// ContentUnitOut / TopicOut trong file đó. Toàn bộ copy hướng ra UI là tiếng Anh
// theo quy tắc đã chốt (docs/claude/architecture.md).

export interface ContentUnitMetrics {
  popularity_index: number;
  engagement_rate: number;
  virality_index: number;
  conversation_rate: number;
}

export interface TopicLabel {
  topic_id: string;
  method: string;
  confidence: number | null;
}

export interface ContentUnit {
  id: string;
  text: string | null;
  full_text: string;
  is_multi_post: boolean;
  continuation_count: number;
  timestamp: string | null;
  metrics: ContentUnitMetrics | null;
  topic: TopicLabel | null;
  umap: [number, number, number] | null;
}

export interface Topic {
  id: string;
  label_en: string;
  description_en: string | null;
  method: string;
  post_count: number;
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
// chung cho bucket giờ/thứ VÀ cho engagement/virality/conversation của 1 cửa sổ
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
  average_engagement_rate: number;
  top_by_engagement: TopPostEntry[];
  top_by_virality: TopPostEntry[];
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
// `engagement`/`virality`/`conversation` là median+mean CỦA TỪNG POST trong cửa
// sổ — KHÔNG phải pooled ratio Σinteractions/Σviews (xem src/analysis/stats.py).
export interface WindowAnalytics {
  start: string;
  end: string;
  views: number;
  content_unit_count: number;
  interactions: number;
  engagement: DistributionStats;
  virality: DistributionStats;
  conversation: DistributionStats;
  top_content_units: TopPostEntry[];
}

// FastAPI backend base URL — mặc định trỏ localhost:8000 (uvicorn src.main:app),
// override qua NEXT_PUBLIC_API_BASE_URL nếu chạy ở port/host khác.
const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

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

export function getAnalyticsOverview(): Promise<AnalyticsOverview> {
  return fetchJson<AnalyticsOverview>("/analytics/overview");
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
