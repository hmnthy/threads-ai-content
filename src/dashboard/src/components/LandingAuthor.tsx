import Image from "next/image";
import { Bullets } from "@/components/AppBlock";
import { SECTION, SectionHead } from "@/components/LandingParts";
import { count, parisDate, type LandingData } from "@/lib/landing";

// "About the channel" (handoff §3.6, design-system §10: ảnh 200×240, radius 16).
// Bio DRAFT — chỉ dựa trên fact đã có trong CLAUDE.md (kênh "thydilammuon", người Việt tại
// Pháp, nội dung alternance/xin việc/lifestyle). Chờ Thy duyệt trước khi coi là bản cuối.
export function LandingAuthor({ data }: { data: LandingData | null }) {
  const summary = data?.summary ?? null;
  const run = summary?.latest_cluster_run ?? null;

  return (
    <section
      id="about"
      data-screen-label="06 About the channel"
      className={`${SECTION} flex flex-wrap items-start gap-12 py-[104px]`}
    >
      <div className="h-60 w-[200px] flex-none overflow-hidden rounded-2xl bg-bg-surface">
        <Image
          src="/photo-author.jpg"
          alt="Thy, author of the @thydilammuon Threads channel"
          width={200}
          height={240}
          className="block h-full w-full object-cover"
          style={{ objectPosition: "50% 30%" }}
        />
      </div>
      <div className="flex min-w-0 flex-[1_1_320px] flex-col gap-[18px]">
        {/* Cùng đầu section display-2 với mọi section (T3: một kiểu display-2 trên cả trang — ADR-0032) */}
        <SectionHead eyebrow="05 · About the channel" title="Thy · @thydilammuon">
          Thy is a Vietnamese creator living and working in France. She writes on Threads about alternance, job hunting
          and everyday life as an expat. Unthreaded started as a way to understand her own channel from its real posts,
          and grew into the statistics and NLP case study on this site.
        </SectionHead>
        {summary ? (
          <div className="flex flex-col gap-2">
            {/* Dòng mono 8 số cũ → gạch đầu dòng dọc, mỗi số có nghĩa (N1); không tiêu đề riêng: section chỉ có 1 khối
                nên hộp con sẽ nằm thẳng dưới display-2 (T5) */}
            <Bullets
              items={[
                `**${count(summary.content_units)} content units** published since the channel's first post.`,
                `**${count(summary.reply_roles.author_answer)} answers to followers** and ${count(summary.reply_roles.outbound)} replies on other accounts' posts, both kept apart from the content units.`,
                "Views and interactions re-read **every 4 hours** while the collecting laptop is awake.",
                run
                  ? `Topics from the clustering run of **${parisDate(run.run_at)}**, named by Claude; ${count(run.n_noise)} content units fit no topic (unclustered).`
                  : null,
              ]}
            />
          </div>
        ) : null}
      </div>
    </section>
  );
}
