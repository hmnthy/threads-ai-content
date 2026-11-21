"use client";

import Link from "next/link";
import { BrandLogo } from "@/components/BrandLogo";
import { ChannelLink } from "@/components/ChannelLink";
import { DEFINITION_TONE, LandingBlocks, rich, Section, TYPE } from "@/components/AppBlock";
import { formatIqrRange } from "@/components/DistributionCaption";
import { UnitVsChannel } from "@/components/UnitVsChannel";
import { CONTENT_UNIT } from "@/lib/appSections";
import { HERO_QUESTION, count, dayMonthYear, monthYear, partOfWhole, pct, type LandingData } from "@/lib/landing";

export function LandingHero({ data }: { data: LandingData | null }) {
  return (
    <section
      data-screen-label="01 Hero"
      className="mx-auto box-border flex w-full max-w-[1200px] flex-col px-4 pb-24 pt-14 sm:px-8"
    >
      <div className="flex flex-col items-center gap-6 text-center">
        {/* Hoạt cảnh chạy 1 lần mỗi 15 giây (Thy 2026-10-29); reduced-motion → bản tĩnh (BrandLogoReplay) */}
        <BrandLogo variant="lockup-replay" height={64} />
        {/* Định vị sản phẩm (Thy 2026-11-19): sản phẩm AI = ứng dụng NLP + RAG pipeline visualizer, nói ngay trên H1;
            vai eyebrow trang (label 12px w600 amber, như PageHeader của trang app). H1 giữ tagline (ADR-0009). */}
        <span className="text-[12px] font-semibold tracking-[0.14em] text-amber-700">
          AN AI PRODUCT · NLP ANALYTICS + RAG PIPELINE VISUALIZER
        </span>
        <h1 className="m-0 text-[clamp(44px,6.4vw,76px)] font-extrabold leading-none tracking-[-0.04em] [text-wrap:balance]">
          The algorithm, read back to you.
        </h1>
        {/* Pitch 2 đoạn (Thy 2026-11-19): đoạn 1 = ý tưởng sản phẩm — kênh nào, của ai, so với gì (tên kênh là link tới
            Threads thật); đoạn 2 = công nghệ. Cô đọng, rộng 880px (Thy: dùng bớt khoảng trắng 2 bên — nới X8 ~720px).
            Hai đoạn CÙNG trải hết bề rộng khung (L5; `pretty`, không `balance` — balance co từng đoạn một kiểu, 2 lề lệch
            nhau, Thy bắt 2026-11-19). */}
        <div className="flex max-w-[880px] flex-col gap-3">
          <p className="m-0 text-[18px] leading-[1.6] text-text-secondary [text-wrap:pretty]">
            Unthreaded is an AI product that reads <ChannelLink />, Thy&apos;s Threads channel for Vietnamese students and
            workers in France, and ranks content units by engagement rate within the channel.
          </p>
          <p className="m-0 text-[18px] leading-[1.6] text-text-secondary [text-wrap:pretty]">
            An NLP pipeline finds topics in the Vietnamese text by meaning. A RAG pipeline visualizer shows which
            passages each search setup ranks first for a fixed question.
          </p>
        </div>
        {/* Định nghĩa ngay sau lần đầu dùng từ (Thy 2026-11-01: người lạ không gặp từ trước khi biết nghĩa) */}
        {/* Cùng khung 880px với pitch ngay trên (L5: một bề rộng cho khối chữ căn giữa của hero). Lớp phụ, nhạt hơn pitch
            (Thy 2026-11-20: định nghĩa cần biết thêm, không phải hook — không được lấn pitch): tông DEFINITION_TONE,
            chung với mọi dòng định nghĩa của `PageHeader` (4 trang app, kể cả RAG pipeline) */}
        <p className={`m-0 max-w-[880px] ${TYPE.note} ${DEFINITION_TONE}`}>
          {rich(CONTENT_UNIT)}
        </p>
        <div className="flex flex-wrap justify-center gap-3">
          {/* Vai nút CTA 15px w600 của trang giới thiệu (Thy 2026-11-01, ADR-0032) */}
          <Link
            href="/overview"
            className={`flex h-12 items-center rounded-full bg-amber-600 px-[22px] ${TYPE.cta} text-white hover:bg-amber-700`}
          >
            View live dashboard
          </Link>
          <a
            href="#method"
            className={`flex h-12 items-center rounded-full border border-border-hairline bg-bg-card px-[22px] ${TYPE.cta} text-text-primary`}
          >
            See how it works
          </a>
        </div>
      </div>
      {data ? <ChannelStats data={data} /> : null}
      {/* Panel hero dùng khuôn khối chung (C1/C2) ở hình khối landing; tiêu đề khối nằm ngay dưới H1 — ngoại lệ T5
          Thy duyệt 2026-11-01 (ADR-0032), máy đo nhận qua data-ux="hero-panel" */}
      <div className="mt-10">
        <LandingBlocks>
          {data?.hero ? (
            <HeroPanel data={data} />
          ) : (
            <HeroEmpty reason={data === null ? "offline" : data.heroFound ? "no-views" : "missing"} />
          )}
        </LandingBlocks>
      </div>
    </section>
  );
}

