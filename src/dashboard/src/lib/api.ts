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

export interface HourBucket {
  hour: number;
  average_engagement_rate: number;
}

export interface WeekdayBucket {
  weekday: number; // 0=Monday .. 6=Sunday
  average_engagement_rate: number;
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

export const WEEKDAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"] as const;
