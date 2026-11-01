// Nạp dữ liệu phía server cho landing và trang /topics — cùng 5 endpoint, cùng hàm dựng
// (`buildLandingData`), nên hai trang luôn đọc một bộ số (landing CTA: "reads the same data").
import {
  getAnalyticsOverview,
  getContentUnits,
  getPipelineSummary,
  getTopicComparisons,
  getTopics,
  type ContentUnit,
  type DistributionStats,
  type TopicComparisons,
} from "@/lib/api";
import { buildLandingData, type LandingData } from "@/lib/landing";

export interface TopicPageData {
  data: LandingData;
  units: ContentUnit[]; // toạ độ UMAP 3D + metrics từng content unit cho bản đồ và danh sách topic
}

// Ngữ cảnh chung cho Overview + Analytics (đọc phía server): tên topic tiếng Anh của từng content unit để chữ gốc
// tiếng Việt / Pháp trong danh sách không đứng một mình (B2), mốc dữ liệu cho chip đầu trang (UI-0025), và ngưỡng
// mẫu nhỏ của backend (MIN_N_PER_BUCKET — UI ghi số này, không tự đặt ngưỡng)
// Mỗi phần hỏng độc lập (code-reviewer: Promise.all làm 1 endpoint lỗi mất cả trang ngữ cảnh). "Không biết" ≠ "rỗng":
// topicOf = null khi không đọc được → UnitText ghi nhãn trung tính, không suy ra "chưa gom cụm" từ chỗ thiếu khoá
export interface AppContext {
  // id content unit → tên topic (null = unclustered); không có khoá = chưa qua lần gom cụm mới nhất;
  // cả map null = không đọc được thông tin topic lúc này
  topicOf: Record<string, string | null> | null;
  topicCount: number | null; // số topic của lần gom cụm mới nhất (null = chưa gom cụm lần nào, hoặc topicOf null)
  latestSnapshotAt: string | null;
  minPosts: number | null; // null = không đọc được /pipeline/summary: chữ bỏ con số, ô vẫn đọc cờ insufficient_data
  // Engagement rate của mọi content unit đã thu (không cửa sổ thời gian) — mốc so cho câu trả lời khối 01 Overview
  // (Thy 2026-11-01: nêu kèm, ghi "not tested"); chỉ nạp khi trang cần (`withChannel`)
  channelEngagement: DistributionStats | null;
  // Ngày UTC (YYYY-MM-DD, cùng quy ước với bộ lọc bài của /analytics/window: timestamp[:10]) của content unit đăng sớm
  // nhất — biểu đồ Overview bắt đầu từ đây (chuỗi views dùng ngày Pacific và đang lệch nhãn 1 ngày: xem OverviewDashboard)
  // (Thy 2026-11-01: đoạn trước bài đầu tiên không có bài, không hiện); null = không đọc được danh sách content unit
  firstPostDate: string | null;
}

export async function loadAppContext(page: string, { withChannel = false } = {}): Promise<AppContext> {
  const [units, topics, summary, overview] = await Promise.allSettled([
    getContentUnits(),
    getTopics(),
    getPipelineSummary(),
    withChannel ? getAnalyticsOverview() : Promise.resolve(null),
  ]);
  for (const result of [units, topics, summary, overview]) {
    if (result.status === "rejected") console.error(`${page}: could not load part of the page context`, result.reason);
  }
  const ok = <T,>(result: PromiseSettledResult<T>): T | null => (result.status === "fulfilled" ? result.value : null);
  const unitList = ok(units);
  const topicList = ok(topics);
  const summaryData = ok(summary);
  // Thông tin topic cần đủ 3 nguồn: thiếu summary thì không biết đã gom cụm chưa → coi cả map là "không biết"
  let topicOf: Record<string, string | null> | null = null;
  if (unitList && topicList && summaryData) {
    const nameOf = new Map(topicList.map((topic) => [topic.id, topic.label_en]));
    topicOf = {};
    for (const unit of unitList) {
      // umap null = chưa qua lần gom cụm mới nhất (UI-L20260830-precomputed) → không gắn nhãn
      if (unit.umap === null) continue;
      topicOf[unit.id] = unit.topic ? (nameOf.get(unit.topic.topic_id) ?? null) : null;
    }
  }
  return {
    topicOf,
    topicCount: topicOf ? (summaryData?.latest_cluster_run?.n_clusters ?? null) : null,
    latestSnapshotAt: summaryData?.latest_snapshot_at ?? null,
    minPosts: summaryData?.min_posts_to_compare ?? null,
    channelEngagement: ok(overview)?.engagement ?? null,
    firstPostDate:
      unitList?.reduce<string | null>(
        (min, unit) => (unit.timestamp && (min === null || unit.timestamp.slice(0, 10) < min) ? unit.timestamp.slice(0, 10) : min),
        null,
      ) ?? null,
  };
}

export async function loadTopicPageData(page: string): Promise<TopicPageData | null> {
  try {
    const [units, topics, overview, summary, comparisons] = await Promise.all([
      getContentUnits(),
      getTopics(),
      getAnalyticsOverview(),
      getPipelineSummary(),
      // Kiểm định theo topic (ADR-0023) là lớp thêm: lỗi riêng nó không được làm mất cả trang —
      // panel vẫn hiện phần mô tả, ô kiểm định "—"
      getTopicComparisons().catch((error: unknown): TopicComparisons | null => {
        console.error(`${page}: could not load topic comparisons`, error);
        return null;
      }),
    ]);
    return { data: buildLandingData(units, topics, overview, summary, comparisons), units };
  } catch (error) {
    // in ra log server để lỗi lập trình không bị nhầm thành "API không chạy"
    console.error(`${page}: could not load data`, error);
    return null;
  }
}
