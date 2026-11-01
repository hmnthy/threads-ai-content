import { PageHeader } from "@/components/AppBlock";
import { OverviewDashboard } from "@/components/OverviewDashboard";
import { CONTENT_UNIT, OVERVIEW_SECTIONS, RATE_DEFINITION } from "@/lib/appSections";
import { parisTime } from "@/lib/landing";
import { loadAppContext } from "@/lib/load";

// Server component: đầu trang căn giữa dùng chung với Topics (Thy 2026-10-31) + ngữ cảnh đọc phía server (tên topic
// tiếng Anh cho danh sách — B2, mốc dữ liệu cho chip — UI-0025). Câu hỏi: Thy chọn hướng "cửa sổ + bài nhiều views
// nhất" 2026-10-31
export default async function OverviewPage() {
  const context = await loadAppContext("overview", { withChannel: true });
  return (
    <div className="flex flex-1 flex-col">
      <PageHeader
        eyebrow="Measure · One time window"
        title="Overview"
        question="How did the channel perform in the time window you choose, and which content units published in it drew the most views?"
        chips={context.latestSnapshotAt ? [`data as of ${parisTime(context.latestSnapshotAt)}`] : undefined}
        definition={`${CONTENT_UNIT} ${RATE_DEFINITION}`}
        sections={OVERVIEW_SECTIONS}
      />
      <main className="mx-auto w-full max-w-[1280px] flex-1 px-6 py-10">
        <OverviewDashboard
          topicOf={context.topicOf}
          topicCount={context.topicCount}
          channelEngagement={context.channelEngagement}
        />
      </main>
    </div>
  );
}
