// Nạp dữ liệu phía server cho landing và trang /topics — cùng 5 endpoint, cùng hàm dựng
// (`buildLandingData`), nên hai trang luôn đọc một bộ số (landing CTA: "reads the same data").
import {
  getAnalyticsOverview,
  getContentUnits,
  getPipelineSummary,
  getTopicComparisons,
  getTopics,
  type ContentUnit,
  type TopicComparisons,
} from "@/lib/api";
import { buildLandingData, type LandingData } from "@/lib/landing";

export interface TopicPageData {
  data: LandingData;
  units: ContentUnit[]; // toạ độ UMAP 3D + metrics từng content unit cho bản đồ và danh sách topic
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
