import Link from "next/link";
import { TopicsView } from "@/components/TopicsView";
import { parisTime } from "@/lib/landing";
import { loadTopicPageData } from "@/lib/load";
import { TOPIC_SECTIONS as SECTIONS } from "@/lib/topicSections";

// Server component: đọc cùng bộ số với landing mỗi request (`lib/load.ts`), rồi giao cho
// TopicsView (client) vẽ. Câu hỏi của trang: chữ Thy duyệt 2026-10-09 (topics-proposal.md §1).
export default async function TopicsPage() {
  const loaded = await loadTopicPageData("topics");
  const summary = loaded?.data.summary;
  const run = summary?.latest_cluster_run ?? null;
  return (
    <div className="flex flex-1 flex-col">
      {/* Nội dung header nằm trong cùng khung 1280px với Nav và <main> — thiếu khung này thì trên màn
          hình rộng tiêu đề dạt sát mép trái, lệch với phần thân căn giữa */}
      {/* Đầu trang căn giữa (Thy 2026-10-29): tiêu đề 40px, câu hỏi của trang, mốc dữ liệu dạng chip, mục lục
          6 khối. Vẫn trong khung 1280px như Nav và <main> */}
      <header className="border-b border-border-hairline bg-bg-card">
        <div className="mx-auto flex w-full max-w-[1280px] flex-col items-center gap-4 px-6 pb-10 pt-12 text-center">
          <span className="text-[12px] font-semibold tracking-[0.14em] text-amber-700">TOPIC ANALYSIS</span>
          <h1 className="m-0 text-[40px] font-bold leading-[1.1] tracking-[-0.025em] text-text-primary">Topic Explorer</h1>
          {/* Thy chốt 2026-10-29 (c): phép so 2 phía — "differ", không "higher" */}
          <p className="m-0 max-w-[720px] text-[18px] leading-[1.55] text-text-secondary [text-wrap:balance]">
            What does the channel write about, and does any topic&apos;s engagement differ from the rest of the
            channel?
          </p>
          {summary ? (
            <p className="m-0 flex flex-wrap justify-center gap-2 font-mono text-[12.5px] text-text-secondary">
              <span className="rounded-full border border-border-hairline bg-bg-sunken px-3 py-1">
                {run ? `clustered ${parisTime(run.run_at)}` : "not clustered yet"}
              </span>
              {/* UI-0025-published-snapshot: mốc dữ liệu kèm giờ + múi giờ (UI-0017-run-time) */}
              {summary.latest_snapshot_at ? (
                <span className="rounded-full border border-border-hairline bg-bg-sunken px-3 py-1">
                  data as of {parisTime(summary.latest_snapshot_at)}
                </span>
              ) : null}
            </p>
          ) : null}
          {/* Mục lục 6 khối: thấy cả trang trong 1 dòng, nhảy thẳng tới khối (Thy 2026-10-29: đọc nhanh
              không sót khối). Số khớp số trên tiêu đề mỗi khối (AppBlock `Section`) */}
          {loaded && loaded.data.topics.length > 0 ? (
            <nav aria-label="Sections of this page" className="mt-4 w-full border-t border-border-hairline pt-6">
              <ol className="m-0 flex list-none flex-wrap justify-center gap-2 p-0">
                {SECTIONS.map(([id, n, label]) => (
                  <li key={id}>
                    <a
                      href={`#${id}`}
                      className="inline-flex min-h-[44px] items-center gap-2 rounded-full border border-border-hairline bg-bg-card px-4 text-[15px] font-medium text-text-primary transition-colors hover:border-amber-600 hover:text-amber-700"
                    >
                      <span className="font-mono text-[12.5px] font-semibold text-amber-600">{n}</span>
                      {label}
                    </a>
                  </li>
                ))}
              </ol>
            </nav>
          ) : null}
        </div>
      </header>
      <main className="mx-auto w-full max-w-[1280px] flex-1 px-6 py-10">
        {!loaded ? (
          <div className="rounded-xl border border-border-hairline bg-bg-card p-6 text-text-secondary">
            The data service is not reachable right now.{" "}
            <Link href="/topics" className="font-medium text-amber-700 underline underline-offset-4">
              Try again
            </Link>
          </div>
        ) : loaded.data.topics.length === 0 ? (
          <div className="rounded-xl border border-border-hairline bg-bg-card p-6 text-text-secondary">
            {run
              ? "The latest clustering run found no topics: every content unit was left as noise."
              : "No clustering run is stored yet, so there are no topics to show. Topics appear after the daily NLP job runs."}
          </div>
        ) : (
          <TopicsView data={loaded.data} units={loaded.units} />
        )}
      </main>
    </div>
  );
}
