import { PageHeader } from "@/components/AppBlock";
import { AnalyticsBreakdown } from "@/components/AnalyticsBreakdown";
import { ANALYTICS_SECTIONS, CONTENT_UNIT, RATE_DEFINITION } from "@/lib/appSections";
import type { PickableUnit } from "@/components/UnitVsChannel";
import { firstLine, parisTime } from "@/lib/landing";
import { loadAppContext } from "@/lib/load";

// Server component: đầu trang căn giữa dùng chung với Topics (Thy 2026-10-31) + ngữ cảnh đọc phía server (tên topic
// tiếng Anh cho bảng — B2, mốc dữ liệu — UI-0025, ngưỡng mẫu nhỏ của backend). Bảng xếp hạng chưa qua kiểm định, nên
// câu hỏi nói "rank highest", không "stand out"
// Khối 02 (một content unit so với kênh) dùng chung `UnitVsChannel` với panel hero của landing: dữ liệu dựng phía server
// bằng cùng hàm. Gửi xuống trình duyệt: tập so của kênh + từng topic (`LandingData`, bỏ bản đồ UMAP và bài đại diện mà
// khối không dùng) và bản rút gọn của từng bài có views (id, 3 tỉ lệ, topic, dòng đầu, ngày, views)
export default async function AnalyticsPage() {
  const context = await loadAppContext("analytics", { withComparison: true });
  const comparison = context.comparison
    ? {
        data: {
          ...context.comparison.data,
          mapPoints: [],
          topics: context.comparison.data.topics.map((topic) => ({ ...topic, representatives: [] })),
        },
        units: context.comparison.units
          .flatMap((unit): PickableUnit[] =>
            unit.metrics
              ? [
                  {
                    id: unit.id,
                    rates: {
                      engagement: unit.metrics.engagement_rate,
                      share: unit.metrics.share_rate,
                      conversation: unit.metrics.conversation_rate,
                    },
                    topicId: unit.topic?.topic_id ?? null,
                    text: firstLine(unit.full_text),
                    timestamp: unit.timestamp,
                    views: unit.metrics.popularity_index,
                  },
                ]
              : [],
          )
          // mới nhất trước: người đọc thường tìm bài vừa đăng
          .sort((a, b) => (b.timestamp ?? "").localeCompare(a.timestamp ?? "")),
      }
    : null;
  return (
    <div className="flex flex-1 flex-col">
      <PageHeader
        eyebrow="Measure · Rankings, one content unit, posting time"
        title="Analytics"
        question="Which content units rank highest on each rate, how does any single content unit compare with the rest of the channel, and how does engagement rate vary with posting hour and weekday?"
        chips={context.latestSnapshotAt ? [`data as of ${parisTime(context.latestSnapshotAt)}`] : undefined}
        definition={`${CONTENT_UNIT} ${RATE_DEFINITION}`}
        sections={ANALYTICS_SECTIONS}
      />
      <main className="mx-auto w-full max-w-[1280px] flex-1 px-6 py-10">
        {/* minPosts null khi không đọc được /pipeline/summary: chữ bỏ con số, mọi ô vẫn đọc cờ insufficient_data */}
        <AnalyticsBreakdown
          topicOf={context.topicOf}
          topicCount={context.topicCount}
          minPosts={context.minPosts}
          comparison={comparison}
        />
      </main>
    </div>
  );
}
