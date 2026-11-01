import { PageHeader } from "@/components/AppBlock";
import { AnalyticsBreakdown } from "@/components/AnalyticsBreakdown";
import { ANALYTICS_SECTIONS, CONTENT_UNIT, RATE_DEFINITION } from "@/lib/appSections";
import { parisTime } from "@/lib/landing";
import { loadAppContext } from "@/lib/load";

// Server component: đầu trang căn giữa dùng chung với Topics (Thy 2026-10-31) + ngữ cảnh đọc phía server (tên topic
// tiếng Anh cho bảng — B2, mốc dữ liệu — UI-0025, ngưỡng mẫu nhỏ của backend). Bảng xếp hạng chưa qua kiểm định, nên
// câu hỏi nói "rank highest", không "stand out"
export default async function AnalyticsPage() {
  const context = await loadAppContext("analytics");
  return (
    <div className="flex flex-1 flex-col">
      <PageHeader
        eyebrow="Measure · Rankings and posting time"
        title="Analytics"
        question="Which content units have the highest rates per 100 views, and how does engagement rate vary with posting hour and weekday?"
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
        />
      </main>
    </div>
  );
}
