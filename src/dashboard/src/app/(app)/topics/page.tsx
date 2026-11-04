import { PageHeader } from "@/components/AppBlock";
import { ReloadError } from "@/components/ReloadError";
import { TopicsView } from "@/components/TopicsView";
import { noTopicsSentence, parisTime } from "@/lib/landing";
import { loadTopicPageData } from "@/lib/load";
import { TOPIC_SECTIONS as SECTIONS } from "@/lib/topicSections";
import { TYPE } from "@/lib/typeScale";

// Server component: đọc cùng bộ số với landing mỗi request (`lib/load.ts`), rồi giao cho
// TopicsView (client) vẽ. Câu hỏi của trang: chữ Thy duyệt 2026-10-09 (topics-proposal.md §1).
export default async function TopicsPage() {
  const loaded = await loadTopicPageData("topics");
  const summary = loaded?.data.summary;
  const run = summary?.latest_cluster_run ?? null;
  return (
    <div className="flex flex-1 flex-col">
      {/* Đầu trang căn giữa dùng chung (AppBlock `PageHeader`, Thy 2026-10-29 / 2026-10-31). Câu hỏi: Thy chốt
          2026-10-29 (c) — phép so 2 phía, "differ", không "higher". Chip mốc dữ liệu: UI-0025-published-snapshot
          (kèm giờ + múi giờ, UI-0017-run-time) */}
      <PageHeader
        eyebrow="Group · Topics from text"
        title="Topic Explorer"
        question="What does the channel write about, and does any topic's engagement differ from the rest of the channel?"
        chips={
          summary
            ? [
                run ? `clustered ${parisTime(run.run_at)}` : "not clustered yet",
                summary.latest_snapshot_at ? `data as of ${parisTime(summary.latest_snapshot_at)}` : null,
              ]
            : undefined
        }
        // Mục lục 6 khối; số khớp số trên tiêu đề mỗi khối (AppBlock `Section`)
        sections={loaded && loaded.data.topics.length > 0 ? SECTIONS : undefined}
      />
      <main className="mx-auto w-full max-w-[1280px] flex-1 px-6 py-10">
        {/* Lỗi tải + trạng thái rỗng theo cùng component / thang chữ với trang app khác (ux-reviewer 2026-11-04:
            C2 LoadError, T1 body 15px) */}
        {!loaded ? (
          <ReloadError />
        ) : loaded.data.topics.length === 0 ? (
          <div className="rounded-xl border border-border-hairline bg-bg-card p-6">
            <p className={`m-0 ${TYPE.body}`}>
              {run
                ? noTopicsSentence(run.n_units)
                : "No clustering run is stored yet, so there are no topics to show. Topics appear after the daily NLP job runs."}
            </p>
          </div>
        ) : (
          <TopicsView data={loaded.data} units={loaded.units} />
        )}
      </main>
    </div>
  );
}
