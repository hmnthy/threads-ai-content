import { PageHeader } from "@/components/AppBlock";
import { RagPipelineView } from "@/components/RagPipelineView";
import { RAG_SECTIONS } from "@/lib/ragPage";

// Trang "RAG pipeline visualization" (ADR-0037 D1, bản đầu thu hẹp — Thy chốt 2026-11-12). Server component chỉ vẽ
// đầu trang; file demo tải phía trình duyệt (RagPipelineView) vì engine xếp hạng chạy ở đó (ADR-0037 D3).
export default function RagPipelinePage() {
  return (
    <div className="flex flex-1 flex-col">
      <PageHeader
        eyebrow="Search · Retrieval demo"
        title="RAG pipeline visualization"
        question="For a fixed question, which passages does each retrieval setup rank first, and where does the correct answer land?"
        // copy-reviewer vòng 1 (B1): định nghĩa RAG trước khi dùng, nói rõ trang không có câu trả lời (ADR-0037 D4)
        definition="**RAG** (retrieval-augmented generation) first finds source passages, then has a model write an answer from them; this page shows only the finding step and writes no answer. A **passage** is a piece of a content unit (an opening post plus the follow-up posts its author added), cut by the chunking method you choose."
        // Mốc đóng băng: ADR-0037 D2 (2026-11-05); file demo không ghi ngày này
        chips={["frozen demo data · Nov 5, 2026", "scores precomputed"]}
        sections={RAG_SECTIONS}
      />
      <main className="mx-auto w-full max-w-[1280px] flex-1 px-6 py-10">
        <RagPipelineView />
      </main>
    </div>
  );
}