// Dải thống kê kênh (Thy duyệt 2026-10-08): định nghĩa mẫu số MỘT lần trước bài mẫu, để các câu sau chỉ cần nói
// "the channel's content units" (một tên "content units" trên cả landing — Thy 2026-11-01). Mọi số từ API:
// /pipeline/summary, /analytics/overview.
function ChannelStats({ data }: { data: LandingData }) {
  const run = data.summary.latest_cluster_run;
  const total = data.summary.content_units;
  const measured = data.channel.stats.n;
  // Median luôn kèm IQR + n (N4/K5); số là phần của số trước ghi % làm tròn xuống (K4) — ux-reviewer PR 2b
  const items: { value: string; label: string; note?: string }[] = [
    {
      value: count(total),
      label: data.firstPostAt ? `content units since ${monthYear(data.firstPostAt)}` : "content units",
    },
    {
      value: count(measured),
      label: "with recorded views",
      note: total > 0 ? `${partOfWhole(measured, total)} of ${count(total)}` : undefined,
    },
    {
      value: measured > 0 ? pct(data.channel.stats.median) : "—",
      label: "median engagement rate",
      note: measured > 0 ? `middle half ${formatIqrRange(data.channel.stats)} (IQR) · n = ${count(measured)}` : undefined,
    },
    ...(run ? [{ value: String(run.n_clusters), label: "topics" }] : []),
  ];
  return (
    <div className="mt-12 flex flex-col items-center gap-3">
      <dl className="m-0 flex flex-wrap justify-center gap-x-10 gap-y-4">
        {items.map((item) => (
          <div key={item.label} className="flex flex-col items-center gap-0.5">
            <dt className={`order-2 ${TYPE.note}`}>{item.label}</dt>
            <dd className={`order-1 m-0 ${TYPE.metric}`}>{item.value}</dd>
            {item.note ? <dd className={`order-3 m-0 ${TYPE.mono} text-text-muted`}>{item.note}</dd> : null}
          </div>
        ))}
      </dl>
      {data.summary.latest_snapshot_at ? (
        <span className={`${TYPE.mono} text-text-muted`}>Data as of {dayMonthYear(data.summary.latest_snapshot_at)}</span>
      ) : null}
    </div>
  );
}

const EMPTY_REASON = {
  offline: "The data service is not reachable right now. Reload in a moment.",
  "no-views": "This content unit has no recorded views yet, so it cannot be placed against the channel.",
  missing: "This content unit is not in the database yet, so it cannot be placed against the channel.",
} as const;

const HERO_PURPOSE =
  "Ranks this content unit against the channel's other content units by engagement rate: likes, replies, reposts and quotes per 100 views of its opening post.";

function HeroEmpty({ reason }: { reason: keyof typeof EMPTY_REASON }) {
  return (
    <Section id="example" ux="hero-panel" n="00" short="One real content unit" title={HERO_QUESTION} purpose={HERO_PURPOSE}>
      <p className={`m-0 ${TYPE.body}`}>{EMPTY_REASON[reason]}</p>
    </Section>
  );
}

// Panel hero = bài mẫu cố định đặt vào phân phối của kênh; phần thân dùng chung với khối 02 của /analytics
// (`UnitVsChannel`), nên hai nơi luôn cùng phép xếp hạng và cùng câu trả lời. Link dưới biểu đồ dẫn thẳng tới khối đó
// (Thy 2026-11-02: lời hứa "how each content unit … did" có đường đi tới chỗ giao)
function HeroPanel({ data }: { data: LandingData }) {
  const hero = data.hero!;
  return (
    <Section id="example" ux="hero-panel" n="00" short="One real content unit" title={HERO_QUESTION} purpose={HERO_PURPOSE}>
      <UnitVsChannel
        data={data}
        topicId={hero.topicId}
        value={hero.rate}
        footer={
          <Link href="/analytics#unit" className={`w-fit ${TYPE.note} font-medium text-amber-700 underline underline-offset-4`}>
            Compare any other content unit by engagement, share or conversation rate, on the Analytics page →
          </Link>
        }
      />
    </Section>
  );
}
