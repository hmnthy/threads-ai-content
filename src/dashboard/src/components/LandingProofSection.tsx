import { LandingBlocks, SectionIndex } from "@/components/AppBlock";
import { TYPE } from "@/lib/typeScale";
import { TopicEngagementPanel } from "@/components/LandingProof";
import { SECTION, SectionHead } from "@/components/LandingParts";
import { StabilityPanel, TopicProfilePanel } from "@/components/TopicsView";
import type { ContentUnit } from "@/lib/api";
import { UNIT_NOUN, type LandingData } from "@/lib/landing";

// "Product proof" (handoff §3.4) — 3 panel dùng LẠI nguyên các khối của /topics (Thy 2026-11-01, ADR-0032: C2 một vai
// một component; bản đồ 3D nhiều màu như /topics). `LandingBlocks` đổi hình khối theo tầng B: tiêu đề lùi 1 cấp (X1),
// panel bo 20px (X3), "Method and limits" thu gọn sẵn (X5), link thuật ngữ sang bảng của /topics. Thứ tự như /topics:
// topic là gì → topic có khác phần còn lại của kênh không → các topic có bền không
const LABELS = {
  topics: ["01", "Topics from text"],
  engagement: ["02", "Topics vs the channel"],
  stability: ["03", "Stability"],
} as const;
// Mục lục 3 khối ngay dưới đầu section (Thy 2026-11-01): cùng chữ với nhãn trên tiêu đề mỗi khối
const INDEX = (Object.entries(LABELS) as [string, readonly [string, string]][]).map(
  ([id, [n, short]]) => [id, n, short] as const,
);

export function LandingProof({ data, units }: { data: LandingData | null; units: ContentUnit[] }) {
  // Bản gọn gửi xuống trình duyệt (code-reviewer: trang công khai không cần nguyên văn mọi bài): bản đồ chỉ hiện 110
  // ký tự đầu khi hover, bảng mọi content unit không có trên landing (`full=false`)
  const slim = units.map((unit) => {
    const head = (unit.text ?? unit.full_text).slice(0, 111);
    return { ...unit, text: head, full_text: head };
  });
  return (
    <section
      id="proof"
      data-screen-label="04 Product proof"
      className={`${SECTION} flex flex-col gap-8 border-t border-rule py-[104px]`}
    >
      <SectionHead eyebrow="03 · Proof" title="What the data already answers, and what it doesn't yet.">
        Each panel asks one question, answers it in a line, shows the evidence, and keeps the method one click away.
      </SectionHead>
      {data && data.topics.length > 0 ? (
        <SectionIndex sections={INDEX} label="Panels in Proof" />
      ) : null}
      {data && data.topics.length > 0 ? (
        <LandingBlocks labels={LABELS}>
          <TopicProfilePanel data={data} units={slim} full={false} />
          <TopicEngagementPanel data={data} noun={UNIT_NOUN} />
          <StabilityPanel data={data} />
        </LandingBlocks>
      ) : (
        <p className={`m-0 ${TYPE.body}`}>
          {!data
            ? "The data service is not reachable right now. Reload in a moment."
            : data.summary.latest_cluster_run
              ? "The latest clustering run found no topics: every content unit was left unclustered."
              : "No clustering run is stored yet, so there are no topics to show."}
        </p>
      )}
    </section>
  );
}
