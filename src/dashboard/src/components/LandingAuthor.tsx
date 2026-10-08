import Image from "next/image";
import { SECTION } from "@/components/LandingParts";
import { count, parisTime, type LandingData } from "@/lib/landing";

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
      <div className="flex min-w-0 max-w-[760px] flex-[1_1_320px] flex-col gap-[18px]">
        <span className="font-mono text-[13px] font-medium text-amber-600">05 · About the channel</span>
        <h2 className="m-0 text-[clamp(28px,3vw,38px)] font-extrabold leading-[1.1] tracking-[-0.03em]">
          Thy · @thydilammuon
        </h2>
        <p className="m-0 text-base leading-[1.7] text-text-secondary [text-wrap:pretty]">
          Thy is a Vietnamese creator living and working in France. She writes on Threads about
          alternance, job hunting and everyday life as an expat. Unthreaded started as a way to
          understand her own channel from its real posts, and grew into the statistics and NLP case
          study on this site.
        </p>
        {summary ? (
          <span className="font-mono text-[12.5px] leading-[1.7] text-text-muted">
            {count(summary.content_units)} posts · {count(summary.reply_roles.author_answer)} answers to
            followers · {count(summary.reply_roles.self_continuation)} follow-up parts ·{" "}
            {count(summary.reply_roles.outbound)} replies on other accounts · snapshots every 4h while
            the machine is awake
            {run
              ? ` · topics as clustered ${parisTime(run.run_at)}, named by Claude · ${count(run.n_noise)} posts unclustered`
              : ""}
          </span>
        ) : null}
      </div>
    </section>
  );
}
